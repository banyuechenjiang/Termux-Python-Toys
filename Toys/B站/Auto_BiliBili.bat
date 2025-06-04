@echo off
chcp 65001 >nul

REM --- 配置 ---
set SCRIPT_NAME=BiliBili-B站日常任务脚本.py
set PYTHON_COMMAND=python 
if defined PYTHON_EXE set PYTHON_COMMAND=%PYTHON_EXE%

REM --- 确保此批处理文件和脚本在同一目录 ---
REM 如果不确定，可以取消注释下一行来设置绝对路径
REM set SCRIPT_FULL_PATH="C:\your\path\to\BiliBili-B站日常任务脚本.py"

REM --- 切换到脚本所在目录 ---
cd /d "%~dp0"

echo.
echo ==========================================================
echo            BiliBili 自动化日常任务脚本启动器
echo ==========================================================
echo.
echo 准备执行脚本: %SCRIPT_NAME%
echo 脚本位置: %~dp0
echo 使用Python: %PYTHON_COMMAND%
echo.

REM --- 执行 Python 脚本并传入 --auto 参数 ---
echo 正在以自动化模式 (--auto) 运行脚本...
echo.
if defined SCRIPT_FULL_PATH (
    %PYTHON_COMMAND% "%SCRIPT_FULL_PATH%" --auto
) else (
    %PYTHON_COMMAND% "%SCRIPT_NAME%" --auto
)

echo.
echo ==========================================================
echo 脚本执行完毕。
echo ==========================================================
echo.

REM --- 可选：如果需要在任务计划程序中运行时，脚本执行后不暂停 ---
REM --- 如果手动运行此bat文件，并希望看到输出，可以取消注释下一行 ---
REM pause