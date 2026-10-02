@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if "%DASHSCOPE_API_KEY%"=="" set DASHSCOPE_API_KEY=sk-local-test-dummy
set "ROOT=%~dp0"
set "PYTHON_EXE=python"
if exist "%ROOT%.venv-main\Scripts\python.exe" set "PYTHON_EXE=%ROOT%.venv-main\Scripts\python.exe"
"%PYTHON_EXE%" scripts\run_test_suite.py %*
exit /b %ERRORLEVEL%
