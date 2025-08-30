#!/data/data/com.termux/files/usr/bin/bash

# ==============================================================================
# 脚本名称: Era_辅助下载.sh
# 功能描述: 一个可扩展的脚本，用于管理多个 Emuera 游戏仓库，支持指定分支。
# 作者: Termux 专家 AI
# 版本: 3.4
# 更新日志:
# v3.4: 恢复单行配置风格，并采用更健壮的'|;|'分隔符与解析逻辑，兼顾便利性与安全性。
# v3.3: 重构为多数组配置，修复了解析bug。
# ==============================================================================

# --- 游戏配置 ---
# 在这里添加或修改你的 Era 游戏仓库。
# 格式: [标识符]="菜单名称|;|Git仓库URL|;|克隆到的目录名|;|[可选的分支名]"
#
# 注意：我们使用 "|;|" (管道符+分号+管道符) 作为字段之间的分隔符。
# 这样做是为了避免当URL或名称中包含单个分号时导致的解析错误。
#
# - 标识符:         一个简短、唯一的内部英文名，用于脚本识别。
# - 菜单名称:       显示在菜单中供用户选择的名字。
# - Git仓库URL:     执行 'git clone' 时使用的地址。
# - 克隆到的目录名: 仓库将被克隆到这个文件夹内，位于下面的 BASE_DIR 中。
# - 分支名 (可选):  如果留空，脚本将使用远程仓库的默认分支 (main/master)。
#                   如果填写，脚本将只针对该分支进行克隆和同步。
# ------------------------------------------------------------------------------
declare -A GAMES_CONFIG=(
    [touhou_tw]="Touhou Era (TW) Sub-Mod|;|https://gitgud.io/era-games-zh/touhou/eratw-sub-modding.git|;|eratw-sub-modding|;|tw_for_simulator"
    # 示例: [another_game]="My Awesome Game|;|https://example.com/repo.git|;|my-awesome-game|;|"
    # 注意最后一个 |;| 后面为空，表示使用默认分支。
)

# 所有游戏仓库的基础存放目录
BASE_DIR="$HOME/storage/shared/emuera"

# --- 终端输出颜色定义 ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m';
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m';

# --- 日志与交互函数 ---
log() {
    local level=$1; shift; local color;
    case "$level" in
        "INFO") color="$BLUE";; "SUCCESS") color="$GREEN";;
        "WARN") color="$YELLOW";; "ERROR") color="$RED";;
        *) color="$NC";;
    esac
    echo -e "${color}[$level]${NC} $*"
}
die() { log "ERROR" "$1"; exit 1; }
pause() { echo ""; read -p "按 [回车键] 返回..."; }

# --- 核心 Git 操作函数 ---

# 获取远程仓库的默认分支
get_default_branch() {
    local repo_path="$1"; local branch;
    if [ ! -d "$repo_path/.git" ]; then echo "main"; return; fi
    branch=$(git -C "$repo_path" remote show origin | sed -n '/HEAD branch/s/.*: //p')
    [ -z "$branch" ] && branch="main" # 备用方案
    echo "$branch"
}

# 同步仓库 (安装与强制更新)
sync_repo() {
    local name="$1" url="$2" dir="$3" branch="$4"
    local full_path="$BASE_DIR/$dir"

    log "INFO" "开始同步仓库: $name"
    
    # 克隆操作
    if [ ! -d "$full_path/.git" ]; then
        log "INFO" "本地仓库不存在，将执行克隆操作..."
        mkdir -p "$BASE_DIR" || die "无法创建基础目录 '$BASE_DIR'。"
        
        local clone_cmd="git clone --progress"
        [ -n "$branch" ] && clone_cmd="$clone_cmd -b $branch"
        
        if $clone_cmd "$url" "$full_path"; then
            log "SUCCESS" "[$name] 克隆成功！"
        else
            log "ERROR" "[$name] 克隆失败！请检查网络、URL和分支名。"
            rm -rf "$full_path"
        fi
        return
    fi

    # 强制同步更新操作
    log "INFO" "本地仓库已存在，将执行强制同步..."
    log "INFO" "1/3: 正在从远程获取最新信息 (fetch)..."
    git -C "$full_path" fetch origin || { log "ERROR" "Git fetch 失败！"; return; }

    local target_branch="${branch:-$(get_default_branch "$full_path")}"
    log "INFO" "2/3: 同步目标分支: '$target_branch'"

    log "INFO" "3/3: 正在重置本地仓库到 'origin/$target_branch' 并清理..."
    git -C "$full_path" reset --hard "origin/$target_branch" || { log "ERROR" "Git reset 失败！"; return; }
    git -C "$full_path" clean -fdx || { log "ERROR" "Git clean 失败！"; return; }

    log "SUCCESS" "[$name] 同步完成！本地已与远程仓库 '$target_branch' 分支完全一致。"
}

