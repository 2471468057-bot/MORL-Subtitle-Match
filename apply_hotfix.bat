@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
set "ZIP=%~1"

if "%ZIP%"=="" (
  for %%f in ("%ROOT%2ByteASR-hotfix-*.zip") do set "ZIP=%%f"
)
if "%ZIP%"=="" (
  echo [失败] 未找到 hotfix 压缩包。请把 2ByteASR-hotfix-*.zip 放到本目录后重试，
  echo        或把 zip 文件拖到本脚本上运行。
  pause
  exit /b 1
)

echo 正在应用 hotfix：%ZIP%
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; $root='%ROOT%'; $zip='%ZIP%';" ^
  "$tmp=Join-Path $env:TEMP ('2byteasr-hotfix-apply-' + [guid]::NewGuid().ToString('N'));" ^
  "New-Item -ItemType Directory -Path $tmp -Force | Out-Null;" ^
  "Expand-Archive -Path $zip -DestinationPath $tmp -Force;" ^
  "$m = Get-Content (Join-Path $tmp 'HOTFIX.json') -Raw | ConvertFrom-Json;" ^
  "foreach ($f in $m.files) { $src=Join-Path $tmp $f; $dst=Join-Path $root $f; if (Test-Path $src) { New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null; Copy-Item $src $dst -Force } };" ^
  "foreach ($f in $m.delete) { Remove-Item (Join-Path $root $f) -Force -ErrorAction SilentlyContinue };" ^
  "Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue;" ^
  "Write-Host '[完成] hotfix 已应用，共 ' $m.files.Count ' 个文件。'"
if errorlevel 1 (
  echo.
  echo [失败] hotfix 应用失败，请检查上方错误信息。
  pause
  exit /b 1
)
echo.
echo 应用完成，现在可以正常启动 2ByteASR 了。
pause
exit /b 0
