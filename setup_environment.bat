@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\setup_environment.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo [失败] 环境配置没有完成，请根据上方提示修复后重试。
  echo        完整日志：%TEMP%\2byteasr-setup.log
  pause
)
exit /b %EXIT_CODE%
