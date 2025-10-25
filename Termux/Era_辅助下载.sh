#!/data/data/com.termux/files/usr/bin/bash

# ==============================================================================
# 脚本名称: Era_辅助下载.sh
# 功能描述: 一个可扩展的脚本，用于管理多个 Emuera 游戏仓库，支持指定分支，
#           并提供安全的存档备份与恢复功能。
# 作者: Termux 专家 AI
# 版本: 4.0
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
)

# --- 全局常量 ---
# 所有游戏仓库的基础存放目录
BASE_DIR="$HOME/storage/shared/emuera"

# --- 终端输出颜色定义 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color, 用于恢复默认颜色

# --- 日志与交互函数 ---

# 统一的日志输出函数
# 用法: log "INFO" "这是一条消息"
log() {
    local level=$1 # 第一个参数是日志级别 (INFO, SUCCESS, WARN, ERROR)
    shift          # 移除第一个参数，剩下的 "$@" 就是要输出的消息
    local color
    case "$level" in
        "INFO") color="$BLUE";;
        "SUCCESS") color="$GREEN";;
        "WARN") color="$YELLOW";;
        "ERROR") color="$RED";;
        *) color="$NC";; # 其他情况不使用颜色
    esac
    # -e 参数让 echo 能够解析颜色代码
    echo -e "${color}[$level]${NC} $*"
}

# 打印错误信息并终止脚本
# 用法: die "关键错误发生"
die() {
    log "ERROR" "$1"
    exit 1 # 以非零状态码退出，表示脚本执行失败
}

# 暂停脚本执行，等待用户按回车键
# 用法: pause
pause() {
    echo "" # 打印一个空行以增加间距
    # -r 选项防止 read 命令处理反斜杠，-p 显示提示信息
    read -r -p "按 [回车键] 返回..."
}

# --- 辅助函数 ---

# 确保 Git 仓库目录被标记为安全，以避免在 Termux 共享存储中出现所有权问题
# 用法: ensure_safe_directory "/path/to/repo"
ensure_safe_directory() {
    local repo_path="$1"
    # 如果目录本身不存在，则无需任何操作
    [[ ! -d "$repo_path" ]] && return 0
    
    # 检查全局 git 配置中是否已经包含了这个路径
    # grep -q (quiet) 只返回状态码不输出，-F (fixed-string) 按字符串匹配而非正则，更安全快速
    if ! git config --global --get-all safe.directory | grep -q -F "$repo_path"; then
        log "INFO" "检测到 Git 所有权问题，自动将 '$repo_path' 添加到安全目录..."
        git config --global --add safe.directory "$repo_path"
    fi
}

# --- 核心 Git 操作函数 ---

# 获取远程仓库的默认分支名称 (通常是 main 或 master)
# 用法: get_default_branch "/path/to/repo"
get_default_branch() {
    local repo_path="$1"; local branch
    [[ ! -d "$repo_path/.git" ]] && { echo "main"; return; } # 如果不是 git 仓库，默认返回 main
    # 通过 git remote show origin 获取远程信息，然后用 sed 提取 'HEAD branch' 所在行的分支名
    branch=$(git -C "$repo_path" remote show origin | sed -n '/HEAD branch/s/.*: //p')
    [[ -z "$branch" ]] && branch="main" # 如果因某种原因没找到，备用方案设为 main
    echo "$branch"
}

# 安装 (克隆) 或常规同步 (git pull) 仓库
install_or_pull_repo() {
    local name="$1" url="$2" dir="$3" branch="$4"
    local full_path="$BASE_DIR/$dir"

    # 检查 .git 目录判断是否已克隆
    if [[ ! -d "$full_path/.git" ]]; then
        log "INFO" "本地仓库不存在，将执行克隆操作..."
        mkdir -p "$BASE_DIR" || die "无法创建基础目录 '$BASE_DIR'。"
        
        # 使用数组构建命令，这是处理含空格或特殊字符参数的最安全方式
        local clone_cmd=("git" "clone" "--progress")
        [[ -n "$branch" ]] && clone_cmd+=("-b" "$branch") # 如果指定了分支，则添加到命令数组
        
        # "${clone_cmd[@]}" 会将数组每个元素作为独立参数安全地展开
        if "${clone_cmd[@]}" "$url" "$full_path"; then
            log "SUCCESS" "[$name] 克隆成功！"
            ensure_safe_directory "$full_path" # 克隆后立即设为安全目录
        else
            log "ERROR" "[$name] 克隆失败！"
            rm -rf "$full_path" # 清理失败后留下的空目录
        fi
        return
    fi

    log "INFO" "本地仓库已存在，将执行常规同步 (git pull)..."
    local target_branch="${branch:-$(get_default_branch "$full_path")}"
    # -C 参数让 git 在指定目录执行命令，避免了 cd 进出的麻烦
    if git -C "$full_path" pull origin "$target_branch"; then
        log "SUCCESS" "[$name] 常规同步完成！"
    else
        log "ERROR" "[$name] 常规同步失败！可能存在本地修改冲突。"
    fi
}

