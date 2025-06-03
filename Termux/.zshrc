ZSH_THEME="random"
# 如果你来自 bash，你可能需要更改你的 $PATH。
# export PATH=$HOME/bin:$HOME/.local/bin:/usr/local/bin:$PATH

# Oh My Zsh 的安装路径。
export ZSH=$HOME/.oh-my-zsh

# 设置要加载的主题名称 --- 如果设置为 "random"，则每次加载 Oh My Zsh 时都会加载一个随机主题，在这种情况下，要知道加载了哪个特定主题，
# 运行：echo $RANDOM_THEME
# 参阅 https://github.com/ohmyzsh/ohmyzsh/wiki/Themes


# 设置随机加载时可供选择的主题列表
# # 当 ZSH_THEME=random 时设置此变量，将导致 zsh 从此变量加载主题，而不是在 $ZSH/themes/ 中查找
# 如果设置为空数组，则此变量无效。
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# 取消注释以下行以使用大小写敏感的补全。
# CASE_SENSITIVE="true"

# 取消注释以下行以使用连字符不敏感的补全。
# 大小写敏感的补全必须关闭。_ 和 - 将可以互换。
# HYPHEN_INSENSITIVE="true"

# 取消注释以下行之一以更改自动更新行为
# zstyle ':omz:update' mode disabled  # 禁用自动更新
# zstyle ':omz:update' mode auto      # 自动更新，不询问
zstyle ':omz:update' mode reminder  # 仅在需要更新时提醒我

# 取消注释以下行以更改自动更新的频率（以天为单位）。
# zstyle ':omz:update' frequency 13

# 如果粘贴 URL 和其他文本时出现混乱，请取消注释以下行。
# DISABLE_MAGIC_FUNCTIONS="true"

# 取消注释以下行以禁用 ls 中的颜色。
# DISABLE_LS_COLORS="true"

# 取消注释以下行以禁用自动设置终端标题。
# DISABLE_AUTO_TITLE="true"

# 取消注释以下行以启用命令自动更正。

ENABLE_CORRECTION="true"

# 取消注释以下行以在等待补全时显示红点。
# 你也可以将其设置为其他字符串，以显示该字符串而不是默认的红点。
# 例如：COMPLETION_WAITING_DOTS="%F{yellow}waiting...%f"
# 注意：此设置可能会导致 zsh < 5.7.1 版本中多行提示符出现问题 (参阅 #5765)
# COMPLETION_WAITING_DOTS="true"

# 如果你希望禁用将 VCS 下未跟踪的文件标记为 dirty (修改过的)，请取消注释以下行。
# 这将使大型仓库的状态检查速度快得多。
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# 如果你想更改 history 命令输出中显示的命令执行时间戳，
# 请取消注释以下行。
# 你可以设置以下三种可选格式之一：
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# 或者使用 strftime 函数格式规范设置自定义格式，
# 详情请参阅 'man strftime'。
# HIST_STAMPS="mm/dd/yyyy"

# 你想使用 $ZSH/custom 以外的其他自定义文件夹吗？
# ZSH_CUSTOM=/path/to/new-custom-folder

# 你想加载哪些插件？
# 标准插件可以在 $ZSH/plugins/ 中找到
# 自定义插件可以添加到 $ZSH_CUSTOM/plugins/
# 示例格式：plugins=(rails git textmate ruby lighthouse)
# 明智地添加，因为太多插件会减慢 shell 启动速度。
plugins=(git
    zsh-autosuggestions
    wd
    sudo

    emoji

    extract

    pip
    pep8
    pylint

    zsh-syntax-highlighting
)

#语法高亮必须在插件列表的最后
#有的可能还没安装 autojump
#
#按两次esc即可轻松为当前或以前的命令添加前缀。sudo
#emoji 是玩具 extract是解压用的

source $ZSH/oh-my-zsh.sh

# 用户配置

# export MANPATH="/usr/local/man:$MANPATH"

# 你可能需要手动设置你的语言环境
# export LANG=en_US.UTF-8
LANG=UTF-8
# 本地和远程会话的首选编辑器
# if [[ -n $SSH_CONNECTION ]]; then
#   export EDITOR='vim'
# else
#   export EDITOR='nvim'
# fi

# 编译标志
# export ARCHFLAGS="-arch $(uname -m)"


# 设置个人别名，覆盖 Oh My Zsh 库、
# 插件和主题提供的别名。别名可以放在这里，尽管 Oh My Zsh
# 用户被鼓励在 $ZSH_CUSTOM 文件夹中的顶级文件内定义别名，
# 文件扩展名为 .zsh。例如：
# - $ZSH_CUSTOM/aliases.zsh
# - $ZSH_CUSTOM/macos.zsh
# 要获取活动别名的完整列表，请运行 `alias`。
#
# 示例别名
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"


alias chcolor='/data/data/com.termux/files/home/.termux/colors.sh'
alias chfont='/data/data/com.termux/files/home/.termux/fonts.sh'


source ~/.bash_profile

source /data/data/com.termux/files/home/.zsh-syntax-highlighting/zsh-syntax-highlighting.zsh


#玩具 注意export和alias一样需要引号包裹



#允许tab自动补全到根目录


#在将命令添加到历史记录之前检查它是否与之前的命令相同。如果相同，则不会添加到历史记录中
##不记录与上一条命令完全相同的命令。
setopt HIST_IGNORE_DUPS

#忽略以空格开头的命令。
setopt HIST_IGNORE_SPACE

# 搜索历史记录时忽略重复的命令。
setopt HIST_FIND_NO_DUPS

#当历史记录文件达到 SAVEHIST 设置的限制时，优先删除重复的条目。
setopt HIST_EXPIRE_DUPS_FIRST

#如果新命令与历史记录中已有的命令重复，则删除旧的记录。
setopt HIST_IGNORE_ALL_DUPS

#在使用 Ctrl+R 搜索历史记录时，不显示重复的条目。
setopt HIST_FIND_NO_DUPS

#写入历史记录文件时，不写入重复的条目。
setopt HIST_SAVE_NO_DUPS