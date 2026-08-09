@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\download_models.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo [失败] 模型下载或校验没有完成，请根据上方提示修复后重试。
  echo        完整日志：%TEMP%\2byteasr-setup.log
  pause
)
exit /b %EXIT_CODE%
