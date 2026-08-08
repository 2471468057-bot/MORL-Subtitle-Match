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
    throw "Prerequisites are still missing: $($remaining -join ', ')."
}

Write-Host "[1/2] Creating Python environments and installing runtime dependencies ..." -ForegroundColor Cyan
& $SetupEnvironment
if ($LASTEXITCODE -ne 0) {
    throw "Python environment setup failed (exit code $LASTEXITCODE)."
}

if ($DownloadModels) {
    Write-Host "[2/2] Downloading pinned models (about 11 GB, resumable) ..." -ForegroundColor Cyan
    & $DownloadModelScript -Yes
    if ($LASTEXITCODE -ne 0) {
        throw "Model download failed (exit code $LASTEXITCODE)."
    }
} else {
    Write-Host "[2/2] Model download skipped. Run download_models.bat later." -ForegroundColor Yellow
}

if (-not $NoLaunch -and (Test-Path -LiteralPath $Launcher)) {
    Start-Process -FilePath $Launcher -WorkingDirectory $ProjectRoot
}

Write-Host "[OK] 2ByteASR is ready." -ForegroundColor Green
