[CmdletBinding()]
param(
    [switch]$InstallPrerequisites,
    [switch]$DownloadModels,
    [switch]$CheckOnly,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

# 完整安装过程记录到 %TEMP%\2byteasr-setup.log，方便排查
$TranscriptPath = Join-Path $env:TEMP "2byteasr-setup.log"
Start-Transcript -Path $TranscriptPath -Append -ErrorAction SilentlyContinue | Out-Null
Write-Host "[日志] 安装过程已记录到 $TranscriptPath" -ForegroundColor DarkGray

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SetupEnvironment = Join-Path $PSScriptRoot "setup_environment.ps1"
$DownloadModelScript = Join-Path $PSScriptRoot "download_models.ps1"
$Launcher = Join-Path $ProjectRoot "2ByteASR.exe"
$SetupMarker = Join-Path $ProjectRoot "2byteasr.setup-complete"

# 安装步骤进度：标题栏 + Write-Progress 双通道，用户随时知道进度与等待时间
$script:StepIndex = 0
$script:StepTotal = 5
function Set-InstallStep {
    param([string]$Label)
    $script:StepIndex++
    if ($Host.UI.RawUI) {
        $Host.UI.RawUI.WindowTitle = "2ByteASR 安装 - 步骤 $($script:StepIndex)/$($script:StepTotal)：$Label"
    }
    Write-Progress -Activity "2ByteASR 安装" -Status $Label `
        -PercentComplete ([math]::Round(100 * $script:StepIndex / $script:StepTotal))
}

# 提前询问 Qwen 复核模型：环境安装需要较长时间，不能等装完才让用户选择。
$IncludeQwenChoice = $false
if ($DownloadModels) {
    $qwenConfig = Join-Path $ProjectRoot "models\Qwen3-ASR-1.7B\config.json"
    if ($env:2BYTEASR_INCLUDE_QWEN -or (Test-Path $qwenConfig)) {
        $IncludeQwenChoice = $true
        if (Test-Path $qwenConfig) { Write-Host "[Qwen] 检测到 Qwen3-ASR 模型已存在。" -ForegroundColor Green }
    } elseif (-not $env:2BYTEASR_NO_QWEN) {
        $answer = Read-Host "附加下载 Qwen3-ASR 复核模型（约 4.7 GB，提升准确度）？[y/N]"
        if ($answer -match "^[yY]") { $IncludeQwenChoice = $true }
    }
    $qwenText = if ($IncludeQwenChoice) { "包含" } else { "不包含" }
    Write-Host "[选择] Qwen3-ASR 复核模型：$qwenText（可随时用 download_models.bat 补下；2BYTEASR_NO_QWEN=1 关闭提问）" -ForegroundColor Cyan
}

# 幂等退出：已完全配置（标记 + 双环境 + 必需模型都在）时不再破坏性重装。
# 补 Qwen / 修复模型请用 download_models.bat；强制重装设 2BYTEASR_FORCE_SETUP=1。
$MainPy = Join-Path $ProjectRoot ".venv-main\Scripts\python.exe"
$MossPy = Join-Path $ProjectRoot ".venv-moss\Scripts\python.exe"
$ModelRoot = Join-Path $ProjectRoot "models"
$requiredModels = @(
    "MOSS-Transcribe-Diarize\model-00000-of-00001.safetensors",
    "FireRedVAD\VAD\model.pth.tar",
    "FireRedASR2-AED\model.pth.tar",
    "spkrec-ecapa-voxceleb\embedding_model.ckpt"
)
$alreadyConfigured = (Test-Path $SetupMarker) -and (Test-Path $MainPy) -and (Test-Path $MossPy)
if ($alreadyConfigured -and -not $env:2BYTEASR_FORCE_SETUP) {
    foreach ($rel in $requiredModels) {
        if (-not (Test-Path (Join-Path $ModelRoot $rel))) { $alreadyConfigured = $false; break }
    }
}
if ($alreadyConfigured) {
    Write-Host "[完成] 2ByteASR 已配置完成（环境与必需模型均已就绪），无需重装。" -ForegroundColor Green
    Write-Host "       补下 Qwen 复核模型或修复模型：运行 download_models.bat" -ForegroundColor Yellow
    Write-Host "       强制重装（会重建环境）：设置 2BYTEASR_FORCE_SETUP=1 后重跑" -ForegroundColor DarkGray
    exit 0
}

# 每次开始配置先清除完成标记：只有 venv 而无标记 = 上次配置中断，
# 2ByteASR.exe 启动器会引导“继续配置”（已下载内容续传），而不是静默失败。
# 注意：必须放在 $ProjectRoot 赋值之后（Join-Path 不接受 null 路径）。
Remove-Item $SetupMarker -Force -ErrorAction SilentlyContinue

# 磁盘预检：模型（按 Qwen 选择）+ 环境/源码/缓存预留，不足直接拦截。
# （模型下载阶段还会再查一次；这里尽早拦截，避免装到一半才发现空间不够）
$modelGb = if ($IncludeQwenChoice) { 11.7 } else { 7 }
$needGb = [math]::Ceiling($modelGb + 3)
$driveName = ([System.IO.Path]::GetPathRoot($ProjectRoot)).TrimEnd('\').TrimEnd(':')
try {
    $drive = Get-PSDrive -Name $driveName
    $freeGb = [math]::Round($drive.Free / 1GB, 1)
    if ($freeGb -lt $needGb) {
        throw "磁盘空间不足：项目盘（${driveName}:）仅剩 $freeGb GB，至少需要 $needGb GB（模型 $modelGb GB + 环境预留 3 GB）。请清理空间后重试。"
    }
    Write-Host "[检查] 磁盘空间：$freeGb GB 可用（本次需要约 $needGb GB）" -ForegroundColor Cyan
} catch {
    Write-Warning "磁盘预检失败：$($_.Exception.Message)（将继续安装，模型下载时还会再次检查）"
}

function Add-BundledToolsToPath {
    # 便携版内置工具（tools/）优先：ffmpeg/git/uv 无需联网下载。
    # Refresh-ProcessPath 会重建整个 PATH，必须在这里一并恢复——
    # 否则便携包首次检查通过、刷新 PATH 后 tools 条目丢失，
    # 会误报“缺少系统依赖 uv, git, ffmpeg, ffprobe”。
    $tools = Join-Path $ProjectRoot "tools"
    foreach ($extra in @($tools, (Join-Path $tools "ffmpeg\bin"), (Join-Path $tools "git\cmd"), (Join-Path $tools "git\bin"))) {
        if (Test-Path $extra) { $env:Path = "$extra;$env:Path" }
    }
}

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $extraPaths = @(
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"),
        (Join-Path $env:LOCALAPPDATA "Programs\Git\cmd"),
        (Join-Path $env:USERPROFILE ".local\bin"),
        (Join-Path $env:ProgramFiles "Git\cmd")
    )
    $env:Path = (@($machinePath, $userPath) + $extraPaths | Where-Object { $_ }) -join ";"
    Add-BundledToolsToPath
}

function Get-MissingCommands {
    $missing = @()
    foreach ($name in @("uv", "git", "ffmpeg", "ffprobe", "nvidia-smi")) {
        if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
            $missing += $name
        }
    }
    return $missing
}

function Install-WinGetPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][string]$Label
    )
    # 下载可能因网络瞬断失败（如 0x80072f78 超时），重试最多 3 次。
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        Write-Host "[Prerequisite] Installing $Label ... (第 $attempt 次尝试)" -ForegroundColor Cyan
        if ($Label -in @("Git", "uv")) {
            Write-Host "  提示：GitHub 组件在国内网络下可能较慢，请耐心等待；失败会自动重试。" -ForegroundColor DarkYellow
        }
        & winget install --id $Id --exact --silent --disable-interactivity `
            --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -eq 0) { return }
        Write-Warning "$Label 安装失败（winget 退出码 $LASTEXITCODE），正在重试..."
        Start-Sleep -Seconds 5
    }
    throw "$Label installation failed (winget exit code $LASTEXITCODE).`n请手动重试：winget install --id $Id -e"
}


