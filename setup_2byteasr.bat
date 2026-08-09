@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\bootstrap_install.ps1" -InstallPrerequisites -DownloadModels
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if "%EXIT_CODE%"=="0" (
  echo [完成] 2ByteASR 已安装并准备就绪。
  rem 由 2ByteASR.exe 启动器触发的成功配置不等待按键
  if "%2BYTEASR_NO_PAUSE%"=="1" goto :done
  pause
  goto :done
)
echo [失败] 首次配置没有完成。修复上方提示后可重新运行 setup_2byteasr.bat。
echo.
echo 完整安装日志：%TEMP%\2byteasr-setup.log
echo 请把上面的红色错误信息或日志内容发给开发者排查。
echo.
rem 失败时无论如何都停住，防止窗口一闪而过看不到错误
pause
:done
exit /b %EXIT_CODE%
