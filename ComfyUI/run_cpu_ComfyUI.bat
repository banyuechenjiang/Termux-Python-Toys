@echo off
title ComfyUI

:: 1. 强制清除代理设置 (解决 ProxyError 的核心)
set HTTP_PROXY=
set HTTPS_PROXY=
set ALL_PROXY=

:: 2. 设置路径
set "TARGET_DIR=%~dp0"
cd /d "%TARGET_DIR%"

:: 3. 激活环境
call "venv\Scripts\activate.bat"

:: 4. 启动 ComfyUI (添加参数跳过某些自动安装)
:: --cpu: 强制CPU
:: --disable-auto-launch: 防止自动打开浏览器卡顿
echo ===================================================
echo   正在启动... (已屏蔽自动更新和代理)
echo ===================================================
python main.py --cpu --disable-auto-launch

pause