# 强制同步：使用远程分支完全覆盖本地，会删除所有本地修改
force_sync_repo() {
    local name="$1" dir="$2" branch="$3"
    local full_path="$BASE_DIR/$dir"
    [[ ! -d "$full_path/.git" ]] && { log "WARN" "[$name] 尚未安装。"; return; }

    log "WARN" "即将执行强制同步，此操作将丢弃您在本地的所有修改！"
    log "WARN" "建议在操作前先备份存档。"
    read -r -p "请输入 'YES' 确认覆盖本地文件: " confirm
    [[ "$confirm" != "YES" ]] && { log "INFO" "操作已取消。"; return; }

    log "INFO" "正在从远程获取最新信息..."
    git -C "$full_path" fetch origin || { log "ERROR" "Git fetch 失败！"; return; }
    local target_branch="${branch:-$(get_default_branch "$full_path")}"
    
    log "INFO" "正在重置本地仓库到 'origin/$target_branch' 并清理..."
    # reset --hard: 将工作区、暂存区和版本库都重置到指定提交，丢弃所有本地修改
    git -C "$full_path" reset --hard "origin/$target_branch" || { log "ERROR" "Git reset 失败！"; return; }
    # clean -fdx: 强制(-f)删除未跟踪的文件(-d)和目录(-x)，包括被.gitignore忽略的文件
    git -C "$full_path" clean -fdx || { log "ERROR" "Git clean 失败！"; return; }
    log "SUCCESS" "[$name] 强制同步完成！"
}

# 备份存档 (sav 文件夹)，增加 YES 确认
backup_saves() {
    local name="$1" dir="$2"
    local source_sav_dir="$BASE_DIR/$dir/sav"
    local backup_base_dir="$BASE_DIR/save_backup_for_era"

    # 检查 sav 目录是否存在
    [[ ! -d "$source_sav_dir" ]] && { log "WARN" "未找到存档目录 '$source_sav_dir'。"; return; }
    # 检查 sav 目录是否为空
    [[ -z "$(ls -A "$source_sav_dir")" ]] && { log "WARN" "存档目录 '$source_sav_dir' 为空。"; return; }

    log "INFO" "找到存档目录 '$source_sav_dir'。"
    read -r -p "您确定要创建此目录的备份吗？请输入 'YES' 确认: " confirm
    [[ "$confirm" != "YES" ]] && { log "INFO" "操作已取消。"; return; }

    log "INFO" "开始备份..."
    mkdir -p "$backup_base_dir" || { log "ERROR" "无法创建备份目录 '$backup_base_dir'！"; return; }
    
    # 创建带精确时间戳的备份文件名
    local backup_filename="${dir}-sav-$(date +'%Y%m%d_%H%M%S').tar.gz"
    local full_backup_path="$backup_base_dir/$backup_filename"

    # 使用 tar 命令打包压缩。-c(创建) -z(gzip压缩) -f(指定文件名)
    # -C 选项至关重要：它让 tar 在打包前先切换到 sav 的父目录，
    # 这样压缩包内的路径是 'sav/...' 而不是 '/data/data/.../storage/shared/emuera/...'
    if tar -czf "$full_backup_path" -C "$BASE_DIR/$dir" "sav"; then
        log "SUCCESS" "存档已成功备份到: $full_backup_path"
    else
        log "ERROR" "创建存档备份失败！"
    fi
}