# 显示仓库状态
show_status() {
    local name="$1" dir="$2"
    local full_path="$BASE_DIR/$dir"
    if [ ! -d "$full_path/.git" ]; then log "WARN" "[$name] 尚未安装。"; return; fi
    log "INFO" "显示 [$name] 的当前状态..."
    git -C "$full_path" status
}

# 删除本地仓库
delete_repo() {
    local name="$1" dir="$2"
    local full_path="$BASE_DIR/$dir"
    if [ ! -d "$full_path" ]; then log "WARN" "[$name] 尚未安装，无需删除。"; return; fi
    
    log "WARN" "您将要删除游戏 [$name] 的所有本地文件！"
    log "WARN" "目录: $full_path"
    read -p "此操作不可逆，请输入 'YES' 确认删除: " confirm

    if [ "$confirm" = "YES" ]; then
        log "INFO" "正在删除 '$full_path'..."
        if rm -rf "$full_path"; then log "SUCCESS" "[$name] 已成功删除。"; else log "ERROR" "删除 [$name] 时发生错误！"; fi
    else
        log "INFO" "操作已取消。"
    fi
}

# --- 菜单系统 ---

# 游戏管理的子菜单
game_menu() {
    local game_id="$1"
    local config_line="${GAMES_CONFIG[$game_id]}"

    # 安全地解析配置字符串：将 '|;|' 替换为换行符，然后逐行读取到变量中
    local name url dir branch
    IFS=$'\n' read -d '' -r -a values < <(echo -n "$config_line" | sed 's/|;|/\n/g')
    name="${values[0]}"
    url="${values[1]}"
    dir="${values[2]}"
    branch="${values[3]}" # 如果不存在，此项为空

    while true; do
        clear
        echo "========================================"
        echo -e "  管理游戏: ${CYAN}$name${NC}"
        echo -e "  目标分支: ${YELLOW}${branch:-默认}${NC}"
        echo "========================================"
        echo "  1. 安装 / 强制同步"
        echo "  2. 查看本地状态"
        echo -e "  3. ${RED}删除本地仓库${NC}"
        echo "----------------------------------------"
        echo "  0. 返回主菜单"
        echo "========================================"
        read -p "请为 [$name] 选择操作 [0-3]: " choice

        case "$choice" in
            1) sync_repo "$name" "$url" "$dir" "$branch"; pause ;;
            2) show_status "$name" "$dir"; pause ;;
            3) delete_repo "$name" "$dir"; pause ;;
            0) break ;;
            *) log "ERROR" "无效输入!"; sleep 1 ;;
        esac
    done
}

# 程序主菜单
main_menu() {
    local -a game_ids=()
    while true; do
        clear
        echo "========================================"
        echo "      Era 游戏辅助下载工具 (v3.4)"
        echo "========================================"
        
        game_ids=(); local i=1
        for id in "${!GAMES_CONFIG[@]}"; do
            # 使用 Bash 参数扩展，高效地提取第一个字段（菜单名称）
            local name="${GAMES_CONFIG[$id]%%\|;\|*}"
            echo "  $i. 管理: $name"
            game_ids[$i]=$id; i=$((i+1))
        done

        echo "----------------------------------------"
        echo "  0. 退出脚本"
        echo "========================================"
        read -p "请选择要管理的游戏 [0-$((${#GAMES_CONFIG[@]}))]: " choice

        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 0 ] && [ "$choice" -le "${#GAMES_CONFIG[@]}" ]; then
            if [ "$choice" -eq 0 ]; then break; fi
            game_menu "${game_ids[$choice]}"
        else
            log "ERROR" "无效输入!"; sleep 1
        fi
    done
}

# --- 脚本入口 ---
if ! command -v git &> /dev/null; then die "'git' 未安装。请运行 'pkg install git'。"; fi
if [ ! -d "$HOME/storage/shared" ]; then die "共享存储未设置。请运行 'termux-setup-storage'。"; fi

main_menu
log "SUCCESS" "感谢使用！再见！"