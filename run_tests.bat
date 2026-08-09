@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if "%DASHSCOPE_API_KEY%"=="" set DASHSCOPE_API_KEY=sk-local-test-dummy
set "ROOT=%~dp0"
set "PYTHON_EXE=python"
if exist "%ROOT%.venv-main\Scripts\python.exe" set "PYTHON_EXE=%ROOT%.venv-main\Scripts\python.exe"
"%PYTHON_EXE%" -m py_compile auto_asr.py moss_firered_pipeline.py subtitle_core.py moss_worker.py firered_llm_worker.py register_host_voiceprint.py
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" -m compileall -q twobyteasr
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" -m pytest -q tests
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" scripts\check_release_hygiene.py
exit /b %ERRORLEVEL%
