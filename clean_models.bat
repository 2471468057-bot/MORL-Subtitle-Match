@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"

echo ============================================
echo  2ByteASR 模型缓存清理
echo ============================================
echo.
echo 将删除 models\ 下的 HuggingFace 下载缓存（.cache）与模型登记文件，
echo 保留已下载的模型文件本身。下次校验会重新登记，不会触发重复下载。
echo.
set /p CONFIRM=确认清理缓存？[y/N]（回车取消）: 
if /i not "%CONFIRM%"=="y" (
  echo 已取消。
  exit /b 0
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root='%ROOT%models'; if (Test-Path $root) { Get-ChildItem $root -Recurse -Directory -Filter .cache -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force; Remove-Item (Join-Path $root '.twobyteasr-models.json') -Force -ErrorAction SilentlyContinue; Write-Host '[完成] 模型缓存已清理。' } else { Write-Host '[提示] models 目录不存在，无需清理。' }"
echo.
echo 重新运行 download_models.bat 即可校验/补全模型。
pause
exit /b 0
