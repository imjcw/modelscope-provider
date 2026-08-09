@echo off
:: start.bat — 启动 AI Provider 服务
:: 用法: start.bat
:: 可通过环境变量覆盖: set HOST=127.0.0.1 && start.bat
:: 托盘版（--noconsole 打包）直接双击 .exe 即可，无需此脚本。

cd /d "%~dp0"

if "%HOST%"=="" set HOST=0.0.0.0
if "%PORT%"=="" set PORT=8000

echo.
echo >>> 启动 AI Provider...
echo     地址: http://%HOST%:%PORT%
echo     文档: http://%HOST%:%PORT%/docs
echo.

python run.py
