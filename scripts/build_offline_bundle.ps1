[CmdletBinding()]
param(
    [string]$OutputDir = ""
)

# 打包离线素材包：models/（约 11 GB 模型）+ third_party/（固定版本源码）。
# 适合国内网络不稳定、在线下载困难的环境：解压到安装目录后，
# setup_2byteasr.bat 会检测到已有模型与源码并跳过下载。
#
# 用法：powershell -ExecutionPolicy Bypass -File scripts/build_offline_bundle.ps1
# 产物：dist/2ByteASR-offline-models-<日期>.7z（需要 7-Zip）

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

$stamp = Get-Date -Format "yyyyMMdd"
$output = Join-Path $OutputDir "2ByteASR-offline-models-$stamp.7z"
Remove-Item $output -Force -ErrorAction SilentlyContinue
Write-Host "[打包] 正在压缩 models 与 third_party（约 12 GB，可能需要一段时间）..." -ForegroundColor Cyan
& $sevenZipPath a -t7z -mx=1 -mmt=on $output `
    (Join-Path $ProjectRoot "models\*") (Join-Path $ProjectRoot "third_party\*")
if ($LASTEXITCODE -ne 0) {
    throw "7-Zip 打包失败（退出码 $LASTEXITCODE）。"
}

Write-Host "[OK] 离线包已生成：$output" -ForegroundColor Green
Write-Host "使用方式：解压到 2ByteASR 安装目录（覆盖 models/ 与 third_party/），再运行 setup_2byteasr.bat 完成环境配置。" -ForegroundColor Yellow