function Download-WithProxy {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$OutFile
    )
    # Invoke-WebRequest 遵循系统代理设置；多次尝试以对抗网络抖动。
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -ErrorAction Stop
            if (Test-Path $OutFile) { return }
        } catch {
            if ($attempt -ge 3) { throw }
            Write-Warning "下载失败（$Url），正在重试（$attempt/3）..."
            Start-Sleep -Seconds 4
        }
    }
    throw "下载失败：$Url"
}


function Install-GitDirect {
    # 国内网络下 winget 直连 GitHub 可能极慢甚至卡死；
    # 改为官方安装包直装，依次尝试国内加速代理与 GitHub 官方源（带连接超时）。
    $downloads = Join-Path $env:TEMP "2byteasr-prereq"
    New-Item -ItemType Directory -Path $downloads -Force | Out-Null
    $gitInstaller = Join-Path $downloads "git.exe"
    $sources = @(
        "https://ghfast.top/https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.3/Git-2.55.0.3-64-bit.exe",
        "https://ghproxy.net/https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.3/Git-2.55.0.3-64-bit.exe",
        "https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.3/Git-2.55.0.3-64-bit.exe"
    )
    $downloaded = $false
    foreach ($url in $sources) {
        try {
            Write-Host "[Prerequisite] 正在下载 Git（约 62 MB，国内网络可能较慢）..." -ForegroundColor Cyan
            Invoke-WebRequest -Uri $url -OutFile $gitInstaller -UseBasicParsing -TimeoutSec 300 -ErrorAction Stop
            if ((Get-Item $gitInstaller).Length -gt 10MB) { $downloaded = $true; break }
        } catch {
            Write-Warning "Git 下载失败（$url），尝试下一个源..."
        }
    }
    if (-not $downloaded) {
        throw "Git 下载失败（国内网络受限）。可手动下载 Git for Windows 安装包后重新运行 setup_2byteasr.bat。"
    }
    # 装到当前用户目录（无需管理员权限），并持久化 PATH
    $gitInstallDir = Join-Path $env:LOCALAPPDATA "Programs\Git"
    $gitLog = Join-Path $env:TEMP "git-install.log"
    Remove-Item $gitLog -Force -ErrorAction SilentlyContinue
    Write-Host "[Prerequisite] 安装 Git 到 $gitInstallDir ..." -ForegroundColor Cyan
    # 兼容两种安装器：Inno（/VERYSILENT /DIR）与 NSIS（/S /D）；
    # NSIS 的 /D= 必须是命令行最后一个参数；GUI 安装器用 & 调用时
    # PowerShell 5.1 拿不到退出码，必须用 Start-Process -Wait。
    $p = Start-Process -FilePath $gitInstaller -ArgumentList @(
        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/S",
        "/DIR=$gitInstallDir", "/LOG=$gitLog", "/D=$gitInstallDir"
    ) -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        throw "Git 安装失败（退出码 $($p.ExitCode)）。安装日志：$gitLog"
    }
    $gitCmd = ""
    foreach ($candidate in @(
        (Join-Path $gitInstallDir "cmd\git.exe"), (Join-Path $gitInstallDir "bin\git.exe"),
        (Join-Path $gitInstallDir "usr\bin\git.exe"), (Join-Path $gitInstallDir "mingw64\bin\git.exe"),
        (Join-Path $env:ProgramFiles "Git\cmd\git.exe"), (Join-Path $env:ProgramFiles "Git\usr\bin\git.exe"),
        (Join-Path $env:ProgramFiles "Git\mingw64\bin\git.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Git\cmd\git.exe")
    )) {
        if (Test-Path $candidate) { $gitCmd = $candidate; break }
    }
    if (-not $gitCmd) {
        $logTail = ""
        if (Test-Path $gitLog) {
            $logTail = "`n--- Git 安装日志（末尾 25 行）---`n" + ((Get-Content $gitLog -Tail 25) -join "`n")
        }
        throw "Git 安装完成但未找到 git.exe（退出码 0）。$logTail`n请手动安装 Git for Windows（https://git-scm.com/download/win）后重新运行 setup_2byteasr.bat。"
    }
    $gitBin = Split-Path $gitCmd -Parent
    # 当前进程与用户级 PATH 持久化（后续进程也能找到 git）
    $env:Path = "$gitBin;$env:Path"
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$gitBin*") {
        [Environment]::SetEnvironmentVariable("Path", "$gitBin;$userPath", "User")
    }
    Write-Host "[Prerequisite] Git 已就绪：$gitCmd" -ForegroundColor Green
}


