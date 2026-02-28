@echo off
setlocal

:: =================================================================
:: ==  ComfyUI 本地工作流环境部署脚本 (CPU-Only)              ==
:: =================================================================
:: ==  目标: 创建一个约2GB的轻量化环境，仅用于编辑工作流；由gemini3pro制作，个人测试使用      ==
:: =================================================================

title ComfyUI CPU 环境部署

:: --- 步骤 0: 环境检查 ---
echo [INFO] 正在检查 Git 和 Python 环境...
where git >nul 2>nul || (echo [ERROR] 未找到 Git，请先安装并配置好 PATH。 & pause & exit /b)
where python >nul 2>nul || (echo [ERROR] 未找到 Python，请先安装并配置好 PATH。 & pause & exit /b)
echo [SUCCESS] 环境检查通过。

:: --- 步骤 1: 克隆核心仓库 ---
if not exist "ComfyUI" (
    echo [INFO] 正在克隆 ComfyUI 主仓库...
    git clone https://github.com/comfyanonymous/ComfyUI.git || (echo [ERROR] ComfyUI 克隆失败。 & pause & exit /b)
) else (
    echo [INFO] ComfyUI 已存在，执行更新...
    cd ComfyUI && git pull && cd ..
)

if not exist "ComfyUI\custom_nodes\ComfyUI-Manager" (
    echo [INFO] 正在克隆 ComfyUI-Manager...
    cd ComfyUI\custom_nodes
    git clone https://github.com/ltdrdata/ComfyUI-Manager.git || (echo [ERROR] ComfyUI-Manager 克隆失败。 & pause & exit /b)
    cd ..\..
) else (
    echo [INFO] ComfyUI-Manager 已存在，执行更新...
    cd ComfyUI\custom_nodes\ComfyUI-Manager && git pull && cd ..\..\..
)

cd ComfyUI

:: --- 步骤 2: 创建虚拟环境并安装依赖 ---
if not exist "venv" (
    echo [INFO] 正在创建 Python 虚拟环境...
    python -m venv venv || (echo [ERROR] 创建虚拟环境失败。 & pause & exit /b)
)

echo [INFO] 激活虚拟环境并安装依赖 (这可能需要几分钟)...
call venv\Scripts\activate.bat

echo [INFO] 1/3 - 安装纯CPU版 PyTorch 以节省空间...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

echo [INFO] 2/3 - 安装 ComfyUI 主依赖...
pip install -r requirements.txt

echo [INFO] 3/3 - 安装 ComfyUI-Manager 依赖...
pip install -r custom_nodes\ComfyUI-Manager\requirements.txt

:: --- 步骤 3: 辅助了解配置文件和启动器的路径 ---

echo [INFO] 正在生成 Manager 配置文件 (config.ini)...
(
    echo [default]
    echo preview_method = none
    echo use_uv = True
    echo network_mode = private
    echo model_download_by_agent = False
    echo update_policy = stable-comfyui
    echo bypass_ssl = False
) > "user\__manager\config.ini"

echo [INFO] 正在生成 CPU 模式启动器 (run_cpu_ComfyUI.bat)...
(
    echo @echo off
    echo title ComfyUI (CPU Workflow Mode)
    echo cd /d "%%~dp0"
    echo call "venv\Scripts\activate.bat"
    echo echo Starting ComfyUI in CPU mode...
    echo python main.py --cpu
    echo pause
) > "run_cpu_ComfyUI.bat"

echo.
echo =================================================================
echo [SUCCESS] 部署完成！
echo.
echo - 占用空间: 约 2 GB
echo - 启动方式: 请进入 ComfyUI 文件夹，双击 "run_cpu_ComfyUI.bat"
echo =================================================================
echo.
pause