# 恢复存档，提供备份选择，并以覆写方式安全恢复
restore_saves() {
    local name="$1" dir="$2"
    local game_path="$BASE_DIR/$dir"
    local backup_base_dir="$BASE_DIR/save_backup_for_era"
    local current_sav_dir="$game_path/sav"

    [[ ! -d "$game_path" ]] && { log "WARN" "[$name] 尚未安装，无法恢复存档。"; return; }

    local -a backup_files=()
    # 使用 mapfile 和 find -print0 来安全地读取文件名到数组，能正确处理带空格等特殊字符的文件名。
    # find -print0: 用 null 字符分隔文件名。
    # sort -rz: -r 倒序，-z 按 null 字符分隔输入，使排序和 find 兼容。
    mapfile -d '' backup_files < <(find "$backup_base_dir" -maxdepth 1 -name "${dir}-sav-*.tar.gz" -print0 | sort -rz)
    
    if [[ ${#backup_files[@]} -eq 0 ]]; then
        log "WARN" "没有找到 [$name] 的任何存档备份。"; return;
    fi

    # 生成选择菜单
    echo "----------------------------------------"
    log "INFO" "找到以下 [$name] 的存档备份 (最新在上):"
    local i=1
    for file in "${backup_files[@]}"; do
        echo "  $i. $(basename "$file")" # basename 只显示文件名
        i=$((i+1))
    done
    echo "  0. 取消"
    echo "----------------------------------------"
    read -r -p "请选择要恢复的备份编号: " choice

    # 校验输入合法性
    if ! [[ "$choice" =~ ^[0-9]+$ && "$choice" -ge 0 && "$choice" -lt "$i" ]]; then
        log "ERROR" "无效输入！"; return
    fi
    [[ "$choice" -eq 0 ]] && { log "INFO" "操作已取消。"; return; }

    local selected_backup="${backup_files[$((choice-1))]}" # 数组索引从0开始，所以要减1
    log "WARN" "您将用备份文件恢复存档！"
    log "WARN" "备份文件: $(basename "$selected_backup")"
    log "WARN" "此操作将完全覆盖当前位于 '$current_sav_dir' 的存档！"
    read -r -p "此操作不可逆，请输入 'YES' 确认恢复: " confirm

    if [[ "$confirm" == "YES" ]]; then
        # 覆写策略：先删除旧目录，再解压，保证恢复的干净彻底
        log "INFO" "正在删除旧的存档目录以进行干净恢复..."
        rm -rf "$current_sav_dir"
        log "INFO" "正在从 '$(basename "$selected_backup")' 恢复..."
        # -x(解压) -z(gzip) -f(指定文件)，-C 指定解压的目标目录
        if tar -xzf "$selected_backup" -C "$game_path"; then
            log "SUCCESS" "存档已成功恢复到 '$current_sav_dir'。"
        else
            log "ERROR" "恢复存档时发生错误！"
        fi
    else
        log "INFO" "恢复操作已取消。"
    fi
}

# 显示 git status
show_status() {
    local name="$1" dir="$2"
    local full_path="$BASE_DIR/$dir"
    [[ ! -d "$full_path/.git" ]] && { log "WARN" "[$name] 尚未安装。"; return; }
    log "INFO" "显示 [$name] 的当前状态..."
    git -C "$full_path" status
}

# 删除本地仓库
delete_repo() {
    local name="$1" dir="$2"
    local full_path="$BASE_DIR/$dir"
    [[ ! -d "$full_path" ]] && { log "WARN" "[$name] 尚未安装，无需删除。"; return; }
    
    log "WARN" "您将要删除游戏 [$name] 的所有本地文件！"
    log "WARN" "目录: $full_path"
    read -r -p "此操作不可逆，请输入 'YES' 确认删除: " confirm

    if [[ "$confirm" == "YES" ]]; then
        log "INFO" "正在删除 '$full_path'..."
        if rm -rf "$full_path"; then
            log "SUCCESS" "[$name] 已成功删除。"
            
            # 尝试自动清理 Git 的 safe.directory 配置
            log "INFO" "正在清理相关的 Git 安全目录配置..."
            # 使用 --unset 精确移除条目，如果配置不存在，2>/dev/null 会抑制错误信息。
            if git config --global --unset safe.directory "$full_path" 2>/dev/null; then
                log "SUCCESS" "已成功清理 Git 安全目录配置。"
            else
                log "INFO" "未找到或无需清理相关的 Git 安全目录配置。"
            fi
        else
            log "ERROR" "删除 [$name] 时发生错误！"
        fi
    else
        log "INFO" "操作已取消。"
    fi
}

# --- 菜单系统 ---

# 游戏管理的子菜单
game_menu() {
    local game_id="$1"
    local config_line="${GAMES_CONFIG[$game_id]}"
    local name url dir branch
    # 使用 IFS 和 read 将配置字符串安全地解析到数组中
    # IFS=$'\n': 将换行符作为分隔符
    # read -d '': 读取直到 null 字符（sed 的输出没有 null，所以会读完整个字符串）
    # sed 's/|;|/\n/g': 将我们的分隔符 '|;|' 替换为换行符
    # < <(...): 进程替换，将命令的输出作为文件供 read 读取
    IFS=$'\n' read -d '' -r -a values < <(echo -n "$config_line" | sed 's/|;|/\n/g')
    name="${values[0]}"; url="${values[1]}"; dir="${values[2]}"; branch="${values[3]}"
    
    local full_path="$BASE_DIR/$dir"
    ensure_safe_directory "$full_path" # 进入菜单时就检查并设置安全目录

    while true; do
        clear
        echo "========================================"
        echo -e "  管理游戏: ${CYAN}$name${NC}"
        echo -e "  目标分支: ${YELLOW}${branch:-默认}${NC}"
        echo "========================================"
        echo "  1. 安装 / 常规同步 (保留本地修改)"
        echo -e "  2. ${YELLOW}强制同步 (覆盖本地修改)${NC}"
        echo "  3. 备份存档 (sav)"
        echo "  4. 恢复存档 (sav)"
        echo "  5. 查看本地状态"
        echo -e "  6. ${RED}删除本地仓库${NC}"
        echo "----------------------------------------"
        echo "  0. 返回主菜单"
        echo "========================================"
        read -r -p "请为 [$name] 选择操作 [0-6]: " choice

        case "$choice" in
            1) install_or_pull_repo "$name" "$url" "$dir" "$branch"; pause ;;
            2) force_sync_repo "$name" "$dir" "$branch"; pause ;;
            3) backup_saves "$name" "$dir"; pause ;;
            4) restore_saves "$name" "$dir"; pause ;;
            5) show_status "$name" "$dir"; pause ;;
            6) delete_repo "$name" "$dir"; pause ;;
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
        echo "      Era 游戏辅助下载工具 (v4.0)"
        echo "========================================"
        game_ids=(); local i=1
        for id in "${!GAMES_CONFIG[@]}"; do
            # 使用 Bash 参数扩展高效地提取菜单名称（第一个字段）
            # %%\|;\|* 表示从右边删除最长的匹配 "|;|" 及其后所有内容的子串
            local name="${GAMES_CONFIG[$id]%%\|;\|*}"
            echo "  $i. 管理: $name"
            game_ids[$i]=$id; i=$((i+1))
        done
        echo "----------------------------------------"
        echo "  0. 退出脚本"
        echo "========================================"
        read -r -p "请选择要管理的游戏 [0-$((${#GAMES_CONFIG[@]}))]: " choice

        # 校验输入是否为合法范围内的数字
        if [[ "$choice" =~ ^[0-9]+$ && "$choice" -ge 0 && "$choice" -le "${#GAMES_CONFIG[@]}" ]]; then
            [[ "$choice" -eq 0 ]] && break
            game_menu "${game_ids[$choice]}"
        else
            log "ERROR" "无效输入!"; sleep 1
        fi
    done
}

# --- 脚本入口 ---

# 检查核心依赖：git 命令
if ! command -v git &> /dev/null; then
    die "'git' 未安装。请运行 'pkg install git'。"
fi
# 检查 Termux 共享存储是否已设置
if [[ ! -d "$HOME/storage/shared" ]]; then
    die "共享存储未设置。请运行 'termux-setup-storage'。"
fi

main_menu
log "SUCCESS" "感谢使用！再见！"