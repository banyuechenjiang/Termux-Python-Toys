@echo off

REM --- 配置 ---
REM 设置 Python 脚本的名称 (假设此批处理文件与 Python 脚本在同一目录)
set SCRIPT_NAME=zTasker.py

REM 设置 Python 解释器的路径 (如果 'python' 命令不在系统 PATH 中，或者您想指定特定的 Python 版本)
REM 如果 'python' 已经在 PATH 中，可以将下一行注释掉 (前面加 REM) 或留空
REM set PYTHON_COMMAND=python 
if defined PYTHON_EXE set PYTHON_COMMAND=%PYTHON_EXE%

REM --- 检查管理员权限并尝试提升 ---
REM 使用 fsutil dirty query 来检查权限，这是一个比较可靠且不需要外部工具的方法
fsutil dirty query %systemdrive% >nul 2>&1

if %errorlevel% NEQ 0 (
    echo Requesting administrative privileges to run %SCRIPT_NAME%...
    REM 使用 PowerShell 以管理员身份重新启动此批处理文件
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

REM --- 如果已经有管理员权限，则执行 Python 脚本 ---
echo Running Python script with admin privileges: %SCRIPT_NAME%
echo Script location: %~dp0

REM 切换到脚本所在目录 (确保脚本中的相对路径正确工作)
cd /d "%~dp0"

REM 执行 Python 脚本
%PYTHON_COMMAND% "%SCRIPT_NAME%"

REM 可选：运行后暂停，以便查看输出和错误信息
echo.
echo Script execution finished. Press any key to close this window.
pause >nul