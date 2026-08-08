[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$ForceSourceRefresh
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LockPath = Join-Path $ProjectRoot "dependencies.lock.json"
$MainEnv = Join-Path $ProjectRoot ".venv-main"
$MossEnv = Join-Path $ProjectRoot ".venv-moss"
$MainPython = Join-Path $MainEnv "Scripts\python.exe"
$MossPython = Join-Path $MossEnv "Scripts\python.exe"

function Show-RecoveryHint {
    param([string]$Name)
    switch ($Name) {
        "uv" { Write-Host "  安装说明：https://docs.astral.sh/uv/getting-started/installation/" }
        "git" { Write-Host "  可执行：winget install --id Git.Git -e" }
        "ffmpeg" { Write-Host "  可执行：winget install --id Gyan.FFmpeg -e" }
        "ffprobe" { Write-Host "  ffprobe 随 FFmpeg 一起安装。" }
        "nvidia-smi" { Write-Host "  请安装或更新 NVIDIA 显卡驱动：https://www.nvidia.com/Download/index.aspx" }
    }
}

function Assert-Prerequisites {
    $missing = @()
    $gpuMissing = -not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)
    foreach ($name in @("uv", "git", "ffmpeg", "ffprobe")) {
        if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
            $missing += $name
        }
    }
    if ($missing.Count -gt 0) {
        Write-Host "[缺少系统依赖] $($missing -join ', ')" -ForegroundColor Red
        foreach ($name in $missing) { Show-RecoveryHint $name }
        throw "请安装以上组件并重新运行 setup_environment.bat。"
    }

    if ($gpuMissing) {
        Write-Warning "未检测到 NVIDIA GPU 驱动（nvidia-smi 不可用）。环境与模型仍会安装，但 MOSS/FireRed/Qwen 实际转写需要 CUDA 显卡。"
        return
    }
    $memoryText = & nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null | Select-Object -First 1
    $memoryMb = 0
    [void][int]::TryParse(($memoryText -replace '[^0-9]', ''), [ref]$memoryMb)
    if ($memoryMb -gt 0 -and $memoryMb -lt 14336) {
        Write-Warning "检测到约 $([math]::Round($memoryMb / 1024, 1)) GB 显存；完整流水线建议至少 16 GB。"
    } elseif ($memoryMb -gt 0) {
        Write-Host "[硬件] NVIDIA GPU 显存约 $([math]::Round($memoryMb / 1024, 1)) GB。"
    }
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "命令失败（退出码 $LASTEXITCODE）：$FilePath $($Arguments -join ' ')"
    }
}

