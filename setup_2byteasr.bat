@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"

if exist "%ROOT%2ByteASR-Configure.exe" (
  start "" "%ROOT%2ByteASR-Configure.exe"
  exit /b 0
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\bootstrap_install.ps1" -InstallPrerequisites -DownloadModels
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo [OK] 2ByteASR installation and configuration completed.
  rem A launcher-triggered successful setup should not wait for a key press.
  if "%2BYTEASR_NO_PAUSE%"=="1" goto :done
  pause
  goto :done
)
echo [FAILED] Initial configuration did not complete. Fix the error above and run setup_2byteasr.bat again.
echo.
echo Full setup log: %TEMP%\2byteasr-setup.log
echo Python installer logs: %TEMP%\2byteasr-python-*-install.log
echo Please send the error or the relevant log to the developer for diagnosis.
echo.
rem Always pause after failure, even when launched by the Setup installer.
pause
:done
exit /b %EXIT_CODE%
