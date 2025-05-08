@echo off
::后续命令使用的是：UTF-8编码
chcp 65001

:: 启用 BypassCertificatePinningForMicrosoftStore 设置（允许绕过Microsoft Store的证书固定）
echo 正在启用 BypassCertificatePinningForMicrosoftStore 设置...
winget settings --enable BypassCertificatePinningForMicrosoftStore
echo 设置已启用。

:: 移除默认的 winget 源并添加中科大镜像源
echo 正在移除默认的 winget 源...
winget source remove winget
echo 正在添加中科大镜像源...
winget source add winget https://mirrors.ustc.edu.cn/winget-source
echo 正在更新 winget 源...
winget source update
echo 源配置已完成。

:: 从winget 源 安装常用软件
echo 正在安装 7-Zip-zstd (支持Zstandard压缩的7-Zip版本)...
winget install mcmilk.7zip-zstd -s winget

echo 正在安装 qBittorrent Enhanced Edition (增强版qBittorrent)...
winget install c0re100.qBittorrent-Enhanced-Edition -s winget

echo 正在安装 Google Chrome 浏览器...
winget install Google.Chrome -s winget

echo 正在安装 Clash Verge Rev 和 Mihomo-Party...
winget install ClashVergeRev.ClashVergeRev Mihomo-Party -s winget

echo 正在安装 Telegram Desktop...
winget install Telegram.TelegramDesktop -s winget

echo 正在安装 zTasker (定时任务管理工具)...
winget install everauto.zTasker -s winget

echo 正在安装 Anki (记忆卡片软件)...
winget install Anki.Anki -s winget

:: 开发环境相关
echo 正在安装 Visual Studio Code...
winget install Microsoft.VisualStudioCode -s winget

echo 正在安装 Git...
winget install Git.Git -s winget

echo 正在安装 Python 3.13...
winget install Python.Python.3.13 -s winget

echo 正在安装 Node.js LTS 版本...
winget install OpenJS.NodeJS.LTS -s winget

echo 所有操作已完成。
pause