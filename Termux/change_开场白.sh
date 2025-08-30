#!/data/data/com/termux/files/usr/bin/bash

# ==============================================================================
# 脚本名称: change_motd.sh
# 功能描述: 用于方便地更改 Termux 的静态启动欢迎语 (MOTD)。
# 作者: Termux 专家 AI
# 版本: 3.0
# 更新日志:
# v3.0: 增加颜色、健壮性检查、自定义内容功能，并优化代码结构。
# v2.3: 修复了 heredoc 导致的 ASCII art 显示错误。
# ==============================================================================

# --- 配置与定义 ---

# 定义 ANSI 颜色常量，使终端输出更美观、更具可读性。
# 使用 echo -e "${C_GREEN}一些文本${C_RESET}" 来输出带颜色的文本。
C_RESET='\033[0m'       # 重置所有格式
C_RED='\033[0;31m'       # 红色，通常用于错误
C_GREEN='\033[0;32m'     # 绿色，通常用于成功
C_YELLOW='\033[0;33m'    # 黄色，通常用于警告
C_BLUE='\033[0;34m'      # 蓝色，通常用于信息
C_CYAN='\033[0;36m'      # 青色，用于界面元素
C_WHITE='\033[1;37m'     # 白色，用于标题

# 定义 MOTD 文件的绝对路径。使用 $PREFIX 变量使其具有更好的移植性。
MOTD_FILE="$PREFIX/etc/motd"


# --- 核心功能函数 ---

