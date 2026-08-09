[CmdletBinding()]
param()

# 生成 hotfix 覆盖包：已发布便携包的用户解压覆盖即可获得修复，
# 无需重新下载 1GB/10GB 整包。文件清单随版本维护，此处即唯一真源。
#
# 用法：powershell -ExecutionPolicy Bypass -File scripts/build_hotfix.ps1
# 产物：dist/2ByteASR-hotfix-<日期>.zip + .sha256

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$OutputDir = Join-Path $ProjectRoot "dist"
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$stamp = Get-Date -Format "yyyyMMdd"
$output = Join-Path $OutputDir "2ByteASR-hotfix-$stamp.zip"

# 覆盖包文件清单：只放修复/演进所需的最小集合。
# 原则：不包含 models/、.venv*、tools/、wheels/ 等大件；
# 新增修复文件时在这里登记，并同步更新 README 的 hotfix 说明。
$files = @(
    "2ByteASR.exe",
    "quick_start.py",
    "subtitle_core.py",
    "setup_2byteasr.bat",
    "scripts\bootstrap_install.ps1",
    "scripts\setup_environment.ps1",
    "scripts\download_models.ps1",
    "twobyteasr\ui.py",
    "twobyteasr\i18n.py",
    "twobyteasr\settings.py",
    "twobyteasr\model_integrity.py",
    "assets\ui-chevron-down.png"
)

$missing = @($files | Where-Object { -not (Test-Path (Join-Path $ProjectRoot $_)) })
if ($missing.Count -gt 0) {
    throw "hotfix 清单中的文件缺失：$($missing -join ', ')"
}

$sevenZipPath = ""
$sevenZipCommand = Get-Command 7z -ErrorAction SilentlyContinue
if ($sevenZipCommand) { $sevenZipPath = $sevenZipCommand.Source }
if (-not $sevenZipPath -and $env:SEVENZIP_PATH -and (Test-Path $env:SEVENZIP_PATH)) {
    $sevenZipPath = $env:SEVENZIP_PATH
}
if (-not $sevenZipPath) {
    foreach ($candidate in @("C:\Program Files\7-Zip\7z.exe", "C:\Program Files (x86)\7-Zip\7z.exe")) {
        if (Test-Path $candidate) { $sevenZipPath = $candidate; break }
    }
}
if (-not $sevenZipPath) {
    throw "未找到 7-Zip（winget install 7zip.7zip）或设置 SEVENZIP_PATH。"
}

Remove-Item $output -Force -ErrorAction SilentlyContinue
$zipArgs = @("a", "-tzip", $output) + $files
& $sevenZipPath @zipArgs | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "hotfix 打包失败（退出码 $LASTEXITCODE）。"
}

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $output).Hash
$checksumPath = "$output.sha256"
"$($hash.ToLowerInvariant())  $([IO.Path]::GetFileName($output))" | Set-Content -Encoding ascii $checksumPath
Write-Host "[OK] $output" -ForegroundColor Green
Write-Host "SHA256 $hash"
Write-Host "用法：解压后覆盖到便携版根目录即可（文件清单见本脚本头部）。" -ForegroundColor Yellow
