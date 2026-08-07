[CmdletBinding()]
param(
    [switch]$InstallPrerequisites,
    [switch]$DownloadModels,
    [switch]$CheckOnly,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SetupEnvironment = Join-Path $PSScriptRoot "setup_environment.ps1"
$DownloadModelScript = Join-Path $PSScriptRoot "download_models.ps1"
$Launcher = Join-Path $ProjectRoot "2ByteASR.exe"

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $extraPaths = @(
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"),
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
    Write-Host "[Prerequisite] Installing $Label ..." -ForegroundColor Cyan
    & winget install --id $Id --exact --silent --disable-interactivity `
        --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "$Label installation failed (winget exit code $LASTEXITCODE)."
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
        throw "winget is unavailable. Install App Installer from Microsoft Store first."
    }
    if ($missing -contains "uv") { Install-WinGetPackage "astral-sh.uv" "uv" }
    if ($missing -contains "git") { Install-WinGetPackage "Git.Git" "Git" }
    if (($missing -contains "ffmpeg") -or ($missing -contains "ffprobe")) {
        Install-WinGetPackage "Gyan.FFmpeg" "FFmpeg"
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