# 函数: 设置 Termux 字符画 Logo
set_termux_logo() {
    # 关键修复：这里的 'EOF' 使用了单引号。
    # 这会告诉 Shell 将 EOF 之间的所有内容视为纯文本，不做任何变量替换或转义，
    # 从而完美地保留 ASCII 字符画中的所有特殊字符（如 `\` 和 ` ` `）。
    cat > "$MOTD_FILE" << 'EOF'
 _____
|_   _|__ _ __ _ __ ___  _   ___  __
  | |/ _ \ '__| '_ ` _ \| | | \ \/ /
  | |  __/ |  | | | | | | |_| |>  <
  |_|\___|_|  |_| |_| |_|\__,_/_/\_\
EOF
    echo -e "${C_GREEN}✅ 启动问候语已更新为 [Termux Logo]。${C_RESET}"
}

# 函数: 设置 Touhou Project 字符画 Logo
set_touhou_logo() {
    # 同样使用 'EOF' 来保护字符画的完整性。
    cat > "$MOTD_FILE" << 'EOF'
  ______            __                   ____               _           __
 /_  __/___  __  __/ /_  ____  __  __   / __ \_________    (_)__  _____/ /_
  / / / __ \/ / / / __ \/ __ \/ / / /  / /_/ / ___/ __ \  / / _ \/ ___/ __/
 / / / /_/ / /_/ / / / / /_/ / /_/ /  / ____/ /  / /_/ / / /  __/ /__/ /_
/_/  \____/\__,_/_/ /_/\____/\__,_/  /_/   /_/   \____/_/ /\___/\___/\__/
                                                     /___/
EOF
    echo -e "${C_GREEN}✅ 启动问候语已更新为 [Touhou Project Logo]。${C_RESET}"
}

# 函数: 设置 LilyWhite 文字 Logo
set_lilywhite_logo() {
    cat > "$MOTD_FILE" << 'EOF'
    __    _ __     _       ____    _ __
   / /   (_) /_  _| |     / / /_  (_) /____
  / /   / / / / / / | /| / / __ \/ / __/ _ \
 / /___/ / / /_/ /| |/ |/ / / / / / /_/  __/
/_____/_/_/\__, / |__/|__/_/ /_/_/\__/\___/
          /____/
EOF
    echo -e "${C_GREEN}✅ 启动问候语已更新为 [LilyWhite Logo]。${C_RESET}"
}

# 函数: 设置 ASCII Art 生成网站链接
set_website_link() {
    # 注意：这里我们故意使用没有引号的 EOF。
    # 因为我们需要 Shell 展开文本块内部的变量 "$MOTD_FILE"，
    # 以便在文件中动态显示正确的路径。
    cat > "$MOTD_FILE" << EOF
推荐的 ASCII 艺术字生成网站:
https://patorjk.com/software/taag/

您可以从这里生成喜欢的字符画，然后使用 nano 命令
手动编辑并粘贴到下面的文件中：
$MOTD_FILE
EOF
    echo -e "${C_GREEN}✅ 启动问候语已更新为 [ASCII Art 网站链接]。${C_RESET}"
}

# 函数: 恢复 Termux 官方默认的问候语
set_default_motd() {
    # 官方问候语不含需要特殊处理的字符，但使用 'EOF' 是一个好习惯。
    cat > "$MOTD_FILE" << 'EOF'
Welcome to Termux!
Wiki:      https://wiki.termux.com
Community: https://termux.com/community
Gitter:    https://gitter.im/termux/termux
IRC:       #termux on freenode
Working with packages:
 * Search packages: pkg search <query>
 * Install a package: pkg install <package>
 * Upgrade packages:  pkg upgrade
Subscribing to additional repositories:
 * Root:      pkg install root-repo
 * Unstable:  pkg install unstable-repo
 * X11:       pkg install x11-repo
For fixing any repository issues please run:
 termux-change-repo
Report issues at https://termux.com/issues
EOF
    echo -e "${C_GREEN}✅ 启动问候语已恢复为 [Termux 默认]。${C_RESET}"
}

# 函数: 清空问候语内容
clear_motd() {
    # 使用重定向 '>' 向文件中写入一个空字符串，这是清空文件最高效的方法。
    > "$MOTD_FILE"
    echo -e "${C_GREEN}✅ 启动问候语已被清空。${C_RESET}"
}

# 函数: 设置自定义问候语 (新增功能)
set_custom_motd() {
    echo -e "${C_YELLOW}请输入或粘贴您的自定义内容。${C_RESET}"
    echo -e "${C_CYAN}输入完成后，在新的一行单独输入 'END' (区分大小写) 并按回车键结束：${C_RESET}"
    # 使用 cat 和 here string 读取多行输入，直到遇到指定的终止符 'END'。
    # 这种方法比循环 read 行更高效。
    content=$(cat <<'END_CUSTOM_INPUT'
END_CUSTOM_INPUT
)
    # 将捕获到的、包含多行的 content 变量内容写入文件。
    # 使用 printf 可以更安全地处理可能包含特殊字符的输入。
    printf "%s" "$content" > "$MOTD_FILE"
    echo -e "${C_GREEN}✅ 启动问候语已更新为您的自定义内容。${C_RESET}"
}


# --- UI 与主逻辑 ---

# 函数: 显示主操作菜单
show_menu() {
    clear # 清屏，让菜单更整洁
    echo -e "${C_WHITE}========================================${C_RESET}"
    echo -e "      ${C_CYAN}Termux 启动问候语修改器 ${C_WHITE}(v3.0)${C_RESET}"
    echo -e "${C_WHITE}========================================${C_RESET}"
    echo -e "  ${C_YELLOW}1.${C_RESET} 设置为 [Termux Logo]"
    echo -e "  ${C_YELLOW}2.${C_RESET} 设置为 [Touhou Project Logo]"
    echo -e "  ${C_YELLOW}3.${C_RESET} 设置为 [LilyWhite Logo]"
    echo -e "  ${C_YELLOW}4.${C_RESET} 设置为 [ASCII Art 网站链接]"
    echo -e "  ${C_YELLOW}5.${C_RESET} ${C_GREEN}[自定义]${C_RESET} 问候语 (手动粘贴)"
    echo -e "${C_WHITE}----------------------------------------${C_RESET}"
    echo -e "  ${C_YELLOW}8.${C_RESET} 恢复为 [Termux 默认]"
    echo -e "  ${C_YELLOW}9.${C_RESET} ${C_RED}[清空]${C_RESET} 问候语"
    echo -e "${C_WHITE}----------------------------------------${C_RESET}"
    echo -e "  ${C_YELLOW}0.${C_RESET} 退出脚本"
    echo -e "${C_WHITE}========================================${C_RESET}"
}

# --- 脚本入口 ---

# 健壮性检查：在脚本执行主要逻辑前，先检查目标文件是否可写。
# 如果不可写，则提前报错退出，避免用户选择了操作后才发现失败。
if [ ! -w "$MOTD_FILE" ]; then
    echo -e "${C_RED}错误: 无法写入 MOTD 文件。${C_RESET}"
    echo "文件路径: $MOTD_FILE"
    echo "请检查文件权限或路径是否正确。"
    exit 1
fi

# 主程序循环：持续显示菜单，直到用户选择退出或完成一项操作。
while true; do
    show_menu
    # -p 参数可以在同一行显示提示信息，并等待用户输入。
    read -p "$(echo -e ${C_BLUE}"请输入您的选项 [0-9]: "${C_RESET})" choice

    case "$choice" in
        1) set_termux_logo ;;
        2) set_touhou_logo ;;
        3) set_lilywhite_logo ;;
        4) set_website_link ;;
        5) set_custom_motd ;;
        8) set_default_motd ;;
        9) clear_motd ;;
        0)
            echo -e "${C_YELLOW}正在退出...${C_RESET}"
            break # 跳出 while 循环，结束脚本
            ;;
        *) # 捕获所有其他无效输入
            echo -e "${C_RED}❌ 无效输入! 请输入菜单中显示的数字。${C_RESET}"
            sleep 2 # 暂停2秒，让用户有时间阅读错误提示
            continue # 跳过本次循环的剩余部分，直接开始下一次循环（即重新显示菜单）
            ;;
    esac

    # 如果用户的选择是有效的操作（不是退出或无效输入），程序会执行到这里。
    # 短暂暂停，让用户可以看到操作成功的提示信息。
    sleep 1
    # 完成操作后，使用 break 退出循环。
    break
done

echo -e "\n${C_CYAN}操作完成。请开启一个新的会话以查看效果。${C_RESET}"