[CmdletBinding()]
param(
    [string]$OutputDir = "",
    [switch]$Lite
)

# 打包便携版 2ByteASR：程序文件 + models/（模型）+ third_party/（固定版本源码）。
# 解压到任意目录即可作为完整程序使用（首次运行 setup_2byteasr.bat 安装 Python 环境）。
# 适合国内网络下载模型困难的环境：一次性下载，解压即用。
#
# -Lite：精简版（用于 GitHub Releases，<2GB）——不含模型，只带程序 + 源码 + 内置工具；
# 首次配置时模型自动下载（约 7 GB 默认 / 11.7 GB 含 Qwen，可断点续传）。
#
# 用法：powershell -ExecutionPolicy Bypass -File scripts/build_offline_bundle.ps1 [-Lite]
# 产物：dist/2ByteASR-portable-<日期>.7z（完整版，约 9-12 GB）
#       或 dist/2ByteASR-lite-<日期>.7z（精简版，约 300-500 MB；需要 7-Zip）

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDir) { $OutputDir = Join-Path $ProjectRoot "dist" }
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$models = Join-Path $ProjectRoot "models"
$thirdParty = Join-Path $ProjectRoot "third_party"
foreach ($required in @((Join-Path $thirdParty "MOSS-Transcribe-Diarize"), (Join-Path $thirdParty "FireRedASR2S"))) {
    if (-not (Test-Path $required)) {
        throw "缺少打包内容：$required（请先运行 setup_environment.bat）"
    }
}
if (-not $Lite -and -not (Test-Path $models)) {
    throw "缺少打包内容：$models（请先运行 download_models.bat）"
}

# 校验模型完整性（与 download_models.bat -VerifyOnly 相同口径）；精简版不含模型
if (-not $Lite) {
    & (Join-Path $PSScriptRoot "download_models.ps1") -VerifyOnly
    if ($LASTEXITCODE -ne 0) {
        throw "模型完整性校验未通过，请先修复模型再打包。"
    }
}

$sevenZipPath = ""
$sevenZipCommand = Get-Command 7z -ErrorAction SilentlyContinue
if ($sevenZipCommand) { $sevenZipPath = $sevenZipCommand.Source }
if (-not $sevenZipPath) {
    foreach ($candidate in @("C:\Program Files\7-Zip\7z.exe", "C:\Program Files (x86)\7-Zip\7z.exe", "G:\VMWARE\7za.exe")) {
        if (Test-Path $candidate) { $sevenZipPath = $candidate; break }
    }
}
if (-not $sevenZipPath) {
    throw "未找到 7-Zip。请安装（winget install 7zip.7zip）后重试。"
}

# 组装便携目录：程序文件（排除运行环境/缓存/产物）+ models + third_party
$staging = Join-Path $OutputDir "staging-2byteasr"
Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $staging -Force | Out-Null

$excludeDirs = @(
    ".venv-main", ".venv-moss", ".venv", ".uv-python", ".uv-cache",
    "tmp", "dist", "backups", "archive", "outputs", "output", "reports",
    "review_tracks", "__pycache__", ".pytest_cache", ".git", ".mimosa", ".zcode",
    "models", "third_party", "2byteasr.setup-complete"
)
Get-ChildItem $ProjectRoot -Force | Where-Object { $_.Name -notin $excludeDirs } |
    ForEach-Object { Copy-Item $_.FullName (Join-Path $staging $_.Name) -Recurse -Force }
if (-not $Lite) {
    Copy-Item $models (Join-Path $staging "models") -Recurse -Force
}
Copy-Item $thirdParty (Join-Path $staging "third_party") -Recurse -Force
Write-Host "[打包] 便携目录已组装：$staging" -ForegroundColor Cyan


function Invoke-Download {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$OutFile
    )
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -TimeoutSec 300 -ErrorAction Stop
            if ((Get-Item $OutFile).Length -gt 1MB) { return }
            Write-Warning "文件不完整（$Url），重试..."
        } catch {
            Write-Warning "下载失败（$Url）：$($_.Exception.Message)"
        }
        Start-Sleep -Seconds 5
    }
    throw "下载失败：$Url"
}

# 收集内置工具（tools/）：ffmpeg、minGit、Python 安装器、uv —— 便携包免联网安装依赖
$tools = Join-Path $staging "tools"
$tmpDownload = Join-Path $OutputDir "tools-tmp"
New-Item -ItemType Directory -Path $tools -Force | Out-Null
New-Item -ItemType Directory -Path $tmpDownload -Force | Out-Null

