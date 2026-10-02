@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\download_models.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo [FAILED] Model download or verification did not complete. Fix the error above and try again.
  echo Full setup log: %TEMP%\2byteasr-setup.log
  pause
)
exit /b %EXIT_CODE%
