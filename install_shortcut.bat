@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\install_shortcut.ps1"
if errorlevel 1 (
  echo.
  echo [失败] 任务栏启动入口没有安装完成。
  pause
  exit /b 1
)

echo.
echo [完成] 现在可以从桌面快捷方式启动，并将它固定到任务栏。
pause
exit /b 0
