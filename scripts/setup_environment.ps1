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
    if ($LASTEXITCODE -ne 0) { throw "无法检查 $Label 工作区。" }
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


function New-UvVenv {
    param(
        [Parameter(Mandatory = $true)][string]$PythonVersion,
        [Parameter(Mandatory = $true)][string]$VenvPath
    )
    # uv 的 Python 版本链接（junction）在中断安装后可能残留损坏条目，
    # 触发 Windows “不受信任的装入点”（os error 448）；venv 创建失败时
    # 一律清理 uv\python 残留后重试一次（Invoke-External 异常不包含 uv 明细）。
    for ($attempt = 1; $attempt -le 2; $attempt++) {
        try {
            Invoke-External $Uv @("venv", "--python", $PythonVersion, "--allow-existing", $VenvPath)
            return
        } catch {
            if ($attempt -ge 2) { throw }
            Write-Warning "uv 创建虚拟环境失败，清理 uv\python 残留后重试..."
            Remove-Item (Join-Path $env:LOCALAPPDATA "uv\python") -Recurse -Force -ErrorAction SilentlyContinue
            Remove-Item (Join-Path $env:APPDATA "uv\python") -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "[环境] 创建主流程 Python $($Lock.python.main) ..."
New-UvVenv ([string]$Lock.python.main) $MainEnv
Invoke-External $Uv @("pip", "install", "--python", $MainPython, "-r", (Join-Path $ProjectRoot "requirements-main.txt"), "--torch-backend=auto")

Write-Host "[环境] 创建 MOSS Python $($Lock.python.moss) ..."
New-UvVenv ([string]$Lock.python.moss) $MossEnv
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
