#!/bin/bash

# ==============================================================================
#
#          macOS Homebrew & Cork 自动化安装脚本
#
#   功能:
#   1. 检查并安装 Homebrew (macOS 的包管理器)。
#   2. 使用 Homebrew 安装 Cork (一个 Homebrew 的图形化前端)。
#   3. 脚本可重复运行，会自动跳过已完成的步骤。
#
#   使用方法:
#   1. 保存此脚本为 install_cork_suite.sh
#   2. 在终端中给予执行权限: chmod +x install_cork_suite.sh
#   3. 运行脚本: ./install_cork_suite.sh
#
# ==============================================================================

# --- 定义颜色用于输出 ---
# 使用tput来确保颜色兼容性
if tput setaf 1 >/dev/null 2>&1; then
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    BLUE=$(tput setaf 4)
    BOLD=$(tput bold)
    NC=$(tput sgr0) # No Color
else
    # 如果tput不可用，则不使用颜色
    GREEN=""
    YELLOW=""
    BLUE=""
    BOLD=""
    NC=""
fi

# --- 辅助函数 ---
function info() {
    echo "${BOLD}${BLUE}==>${NC}${BOLD} $1${NC}"
}

function success() {
    echo "${BOLD}${GREEN}==>${NC}${BOLD} $1${NC}"
}

function warn() {
    echo "${BOLD}${YELLOW}==>${NC}${BOLD} $1${NC}"
}

# --- 核心功能 ---

# 步骤 1: 安装 Homebrew
function install_homebrew() {
    info "正在检查 Homebrew..."
    # 使用 `command -v` 来检查 'brew' 命令是否存在
    if command -v brew >/dev/null 2>&1; then
        success "Homebrew 已经安装。跳过安装步骤。"
        info "正在更新 Homebrew，这可能需要一些时间..."
        brew update
    else
        warn "未找到 Homebrew。现在开始安装..."
        info "Homebrew 安装程序即将运行。"
        warn "您可能需要按 “回车” 键，并输入您的 Mac 登录密码。"
        
        # 运行官方的非交互式安装命令
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # 检查安装是否成功
        if [ $? -ne 0 ]; then
            echo "${BOLD}Homebrew 安装失败。请检查网络连接或查看上面的错误信息。${NC}"
            exit 1
        fi

        # 根据CPU架构配置环境变量
        info "正在配置 Homebrew 环境变量..."
        if [[ "$(uname -m)" == "arm64" ]]; then
            # Apple Silicon (M1/M2/M3...)
            BREW_PATH="/opt/homebrew/bin/brew"
        else
            # Intel
            BREW_PATH="/usr/local/bin/brew"
        fi
        
        # 将 shellenv 添加到 .zprofile 并应用到当前会话
        (echo; echo "eval \"\$($BREW_PATH shellenv)\"") >> ~/.zprofile
        eval "$($BREW_PATH shellenv)"
        
        success "Homebrew 安装并配置成功！"
    fi
    # 验证一下
    brew --version
}

# 步骤 2: 安装 Cork
function install_cork() {
    info "正在检查 Cork..."
    # 使用 `brew list` 检查 Cork 是否已安装
    if brew list --cask cork >/dev/null 2>&1; then
        success "Cork 已经安装。"
    else
        warn "未找到 Cork。现在开始安装..."
        info "正在使用 Homebrew 安装 Cork..."
        brew install --cask cork

        if [ $? -eq 0 ]; then
            success "Cork 安装成功！"
        else
            echo "${BOLD}Cork 安装失败。请尝试手动运行 'brew install --cask cork' 来排查问题。${NC}"
            exit 1
        fi
    fi
}

# --- 主函数 ---
function main() {
    echo "============================================="
    echo "     macOS Homebrew & Cork 自动化安装      "
    echo "============================================="
    echo ""
    
    # 运行步骤
    install_homebrew
    echo ""
    install_cork
    echo ""

    # 完成提示
    success "所有操作已完成！"
    info "您现在可以从“应用程序”文件夹或通过 Spotlight 搜索来启动 Cork。"
    info "享受您的新包管理器吧！"
    echo ""
}

# --- 启动脚本 ---
main