function Install-DirectPrerequisites {
    # winget 不可用时的降级方案：从官方渠道直接下载安装（使用系统代理）。
    $downloads = Join-Path $env:TEMP "2byteasr-prereq"
    New-Item -ItemType Directory -Path $downloads -Force | Out-Null
    if ($missing -contains "uv") {
        Write-Host "[Prerequisite] 从 GitHub 官方下载 uv ..." -ForegroundColor Cyan
        Download-WithProxy "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" (Join-Path $downloads "uv.zip")
        Expand-Archive (Join-Path $downloads "uv.zip") (Join-Path $downloads "uv") -Force
        $uvDir = Join-Path $env:LOCALAPPDATA "uv"
        New-Item -ItemType Directory -Path $uvDir -Force | Out-Null
        Copy-Item (Join-Path $downloads "uv\uv.exe") (Join-Path $uvDir "uv.exe") -Force
        $env:Path = "$uvDir;$env:Path"
    }
    if ($missing -contains "git") {
        Install-GitDirect
    }
    if (($missing -contains "ffmpeg") -or ($missing -contains "ffprobe")) {
        Write-Host "[Prerequisite] 从 gyan.dev 官方下载 FFmpeg ..." -ForegroundColor Cyan
        $ffmpegZip = Join-Path $downloads "ffmpeg.zip"
        Download-WithProxy "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" $ffmpegZip
        Expand-Archive $ffmpegZip (Join-Path $downloads "ffmpeg") -Force
        $ffBin = Get-ChildItem (Join-Path $downloads "ffmpeg") -Recurse -Directory |
            Where-Object { $_.Name -eq "bin" } | Select-Object -First 1
        if (-not $ffBin) { throw "FFmpeg 解压后未找到 bin 目录。" }
        $dest = Join-Path $env:LOCALAPPDATA "Programs\FFmpeg\bin"
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
        Copy-Item (Join-Path $ffBin.FullName "ffmpeg.exe") $dest -Force
        Copy-Item (Join-Path $ffBin.FullName "ffprobe.exe") $dest -Force
        $env:Path = "$dest;$env:Path"
    }
}

