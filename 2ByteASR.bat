@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
set "PYW=%ROOT%.venv-main\Scripts\pythonw.exe"
set "LAUNCHER=%ROOT%2ByteASR.exe"

if exist "%LAUNCHER%" (
  start "2ByteASR" "%LAUNCHER%" %*
  exit /b 0
)

if not exist "%PYW%" (
  echo [启动失败] 缺少固定主环境：.venv-main
  echo            请先运行 setup_environment.bat
  pause
  exit /b 1
)

start "2ByteASR" "%PYW%" "%ROOT%quick_start.py" %*
exit /b 0