function Resolve-ProjectPath {
    param([string]$RelativePath)
    return Join-Path $ProjectRoot ($RelativePath -replace '/', '\')
}

function Ensure-PinnedSource {
    param(
        [Parameter(Mandatory = $true)]$Spec,
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$Marker
    )

    $destination = Resolve-ProjectPath $Spec.path
    $gitDir = Join-Path $destination ".git"
    $markerPath = Join-Path $destination $Marker

    if ((Test-Path $destination) -and -not (Test-Path $gitDir)) {
        if (-not (Test-Path $markerPath)) {
            throw "$Label 目录存在但内容不完整：$destination"
        }
        Write-Warning "$Label 是旧版无 Git 元数据目录，保留并继续使用。全新安装会固定到 $($Spec.revision)。"
        return
    }

    if (-not (Test-Path $gitDir)) {
        Write-Host "[源码] 正在获取 $Label ..."
        # 强制 autocrlf=true：FireRed 加固补丁的 Upstream/Hardened SHA-256 按 CRLF 工作区设计，
        # 全新机器 git 默认检出 LF 会导致补丁哈希校验失败（首次安装必现）。
        Invoke-External "git" @("-c", "core.autocrlf=true", "clone", "--filter=blob:none", "--no-checkout", [string]$Spec.repository, $destination)
        # 新克隆没有工作区文件，git status 会把全部文件报告为已删除（D），
        # 必须先检出固定版本，再做本地修改检查，否则首次安装会误报“本地修改”。
        Invoke-External "git" @("-c", "safe.directory=$destination", "-c", "core.autocrlf=true", "-C", $destination, "checkout", "--detach", [string]$Spec.revision)
    }

    $gitPrefix = @("-c", "safe.directory=$destination", "-C", $destination)
    $dirty = & git @gitPrefix status --porcelain
    if ($LASTEXITCODE -ne 0) {
        # git 元数据损坏（如虚拟机快照回滚后 .git 不完整），删除目录后重新获取。
        Write-Warning "$Label git 元数据异常（退出码 $LASTEXITCODE），删除后重新获取..."
        & cmd /c "rmdir /s /q `"$destination`"" 2>$null | Out-Null
        if (Test-Path $destination) {
            throw "无法清理 $Label 目录（可能被占用）：$destination"
        }
        Invoke-External "git" @("-c", "core.autocrlf=true", "clone", "--filter=blob:none", "--no-checkout", [string]$Spec.repository, $destination)
        Invoke-External "git" @("-c", "safe.directory=$destination", "-c", "core.autocrlf=true", "-C", $destination, "checkout", "--detach", [string]$Spec.revision)
        $gitPrefix = @("-c", "safe.directory=$destination", "-C", $destination)
        $dirty = & git @gitPrefix status --porcelain
        if ($LASTEXITCODE -ne 0) { throw "无法检查 $Label 工作区。" }
    }
    if ($dirty) {
        $allowedFireRedChanges = @(
            "fireredasr2s/fireredasr2/asr.py",
            "fireredasr2s/fireredvad/core/detect_model.py",
            "fireredasr2s/fireredlid/lid.py",
            "fireredasr2s/fireredpunc/punc.py"
        )
        $dirtyPaths = @($dirty | ForEach-Object { ([string]$_).Substring(3).Trim().Replace('\', '/') })
        $onlySecurityPatch = $Label -eq "FireRedASR2S" -and
            @($dirtyPaths | Where-Object { $_ -notin $allowedFireRedChanges }).Count -eq 0
        if ($onlySecurityPatch) {
            # 目录只有允许的安全补丁修改时，执行完整补丁补齐（含上次中断未完成的文件），
            # 而不是仅 CheckOnly——部分补丁状态会让 CheckOnly 误报缺失。
            & (Join-Path $PSScriptRoot "harden_firered_source.ps1")
        } else {
            throw "$Label 存在本地修改，安装器不会覆盖：$destination"
        }
    }

    $current = (& git @gitPrefix rev-parse HEAD 2>$null).Trim()
    if ($ForceSourceRefresh -or $current -ne [string]$Spec.revision) {
        & git @gitPrefix cat-file -e "$($Spec.revision)^{commit}" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Invoke-External "git" @("-c", "safe.directory=$destination", "-c", "core.autocrlf=true", "-C", $destination, "fetch", "--depth", "1", "origin", [string]$Spec.revision)
        }
        Invoke-External "git" @("-c", "safe.directory=$destination", "-c", "core.autocrlf=true", "-C", $destination, "checkout", "--detach", "--force", [string]$Spec.revision)
    }

    $resolved = (& git @gitPrefix rev-parse HEAD).Trim()
    if ($resolved -ne [string]$Spec.revision) {
        throw "$Label 版本校验失败：期望 $($Spec.revision)，实际 $resolved"
    }
    Write-Host "[源码] $Label：$resolved"
}

if (-not (Test-Path $LockPath)) {
    throw "缺少依赖版本清单：$LockPath"
}
$Lock = Get-Content -Raw -Encoding UTF8 $LockPath | ConvertFrom-Json
if ($Lock.schema_version -ne 1) {
    throw "不支持的 dependencies.lock.json schema_version：$($Lock.schema_version)"
}

Write-Host "2ByteASR 环境安装（不下载约 11 GB 模型）" -ForegroundColor Cyan
Assert-Prerequisites
if ($CheckOnly) {
    Write-Host "[完成] 系统依赖检查通过。"
    exit 0
}

Ensure-PinnedSource $Lock.sources.moss "MOSS-Transcribe-Diarize" "pyproject.toml"
Ensure-PinnedSource $Lock.sources.firered "FireRedASR2S" "fireredasr2s\__init__.py"
& (Join-Path $PSScriptRoot "harden_firered_source.ps1")

$Uv = (Get-Command uv).Source
$MossSource = Resolve-ProjectPath $Lock.sources.moss.path

# 便携版内置工具（tools/）优先加入 PATH：ffmpeg、git、uv 无需联网下载
$ToolsDir = Join-Path $ProjectRoot "tools"
if (Test-Path $ToolsDir) {
    foreach ($extra in @($ToolsDir, (Join-Path $ToolsDir "ffmpeg\bin"), (Join-Path $ToolsDir "git\cmd"), (Join-Path $ToolsDir "git\bin"))) {
        if (Test-Path $extra) { $env:Path = "$extra;$env:Path" }
    }
    if (-not $Uv) {
        $localUv = Join-Path $ToolsDir "uv.exe"
        if (Test-Path $localUv) {
            $env:Path = "$ToolsDir;$env:Path"
            $Uv = (Get-Command uv).Source
        }
    }
}

# 国内网络默认使用清华 PyPI 镜像安装依赖；
# 需要官方 PyPI 时设置环境变量 UV_DEFAULT_INDEX=https://pypi.org/simple 覆盖。
if (-not $env:UV_DEFAULT_INDEX) {
    $env:UV_DEFAULT_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"
    Write-Host "[网络] 依赖走清华 PyPI 镜像：$env:UV_DEFAULT_INDEX（可用 UV_DEFAULT_INDEX 覆盖）" -ForegroundColor Cyan
}

# 依赖缓存目录固定到项目内，避免默认 %LOCALAPPDATA%\uv\cache 占用系统盘
# （torch 等大包缓存可达数 GB）。可用 UV_CACHE_DIR 覆盖。
if (-not $env:UV_CACHE_DIR) {
    $env:UV_CACHE_DIR = Join-Path $ProjectRoot ".uv-cache"
    Write-Host "[网络] uv 依赖缓存：$env:UV_CACHE_DIR（可用 UV_CACHE_DIR 覆盖）" -ForegroundColor Cyan
}


function Resolve-SystemPython {
    param([Parameter(Mandatory = $true)][string]$MajorMinor)
    # 依次查找：常见安装路径（winget/官方安装器）→ 注册表。
    # 不用 py 启动器：找不到版本时它会把横幅写到 stderr，在
    # ErrorActionPreference=Stop 下触发 NativeCommandError。
    $short = $MajorMinor -replace '\.', ''
    foreach ($base in @((Join-Path $env:LOCALAPPDATA "Programs\Python"), (Join-Path $env:ProgramFiles "Python"))) {
        $candidate = Join-Path (Join-Path $base "Python$short") "python.exe"
        if (Test-Path $candidate) { return $candidate }
    }
    foreach ($root in @("HKLM:\SOFTWARE\Python\PythonCore\$MajorMinor\InstallPath", "HKCU:\SOFTWARE\Python\PythonCore\$MajorMinor\InstallPath")) {
        $reg = Get-ItemProperty $root -ErrorAction SilentlyContinue
        if ($reg -and $reg.'(default)' -and (Test-Path (Join-Path $reg.'(default)' "python.exe"))) {
            return (Join-Path $reg.'(default)' "python.exe")
        }
    }
    return ""
}


function Ensure-SystemPython {
    param(
        [Parameter(Mandatory = $true)][string]$MajorMinor,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $exe = Resolve-SystemPython $MajorMinor
    if ($exe) { return $exe }
    # 便携包内置 Python 安装器优先（本地安装，不联网）
    $pyVersion = if ($MajorMinor -eq "3.10") { "3.10.11" } elseif ($MajorMinor -eq "3.12") { "3.12.10" } else { $MajorMinor }
    $localInstaller = Join-Path $ProjectRoot "tools\python-$pyVersion-amd64.exe"
    if (Test-Path $localInstaller) {
        Write-Host "[环境] 使用便携包内置 Python 安装器（$pyVersion）..." -ForegroundColor Cyan
        & $localInstaller /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0 Include_doc=0 Include_tcltk=0
        $exe = Resolve-SystemPython $MajorMinor
        if ($exe) { return $exe }
        throw "$Label 需要 Python $MajorMinor。便携包内置安装器安装失败，请手动安装后重试。"
    }
    Write-Host "[环境] 未找到系统 Python $MajorMinor，尝试通过 winget 安装..." -ForegroundColor Cyan
    # winget 的进度输出会污染函数返回值，必须全部吞掉
    & winget install --id "Python.Python.$MajorMinor" --exact --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "winget 安装 Python 失败，尝试从 python.org 官方下载安装（使用系统代理）..."
        $pyVersion = if ($MajorMinor -eq "3.10") { "3.10.11" } elseif ($MajorMinor -eq "3.12") { "3.12.10" } else { $MajorMinor }
        $installer = Join-Path $env:TEMP "python-$pyVersion-amd64.exe"
        # 依次尝试 python.org 官方与华为云国内镜像
        $pyUrls = @(
            "https://www.python.org/ftp/python/$pyVersion/python-$pyVersion-amd64.exe",
            "https://mirrors.huaweicloud.com/python/$pyVersion/python-$pyVersion-amd64.exe"
        )
        for ($attempt = 1; $attempt -le ($pyUrls.Count * 2); $attempt++) {
            $url = $pyUrls[[math]::Floor(($attempt - 1) / 2)]
            try {
                Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing -ErrorAction Stop
                break
            } catch {
                if ($attempt -ge ($pyUrls.Count * 2)) {
                    throw "$Label 需要 Python $MajorMinor。官方与镜像下载均失败，请从 https://www.python.org/downloads/ 手动安装后重新运行 setup_2byteasr.bat。"
                }
                Write-Warning "下载失败（$url），正在重试..."
                Start-Sleep -Seconds 4
            }
        }
        & $installer /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0 Include_test=0 Include_doc=0 Include_tcltk=0
        if ($LASTEXITCODE -ne 0) {
            throw "$Label 需要 Python $MajorMinor。python.org 安装失败（退出码 $LASTEXITCODE），请手动安装后重新运行 setup_2byteasr.bat。"
        }
    }
    $exe = Resolve-SystemPython $MajorMinor
    if (-not $exe) {
        throw "$Label 需要 Python $MajorMinor。安装后请重新运行 setup_2byteasr.bat。"
    }
    return $exe
}


function New-StdlibVenv {
    param(
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [Parameter(Mandatory = $true)][string]$VenvPath
    )
    # 使用 python -m venv（标准库）创建环境，避免 uv 管理 Python 时
    # 创建版本链接（junction）触发 Windows “不受信任的装入点”（os error 448）。
    Remove-Item $VenvPath -Recurse -Force -ErrorAction SilentlyContinue
    Invoke-External $PythonExe @("-m", "venv", $VenvPath)
    if (-not (Test-Path (Join-Path $VenvPath "Scripts\python.exe"))) {
        throw "虚拟环境创建失败：$VenvPath"
    }
}

Write-Host "[环境] 创建主流程 Python $($Lock.python.main) ..."
$MainPythonExe = Ensure-SystemPython ([string]$Lock.python.main) "主流程"
Write-Host "[环境] 使用系统 Python：$MainPythonExe"
New-StdlibVenv $MainPythonExe $MainEnv
$MainPython = Join-Path $MainEnv "Scripts\python.exe"
Invoke-External $Uv @("pip", "install", "--python", $MainPython, "-r", (Join-Path $ProjectRoot "requirements-main.txt"), "--torch-backend=auto")

Write-Host "[环境] 创建 MOSS Python $($Lock.python.moss) ..."
$MossPythonExe = Ensure-SystemPython ([string]$Lock.python.moss) "MOSS"
Write-Host "[环境] 使用系统 Python：$MossPythonExe"
New-StdlibVenv $MossPythonExe $MossEnv
$MossPython = Join-Path $MossEnv "Scripts\python.exe"
Invoke-External $Uv @("pip", "install", "--python", $MossPython, "-e", "$MossSource[torch-runtime]", "--torch-backend=auto")

if (-not (Test-Path (Join-Path $MossEnv "Scripts\hf.exe"))) {
    Invoke-External $Uv @("pip", "install", "--python", $MossPython, "huggingface_hub[cli]==1.24.0")
}

Invoke-External $MainPython @(
    "-m", "py_compile",
    (Join-Path $ProjectRoot "auto_asr.py"),
    (Join-Path $ProjectRoot "moss_firered_pipeline.py"),
    (Join-Path $ProjectRoot "subtitle_core.py"),
    (Join-Path $ProjectRoot "twobyteasr\ui.py")
)

Write-Host ""
Write-Host "[完成] 程序环境已准备好。下一步运行 download_models.bat。" -ForegroundColor Green
