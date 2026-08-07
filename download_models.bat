@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\download_models.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" echo.
if not "%EXIT_CODE%"=="0" echo [Error] Model download or verification did not finish. Review the message above.
pause
exit /b %EXIT_CODE%
