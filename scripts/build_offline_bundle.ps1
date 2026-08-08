[CmdletBinding()]
param(
    [string]$OutputDir = ""
)

# 打包便携版 2ByteASR：程序文件 + models/（模型）+ third_party/（固定版本源码）。
# 解压到任意目录即可作为完整程序使用（首次运行 setup_2byteasr.bat 安装 Python 环境）。
# 适合国内网络下载模型困难的环境：一次性下载，解压即用。
#
# 用法：powershell -ExecutionPolicy Bypass -File scripts/build_offline_bundle.ps1
# 产物：dist/2ByteASR-portable-<日期>.7z（约 9-12 GB，需要 7-Zip）

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDir) { $OutputDir = Join-Path $ProjectRoot "dist" }
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$models = Join-Path $ProjectRoot "models"
$thirdParty = Join-Path $ProjectRoot "third_party"
foreach ($required in @($models, (Join-Path $thirdParty "MOSS-Transcribe-Diarize"), (Join-Path $thirdParty "FireRedASR2S"))) {
    if (-not (Test-Path $required)) {
        throw "缺少打包内容：$required（请先运行 setup_environment.bat 与 download_models.bat）"
    }
}

# 校验模型完整性（与 download_models.bat -VerifyOnly 相同口径）
& (Join-Path $PSScriptRoot "download_models.ps1") -VerifyOnly
if ($LASTEXITCODE -ne 0) {
    throw "模型完整性校验未通过，请先修复模型再打包。"
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
    "models", "third_party"
)
Get-ChildItem $ProjectRoot -Force | Where-Object { $_.Name -notin $excludeDirs } |
    ForEach-Object { Copy-Item $_.FullName (Join-Path $staging $_.Name) -Recurse -Force }
Copy-Item $models (Join-Path $staging "models") -Recurse -Force
Copy-Item $thirdParty (Join-Path $staging "third_party") -Recurse -Force
Write-Host "[打包] 便携目录已组装：$staging" -ForegroundColor Cyan

$stamp = Get-Date -Format "yyyyMMdd"
$output = Join-Path $OutputDir "2ByteASR-portable-$stamp.7z"
Remove-Item $output -Force -ErrorAction SilentlyContinue
Write-Host "[打包] 正在压缩（约 9-12 GB，可能需要一段时间）..." -ForegroundColor Cyan
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
Write-Host "用法：解压到任意目录（如 D:\2ByteASR），双击 setup_2byteasr.bat 完成环境配置后即可使用。" -ForegroundColor Yellow