# FFmpeg（gyan.dev essentials，含 ffmpeg/ffprobe）
Write-Host "[工具] 下载 FFmpeg ..." -ForegroundColor Cyan
$ffmpegZip = Join-Path $tmpDownload "ffmpeg.zip"
Invoke-Download "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" $ffmpegZip
Expand-Archive $ffmpegZip (Join-Path $tmpDownload "ffmpeg") -Force
$ffBin = Get-ChildItem (Join-Path $tmpDownload "ffmpeg") -Recurse -Directory | Where-Object { $_.Name -eq "bin" } | Select-Object -First 1
if (-not $ffBin) { throw "FFmpeg 解压后未找到 bin 目录。" }
New-Item -ItemType Directory -Path (Join-Path $tools "ffmpeg\bin") -Force | Out-Null
Copy-Item (Join-Path $ffBin.FullName "ffmpeg.exe") (Join-Path $tools "ffmpeg\bin") -Force
Copy-Item (Join-Path $ffBin.FullName "ffprobe.exe") (Join-Path $tools "ffmpeg\bin") -Force

# minGit（Git for Windows 精简便携版，含 git）
Write-Host "[工具] 下载 minGit ..." -ForegroundColor Cyan
$gitZip = Join-Path $tmpDownload "mingit.zip"
Invoke-Download "https://ghfast.top/https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.3/MinGit-2.55.0.3-64-bit.zip" $gitZip
Expand-Archive $gitZip (Join-Path $tools "git") -Force
if (-not (Test-Path (Join-Path $tools "git\cmd\git.exe"))) { throw "minGit 解压后未找到 git.exe。" }

# uv
Write-Host "[工具] 下载 uv ..." -ForegroundColor Cyan
$uvZip = Join-Path $tmpDownload "uv.zip"
Invoke-Download "https://ghfast.top/https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" $uvZip
Expand-Archive $uvZip (Join-Path $tmpDownload "uv") -Force
Copy-Item (Join-Path $tmpDownload "uv\uv.exe") (Join-Path $tools "uv.exe") -Force

# Python 官方安装器（3.10 / 3.12）
foreach ($py in @("3.10.11", "3.12.10")) {
    Write-Host "[工具] 下载 Python $py 安装器 ..." -ForegroundColor Cyan
    $pyInstaller = Join-Path $tools "python-$py-amd64.exe"
    $ok = $false
    foreach ($url in @(
        "https://www.python.org/ftp/python/$py/python-$py-amd64.exe",
        "https://mirrors.huaweicloud.com/python/$py/python-$py-amd64.exe"
    )) {
        try { Invoke-Download $url $pyInstaller; $ok = $true; break } catch { Write-Warning "Python $py 下载失败（$url），尝试镜像..." }
    }
    if (-not $ok) { throw "Python $py 安装器下载失败。" }
}

Remove-Item $tmpDownload -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "[工具] 内置工具收集完成：$tools" -ForegroundColor Green

$stamp = Get-Date -Format "yyyyMMdd"
$baseName = if ($Lite) { "2ByteASR-lite" } else { "2ByteASR-portable" }
$output = Join-Path $OutputDir "$baseName-$stamp.7z"
Remove-Item $output -Force -ErrorAction SilentlyContinue
$label = if ($Lite) { "精简版（不含模型，约 300-500 MB）" } else { "完整版（约 9-12 GB）" }
Write-Host "[打包] 正在压缩（$label，可能需要一段时间）..." -ForegroundColor Cyan
$logOut = Join-Path $OutputDir "portable-bundle.log"
$logErr = Join-Path $OutputDir "portable-bundle.err.log"
$p = Start-Process -FilePath $sevenZipPath -ArgumentList @(
    "a", "-t7z", "-mx=1", "-mmt=on", $output, (Join-Path $staging "*")
) -Wait -PassThru -NoNewWindow -RedirectStandardOutput $logOut -RedirectStandardError $logErr
if ($p.ExitCode -ne 0) {
    $tail = ""
    if (Test-Path $logErr) { $tail = "`n" + ((Get-Content $logErr -Tail 10) -join "`n") }
    throw "7-Zip 打包失败（退出码 $($p.ExitCode)）。$tail"
}
Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $logOut, $logErr -Force -ErrorAction SilentlyContinue

Write-Host "[OK] 便携包已生成：$output" -ForegroundColor Green
if ($Lite) {
    Write-Host "用法：解压到任意目录，双击 setup_2byteasr.bat —— 内置 git/ffmpeg/python/uv 无需联网安装，模型会自动下载（约 7 GB，可续传）。" -ForegroundColor Yellow
} else {
    Write-Host "用法：解压到任意目录（如 D:\2ByteASR），双击 setup_2byteasr.bat 完成环境配置后即可使用。" -ForegroundColor Yellow
}