Refresh-ProcessPath
$missing = @(Get-MissingCommands)

if ($CheckOnly) {
    if ($missing.Count -gt 0) {
        Write-Host "[Missing prerequisites] $($missing -join ', ')" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] System prerequisites are ready." -ForegroundColor Green
    exit 0
}

$gpuWarned = $false
if ($missing -contains "nvidia-smi") {
    $gpuWarned = $true
    Write-Warning "未检测到 NVIDIA GPU 驱动（nvidia-smi 不可用）。环境与模型仍会安装，但 MOSS/FireRed/Qwen 实际转写需要 CUDA 显卡；如确认无 GPU 环境可忽略此提示。"
    $missing = @($missing | Where-Object { $_ -ne "nvidia-smi" })
}

if ($InstallPrerequisites) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Warning "winget 不可用，改用官方渠道直接下载安装依赖（使用系统代理）..."
        Install-DirectPrerequisites
    } else {
        if ($missing -contains "uv") { Install-WinGetPackage "astral-sh.uv" "uv" }
        if ($missing -contains "git") { Install-GitDirect }
        if (($missing -contains "ffmpeg") -or ($missing -contains "ffprobe")) {
            Install-WinGetPackage "Gyan.FFmpeg" "FFmpeg"
        }
    }
    Refresh-ProcessPath
}

$remaining = @(Get-MissingCommands)
if ($gpuWarned) {
    $remaining = @($remaining | Where-Object { $_ -ne "nvidia-smi" })
}
if ($remaining.Count -gt 0) {
    $tools = Join-Path $ProjectRoot "tools"
    if (Test-Path $tools) {
        Write-Host "tools/ 目录存在（$tools），但以下命令仍不可用。tools 内文件（前 25 项）：" -ForegroundColor Yellow
        Get-ChildItem $tools -Recurse -File -ErrorAction SilentlyContinue |
            Select-Object -First 25 | ForEach-Object {
                Write-Host "  $($_.FullName.Substring($tools.Length + 1))" -ForegroundColor DarkGray
            }
    } else {
        Write-Host "便携版应自带 tools/ 目录（$tools），当前缺失。请确认解压完整，或改用 Setup 安装版。" -ForegroundColor Yellow
    }
    throw "Prerequisites are still missing: $($remaining -join ', ')."
}

Write-Host "[1/2] Creating Python environments and installing runtime dependencies ..." -ForegroundColor Cyan
Set-InstallStep "创建 Python 环境并安装依赖（首次约 5-15 分钟）"
& $SetupEnvironment
if ($LASTEXITCODE -ne 0) {
    throw "Python environment setup failed (exit code $LASTEXITCODE)."
}

if ($DownloadModels) {
    $totalText = if ($IncludeQwenChoice) { "约 11.7 GB（含 Qwen 复核模型）" } else { "约 7 GB" }
    Set-InstallStep "下载模型（$totalText，可断点续传）"
    Write-Host "[2/2] 下载固定版本模型（$totalText：MOSS 转写/说话人、FireRed 字级时间轴、声纹；可续传）..." -ForegroundColor Cyan
    if ($IncludeQwenChoice) {
        & $DownloadModelScript -Yes -IncludeQwen
    } else {
        & $DownloadModelScript -Yes
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Model download failed (exit code $LASTEXITCODE)."
    }
} else {
    Write-Host "[2/2] Model download skipped. Run download_models.bat later." -ForegroundColor Yellow
}

Set-InstallStep "收尾"
# 全部成功后才写完成标记：2ByteASR.exe 启动器据此判断环境是否完整。
# 必须先写标记再启动启动器，避免启动器先读到缺标记而误弹“继续配置”。
Set-Content -LiteralPath $SetupMarker -Value (Get-Date).ToString("o") -Encoding ascii

if (-not $NoLaunch -and (Test-Path -LiteralPath $Launcher)) {
    Start-Process -FilePath $Launcher -WorkingDirectory $ProjectRoot
}

Write-Host "[OK] 2ByteASR is ready." -ForegroundColor Green
