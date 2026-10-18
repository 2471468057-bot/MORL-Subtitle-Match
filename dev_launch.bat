@echo off
setlocal
set "ROOT=%~dp0"

rem Source-mode launcher for 2ByteASR (TuBai subtitle studio).
rem Runs on the managed main runtime (torch+CUDA) so the recognition
rem preflight passes without a second interpreter hop. GUI deps
rem (PySide6/qtawesome/etc.) were installed into that runtime too.
rem User data is redirected to the project _userdata folder.

set "LOCALAPPDATA=%ROOT%_userdata"
if not exist "%LOCALAPPDATA%" mkdir "%LOCALAPPDATA%"

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "TWOBYTEASR_LAUNCH_MODE=source-dev"
set "PATH=%ROOT%tools\ffmpeg\bin;%PATH%"

set "MPY=%LOCALAPPDATA%\2ByteASR\runtimes\main"
for /d %%D in ("%MPY%\*") do set "MPY=%%D"
set "MPYW=%MPY%\Scripts\pythonw.exe"
if not exist "%MPYW%" set "MPYW=%MPY%\Scripts\python.exe"

cd /d "%ROOT%"
"%MPYW%" quick_start.py %*

echo.
echo Exit code: %ERRORLEVEL%
endlocal