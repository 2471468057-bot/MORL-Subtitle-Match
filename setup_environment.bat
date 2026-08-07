@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\setup_environment.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" echo.
if not "%EXIT_CODE%"=="0" echo [Error] Environment setup did not finish. Review the message above.
pause
exit /b %EXIT_CODE%
