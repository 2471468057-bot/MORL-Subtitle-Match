@echo off
chcp 65001 >nul
echo [Info] This compatibility entry now installs environments only.
echo        Model weights are downloaded separately by download_models.bat.
echo.
call "%~dp0setup_environment.bat" %*
exit /b %ERRORLEVEL%
