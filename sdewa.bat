@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set "ROOT=%~dp0"
set "MAIN_PY=%ROOT%.venv-main\Scripts\python.exe"
set "MAIN_PYW=%ROOT%.venv-main\Scripts\pythonw.exe"

if not exist "%MAIN_PY%" (
  echo [启动失败] 缺少固定主环境：.venv-main
  echo            请先运行 setup_environment.bat
  pause
  exit /b 1
)

"%MAIN_PY%" -m twobyteasr.preflight
if errorlevel 1 (
  echo.
  echo [启动已停止] 请按上面的处理提示修复后重试。
  pause
  exit /b 1
)

if /I "%~1"=="--console" (
  "%MAIN_PY%" "%ROOT%auto_asr.py"
  set "EXIT_CODE=%ERRORLEVEL%"
  pause
  exit /b %EXIT_CODE%
)

if not exist "%MAIN_PYW%" (
  echo [启动失败] 主环境缺少 pythonw.exe，请重新运行 setup_environment.bat
  pause
  exit /b 1
)

start "2ByteASR" "%MAIN_PYW%" "%ROOT%auto_asr.py"
exit /b 0
