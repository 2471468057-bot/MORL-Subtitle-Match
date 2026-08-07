@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\bootstrap_install.ps1" -InstallPrerequisites -DownloadModels
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo [完成] 2ByteASR 已安装并准备就绪。
) else (
  echo [失败] 首次配置没有完成。修复上方提示后可重新运行 setup_2byteasr.bat。
)
pause
exit /b %EXIT_CODE%
