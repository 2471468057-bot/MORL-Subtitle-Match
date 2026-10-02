@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\setup_environment.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo [FAILED] Environment setup did not complete. Fix the error above and try again.
  echo Full setup log: %TEMP%\2byteasr-setup.log
  echo Python installer logs: %TEMP%\2byteasr-python-*-install.log
  pause
)
exit /b %EXIT_CODE%
