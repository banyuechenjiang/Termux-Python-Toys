# tavern_sync_config_gui.py (v3.24 - 修复 messagebox.warning 错误 & 优化配置提示)
# v3.24:  修复 AttributeError: module 'tkinter.messagebox' has no attribute 'warning' 错误，优化配置提示信息和描述
# v3.22:  为 "复制命令" 功能添加配置验证，在执行命令前检查必要配置项，并更新命令描述信息
# v3.21:  恢复 "复制命令" 弹窗中的命令说明，放置在三栏下方，完善命令描述信息 (纯文本)
# v3.19:  简化 "复制命令" 弹窗，移除命令说明，修复 grid/pack 布局冲突，调整弹窗大小和布局，移除 "预览命令" 功能

# v3.16:  新增 "预览命令" 和 "复制命令" 功能，方便用户查看和使用 tavern_sync.py 命令行

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import json
import os
from pathlib import Path
import sys

CONFIG_FILE = "tavern_sync_config.json"
SCRIPT_DIR = Path(__file__).resolve().parent
DIALOG_POSITIONS_KEY = "dialog_positions"
dialog_positions = {}

CONFIG_DESCRIPTION = """
脚本说明 (tavern_sync_config_gui.py):

本脚本提供一个图形用户界面 (GUI)，用于创建和编辑 tavern_sync.py 脚本所需的配置文件 (tavern_sync_config.json)。

关键功能:

- 可视化配置:  通过友好的图形界面，无需手动编辑 JSON 文件即可管理世界书同步配置。
- 路径管理:  方便地浏览和选择世界书相关的文件和文件夹路径。
- 配置说明:  提供详细的配置字段说明和注意事项 (即本脚本说明)。
- 复制命令:  允许用户选择所有支持的 tavern_sync.py 命令，并可根据需要添加选项 (--no_detect, --no_trim, --port, -y)，一键复制到剪贴板，方便在终端中直接执行。
- 配置验证:  在复制命令前，GUI 会自动检查所选命令是否需要必要的配置，并在配置缺失时给出提示。
- 窗口位置记忆:  编辑窗口会记住上次关闭时的位置 (此功能仅为 GUI 辅助，不影响 tavern_sync.py 的使用)。

配置文件 (tavern_sync_config.json) 格式说明:

根对象是一个字典，键是“世界书名称”，值是包含以下字段的字典：

{
  "世界书名称": {
    "directory": "条目文件夹的绝对路径 (必填), 如 C:/某世界书分文件文件夹, 其中 / 也可以换成 \\",
    "json_file": "世界书json文件的绝对路径 (必填), 如 C:/SillyTavern/data/default-user/worlds/世界书.json",
    "user_name": "填入你<user>的名字，则同步时会自动将名字替换成<user>",
    "publish_directory": "要打包到的文件夹的绝对路径 (可选), 如 C:/",
    "character_card": "角色卡文件的绝对路径 (可选), 如 C:/SillyTavern/data/default-user/characters/角色卡.png",
    "quick_replies": [
      "快速回复路径1 (可选)",
      "快速回复路径2 (可选)"
    ],
    "script_directory": "前端助手源文件的绝对路径 (可选)"
  },
  "dialog_positions": { ... }  // GUI 窗口位置信息 (不影响 tavern_sync.py 使用)
}

字段说明:

- 世界书名称: 用于标识不同的世界书配置，应具有唯一性。在命令行中使用 tavern_sync.py 时，需要用到此名称。
- directory: 存放世界书条目分文件的文件夹 (必填), 在 GUI 中会显示为相对于脚本所在目录的相对路径。
- json_file: SillyTavern 中世界书 JSON 文件的完整路径 (必填), 在 GUI 中仅显示文件名。
- user_name: 你的用户名，同步时会被替换为 <user>。
- publish_directory: 要打包到的文件夹的绝对路径 (可选), 在 GUI 中仅显示文件名。
- character_card: 角色卡文件路径 (可选)，在 GUI 中仅显示文件名。
- quick_replies: 快速回复文件路径 (可选)，在 GUI 中仅显示文件名。
- script_directory: 前端助手源文件路径 (可选)，在 GUI 中会显示为相对于脚本所在目录的相对路径。

注意事项:

- 本脚本生成的配置文件 (tavern_sync_config.json) 与 tavern_sync.py 脚本配合使用。
- 请确保 SillyTavern 根目录设置正确。
- 配置文件中的路径请使用绝对路径，GUI 会根据情况显示相对路径或文件名以简化界面。
- __"条目文件夹"__ 和 __"世界书 JSON 文件"__  是 tavern_sync.py 脚本运行的必要配置，请务必正确填写。
- 使用 "复制命令" 功能，您可以方便地将 tavern_sync.py 命令复制到剪贴板，然后在终端中执行。
"""

COMMAND_DESCRIPTIONS = {
    "extract": "命令: extract <世界书名称> [选项]\n\n"
               "  将世界书提取成独立文件。\n\n"
               "必要配置:  条目文件夹 和 世界书 JSON 文件。\n\n"
               "  -  <世界书名称> (必需):  配置文件中世界书的名称。\n"
               "  -  选项:\n"
               "      --no_detect: 禁用格式自动检测，所有条目提取为 .md 文件。\n"
               "      -y: 免确认执行。",
    "push":    "命令: push <世界书名称> [选项]\n\n"
               "  将独立文件推送到世界书。\n\n"
               "必要配置:  条目文件夹 和 世界书 JSON 文件。\n\n"
               "  -  <世界书名称> (必需):  配置文件中世界书的名称。\n"
               "  -  选项:\n"
               "      --no_trim: 推送时不压缩条目内容。\n"
               "      -y: 免确认执行。",
    "watch":   "命令: watch <世界书名称> [选项]\n\n"
               "  实时监听文件改动并自动推送。\n\n"
               "必要配置:  条目文件夹 和 世界书 JSON 文件。\n\n"
               "  -  <世界书名称> (必需):  配置文件中世界书的名称。\n"
               "  -  选项:\n"
               "      --no_trim: 监听推送时不压缩条目内容。\n"
               "      --port <端口号>: 指定监听端口 (默认: 6620)。",
    "pull":    "命令: pull <世界书名称> [选项]\n\n"
               "  将世界书条目拉取到独立文件。\n\n"
               "必要配置:  条目文件夹 和 世界书 JSON 文件。\n\n"
               "  -  <世界书名称> (必需):  配置文件中世界书的名称。\n"
               "  -  选项:\n"
               "      -y: 免确认执行。",
    "publish": "命令: publish <世界书名称> [选项]\n\n"
               "  打包世界书及相关资源。\n\n"
               "建议配置 (完整打包):  发布文件夹，角色卡，快速回复 和 前端脚本文件夹。\n\n"
               "  -  <世界书名称> (必需):  配置文件中世界书的名称。\n"
               "  -  选项:\n"
               "      -y: 免确认执行。",
    "to_json": "命令: to_json <世界书名称> [选项]\n\n"
               "  将 YAML 文件转换为 JSON 文件。\n\n"
               "必要配置:  条目文件夹 和 世界书 JSON 文件。\n\n"
               "  -  <世界书名称> (必需):  配置文件中世界书的名称。\n"
               "  -  选项:\n"
               "      -y: 免确认执行。",
    "to_yaml": "命令: to_yaml <世界书名称> [选项]\n\n"
               "  将 JSON 文件转换为 YAML 文件。\n\n"
               "必要配置:  条目文件夹 和 世界书 JSON 文件。\n\n"
               "  -  <世界书名称> (必需):  配置文件中世界书的名称。\n"
               "  -  选项:\n"
               "      -y: 免确认执行。"
}


def get_root_path():
    """获取 SillyTavern 根目录 (优化：优先从配置文件获取)"""

    def extract_root_from_path(file_path):
        """尝试从给定路径中提取 SillyTavern 根目录"""
        current_path = Path(file_path)
        while current_path != current_path.parent:
            expected_path = current_path / "data" / "default-user" / "worlds"
            if expected_path.exists() and expected_path.is_dir():
                return str(current_path)
            current_path = current_path.parent
        return None

    # 1. 尝试从配置文件读取
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            world_entries = json.load(f)
            for entry_data in world_entries.values():
                json_file = entry_data.get("json_file")
                if json_file:
                    root_path = extract_root_from_path(json_file)
                    if root_path:
                        return root_path
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # 2. 自动查找
    def find_worlds_dir():
        documents_path = os.path.expanduser("~/Documents")
        if not os.path.exists(documents_path):
            documents_path = os.path.expanduser("~")

        for root, dirs, _ in os.walk(documents_path):
            if "worlds" in dirs:
                worlds_path = os.path.join(root, "worlds")
                if (Path(worlds_path) / "data" / "default-user").exists():
                    return extract_root_from_path(worlds_path)
        return None

    root_path = find_worlds_dir()
    if root_path:
        return root_path

    # 3. 手动选择
    while True:
        root_path = filedialog.askdirectory(title="请选择 SillyTavern 文件夹")
        if not root_path:
            if messagebox.askyesno("退出", "未选择 SillyTavern 文件夹，是否退出？"):
                exit()
            else:
                continue

        extracted_root = extract_root_from_path(root_path)
        if extracted_root:
            return extracted_root

        messagebox.showerror("错误", "所选文件夹或其上级文件夹中未找到有效的 SillyTavern 目录结构，请重新选择。")

def create_browse_button(parent, text, row, column, initialdir_func, target_var, filetypes=[("JSON Files", "*.json")]):
    """创建浏览按钮的通用函数 (根据 text 判断选择文件或文件夹) # 优化: 根据 text 参数判断"""
    def browse():
        initialdir = initialdir_func()
        if text == "浏览文件夹":
            selected_path = filedialog.askdirectory(initialdir=initialdir if initialdir and os.path.exists(initialdir) else "")
        else:
            selected_path = filedialog.askopenfilename(
                initialdir=initialdir if initialdir and os.path.exists(initialdir) else "",
                filetypes=filetypes
            )
        if selected_path:
            target_var.set(selected_path)
            if text != "浏览文件夹":
               target_var.set(os.path.basename(selected_path))

    button = tk.Button(parent, text=text, command=browse)
    button.grid(row=row, column=column)

def browse_character_card(parent, row, column, initialdir_func, target_var):
    """角色卡文件浏览函数 (不限制文件类型)  # 优化:  不限制文件类型"""
    def browse():
        initialdir = initialdir_func()
        selected_path = filedialog.askopenfilename(
            initialdir=initialdir if initialdir and os.path.exists(initialdir) else ""
            # filetypes 参数不传入，即不限制类型
        )
        if selected_path:
            target_var.set(selected_path)
            target_var.set(os.path.basename(selected_path))

    button = tk.Button(parent, text="浏览文件", command=browse)
    button.grid(row=row, column=column)

def create_world_entry_dialog(parent, root_path, world_name=None, entry_data=None):
    dialog = tk.Toplevel(parent)
    dialog.title("编辑世界书配置" if entry_data else "添加世界书配置")
    dialog.transient(parent)
    dialog.grab_set()

    # 尝试恢复窗口位置 # 优化: 记住并恢复窗口位置
    if world_name in dialog_positions:
        dialog.geometry(dialog_positions[world_name])
    else:
        # 默认居中 (如果需要)
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()
        x = (dialog.winfo_screenwidth() // 2) - (width // 2)
        y = (dialog.winfo_screenheight() // 2) - (height // 2)
        dialog.geometry(f"+{x}+{y}")

    frame = tk.Frame(dialog, padx=10, pady=10)
    frame.pack(fill=tk.BOTH, expand=True)

    # --- 世界书名称 ---
    tk.Label(frame, text="世界书名称:").grid(row=0, column=0, sticky=tk.W)
    name_var = tk.StringVar(value=world_name if world_name else "")
    name_entry = tk.Entry(frame, textvariable=name_var)
    name_entry.grid(row=0, column=1, sticky=tk.EW)
    if not world_name:
        tk.Label(frame, text="提示：此名称将作为 tavern_sync.py 脚本的标识符。\n例如：`python tavern_sync.py extract 此世界书名称`").grid(row=0, column=2, sticky=tk.W)

    # --- 条目文件夹 (directory) --- # 优化: 条目文件夹选择与路径显示
    tk.Label(frame, text="条目文件夹 (directory):").grid(row=1, column=0, sticky=tk.W, pady=5)
    if entry_data:
        directory_path = entry_data.get("directory", "")
        # 显示逻辑：相对路径或绝对路径
        if os.path.isabs(directory_path):
            try:
                relative_path = os.path.relpath(directory_path, SCRIPT_DIR)
                if not relative_path.startswith(".."):
                    directory_path = relative_path
            except ValueError:
                pass
        directory_var = tk.StringVar(value=directory_path)
    else:
        directory_var = tk.StringVar(value=str(Path("【条目文件】") / name_var.get()))

    directory_entry = tk.Entry(frame, textvariable=directory_var)
    directory_entry.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=5)
    create_browse_button(frame, "浏览文件夹", 2, 2, lambda: directory_var.get(), directory_var)

    # --- 世界书 JSON 文件 (json_file) --- # 优化:  GUI 仅显示文件名
    tk.Label(frame, text="世界书 JSON 文件 (json_file):").grid(row=3, column=0, sticky=tk.W, pady=5)
    json_file_var = tk.StringVar()
    if entry_data:
        json_file_path = entry_data.get("json_file", "")
        if json_file_path:
            json_file_var.set(os.path.basename(json_file_path))
    json_file_entry = tk.Entry(frame, textvariable=json_file_var)
    json_file_entry.grid(row=4, column=0, columnspan=2, sticky=tk.EW, padx=5)
    create_browse_button(frame, "浏览文件", 4, 2, lambda: str(Path(root_path) / "data" / "default-user" / "worlds"), json_file_var)

    # --- 用户名 (user_name) ---
    tk.Label(frame, text="用户名 (user_name):").grid(row=5, column=0, sticky=tk.W)
    user_name_var = tk.StringVar(value=entry_data.get("user_name", "<user>") if entry_data else "<user>")
    user_name_entry = tk.Entry(frame, textvariable=user_name_var)
    user_name_entry.grid(row=5, column=1, sticky=tk.EW)
    tk.Label(frame, text="提示：填入你<user>的名字，则同步时会自动将名字替换成<user>").grid(row=5, column=2, sticky=tk.W)

    # --- 发布文件夹 (publish_directory) --- # 优化: GUI 仅显示文件名
    tk.Label(frame, text="发布文件夹 (publish_directory):").grid(row=6, column=0, sticky=tk.W, pady=5)
    publish_directory_var = tk.StringVar()
    if entry_data:
        publish_directory_path = entry_data.get("publish_directory", "")
        if publish_directory_path:
            publish_directory_var.set(os.path.basename(publish_directory_path))
    publish_directory_entry = tk.Entry(frame, textvariable=publish_directory_var)
    publish_directory_entry.grid(row=7, column=0, columnspan=2, sticky=tk.EW, padx=5)
    create_browse_button(frame, "浏览文件夹", 7, 2, lambda: "", publish_directory_var)

    # --- 角色卡 (character_card) --- # 优化:  GUI 仅显示文件名, 角色卡文件类型不限制
    tk.Label(frame, text="角色卡 (character_card):").grid(row=8, column=0, sticky=tk.W, pady=5)
    character_card_var = tk.StringVar()
    if entry_data:
        character_card_path = entry_data.get("character_card", "")
        if character_card_path:
            character_card_var.set(os.path.basename(character_card_path))
    character_card_entry = tk.Entry(frame, textvariable=character_card_var)
    character_card_entry.grid(row=9, column=0, columnspan=2, sticky=tk.EW, padx=5)
    browse_character_card(frame, 9, 2, lambda: str(Path(root_path) / "data" / "default-user" / "characters"), character_card_var)

    # --- 快速回复 (quick_replies) --- (单独一行) # 优化: GUI 仅显示文件名
    tk.Label(frame, text="快速回复 (quick_replies):").grid(row=10, column=0, sticky=tk.W)
    quick_replies_filenames = [os.path.basename(path) for path in entry_data.get("quick_replies", [])] if entry_data else []
    quick_replies_list_var = tk.Variable(value=quick_replies_filenames)
    quick_replies_listbox = tk.Listbox(frame, listvariable=quick_replies_list_var, height=3, selectmode=tk.SINGLE)
    quick_replies_listbox.grid(row=11, column=0, columnspan=4, sticky=tk.EW)

    def add_quick_reply():
        initialdir = Path(root_path) / "data" / "default-user" / "QuickReplies"
        file_path = filedialog.askopenfilename(initialdir=initialdir if initialdir.exists() else root_path, filetypes=[("JSON Files", "*.json")])
        if file_path:
            filename = os.path.basename(file_path)
            current_replies = list(quick_replies_list_var.get())
            if filename not in current_replies:
                current_replies.append(filename)
                quick_replies_list_var.set(current_replies)

    def remove_quick_reply():
        selected_indices = quick_replies_listbox.curselection()
        if selected_indices:
            current_replies = list(quick_replies_list_var.get())
            current_replies.pop(selected_indices[0])
            quick_replies_list_var.set(current_replies)

    add_button = tk.Button(frame, text="添加", command=add_quick_reply)
    add_button.grid(row=12, column=1, sticky="ew")
    remove_button = tk.Button(frame, text="移除", command=remove_quick_reply)
    remove_button.grid(row=12, column=2, sticky="ew")

    # --- 前端脚本文件夹 (script_directory) --- # 优化: 条目文件夹选择
    tk.Label(frame, text="前端脚本文件夹 (script_directory):").grid(row=13, column=0, sticky=tk.W, pady=5)
    if entry_data:
        script_directory_path = entry_data.get("script_directory", "")
        # 显示逻辑：相对路径或绝对路径
        if os.path.isabs(script_directory_path):
            try:
                relative_path = os.path.relpath(script_directory_path, SCRIPT_DIR)
                if not relative_path.startswith(".."):
                    script_directory_path = relative_path
            except ValueError:
                pass
        script_directory_var = tk.StringVar(value=script_directory_path)
    else:
        script_directory_var = tk.StringVar(value="")
    script_directory_entry = tk.Entry(frame, textvariable=script_directory_var)
    script_directory_entry.grid(row=14, column=0, columnspan=2, sticky=tk.EW, padx=5)
    create_browse_button(frame, "浏览文件夹", 14, 2, lambda: "", script_directory_var)

    # --- 确定/取消 按钮 ---
    def on_ok():
        new_world_name = name_var.get()
        directory_path = directory_var.get()
        if not os.path.isabs(directory_path):
            directory_path = os.path.abspath(os.path.join(SCRIPT_DIR, directory_path))

        quick_replies_filenames = list(quick_replies_list_var.get())
        quick_replies_full_paths = []

        if entry_data and "quick_replies" in entry_data:
            for filename in quick_replies_filenames:
                original_path = next((path for path in entry_data["quick_replies"] if os.path.basename(path) == filename), None)
                quick_replies_full_paths.append(original_path or os.path.join(root_path, "data", "default-user", "QuickReplies", filename))
        else:
            quick_replies_full_paths = [os.path.join(root_path, "data", "default-user", "QuickReplies", filename) for filename in quick_replies_filenames]

        # 获取 json_file, character_card 的完整路径
        json_file_full_path = entry_data.get("json_file", "") if entry_data else ""
        if json_file_var.get():
            input_filename = json_file_var.get()
            if entry_data and "json_file" in entry_data and os.path.basename(entry_data["json_file"]) == input_filename:
                json_file_full_path = entry_data["json_file"]
            else:
                json_file_full_path = os.path.join(root_path, "data", "default-user", "worlds", input_filename)

        character_card_full_path = entry_data.get("character_card", "") if entry_data else ""
        if character_card_var.get():
            input_filename = character_card_var.get()
            if entry_data and "character_card" in entry_data and os.path.basename(entry_data["character_card"]) == input_filename:
                character_card_full_path = entry_data["character_card"]
            else:
                character_card_full_path = os.path.join(root_path, "data", "default-user", "characters", input_filename)

        entry_data_result = {
            "directory": directory_path,
            "json_file": json_file_full_path,
            "user_name": user_name_var.get(),
            "publish_directory": publish_directory_var.get(),
            "character_card": character_card_full_path,
            "quick_replies": quick_replies_full_paths,
            "script_directory": script_directory_var.get()
        }
        if not new_world_name or not entry_data_result["directory"] or not entry_data_result["json_file"]:
            messagebox.showerror("错误", "世界书名称、条目文件夹、JSON 文件为必填项。")
            return

        dialog.result = (new_world_name, entry_data_result)
        dialog.destroy()

    def on_cancel():
        dialog.result = None
        dialog.destroy()

    button_width = 10
    ok_button = tk.Button(frame, text="确定", command=on_ok, width=button_width)
    ok_button.grid(row=15, column=1, sticky=tk.E, pady=5)
    cancel_button = tk.Button(frame, text="取消", command=on_cancel, width=button_width)
    cancel_button.grid(row=15, column=2, sticky=tk.W, pady=5)

    def save_dialog_position(event):
        if world_name:
            dialog_positions[world_name] = dialog.winfo_geometry()
    dialog.bind("<Destroy>", save_dialog_position)

    for i in range(4):
        frame.columnconfigure(i, weight=1)

    def update_default_directory(*args):
        default_directory = Path("【条目文件】") / name_var.get()
        directory_var.set(str(default_directory))
    name_var.trace_add("write", update_default_directory)

    dialog.wait_window(dialog)
    return dialog.result if hasattr(dialog, 'result') else None

def build_command_string(command_type, world_name, world_data, extra_args=None):
    """
    构建 tavern_sync.py 命令的字符串。

    Args:
        command_type: 命令类型 (extract, push, watch, pull, publish, to_json, to_yaml)。
        world_name: 世界书名称。
        world_data: 世界书配置数据。
        extra_args: 字典类型，表示附加参数, 例如: {no_trim: True, port: 6620}
    Returns:
        完整的命令行字符串。
    """
    command = ["python", "tavern_sync.py", command_type, world_name]

    if extra_args:
       if extra_args.get("no_detect"):
            command.append("--no_detect")
       if extra_args.get("no_trim"):
            command.append("--no_trim")
       if command_type == "watch" and extra_args.get("port"): #  仅 watch 命令添加 --port
            command.extend(["--port", str(extra_args.get("port"))])
       if extra_args.get("confirm") is False: #  False 相当于 -y 参数
            command.append("-y")

    return " ".join(command)

def create_gui(root_path):
    root = tk.Tk()
    root.title("Tavern Sync 配置助手")

    root.geometry("800x600")
    font_size = 12
    default_font = ("Arial", font_size)
    root.option_add("*Font", default_font)

    style = ttk.Style()
    style.configure("Treeview.Heading", font=('Arial', font_size))
    style.configure("Treeview", font=('Arial', font_size), rowheight=int(font_size * 2.2))

    world_entries = {}
    global dialog_positions

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            world_entries = data
            dialog_positions = data.get(DIALOG_POSITIONS_KEY, {})
            if DIALOG_POSITIONS_KEY in world_entries:
               del world_entries[DIALOG_POSITIONS_KEY]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        messagebox.showinfo("提示", f"配置文件 {CONFIG_FILE} 不存在或格式错误，将创建一个新的配置文件。")

    tk.Label(root, text="双击条目进行编辑", font=("Arial", font_size, "italic")).pack(pady=5)

    tree = ttk.Treeview(root, columns=("世界书名称",), show="headings")
    tree.heading("世界书名称", text="世界书名称")
    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def update_treeview():
        for i in tree.get_children():
            tree.delete(i)
        for name in world_entries:
            tree.insert("", tk.END, values=(name,))

    def show_description():
        desc_window = tk.Toplevel(root)
        desc_window.title("脚本说明") # 修改标题
        text_widget = tk.Text(desc_window, wrap=tk.WORD, padx=10, pady=10, font=default_font)
        text_widget.insert(tk.END, CONFIG_DESCRIPTION)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(fill=tk.BOTH, expand=True)

        width = 800
        height = 600
        screen_width = desc_window.winfo_screenwidth()
        screen_height = desc_window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        desc_window.geometry(f"{width}x{height}+{x}+{y}")

    def add_world_entry():
        world_name = simpledialog.askstring("输入", "请输入世界书名称:\n此名称将作为 tavern_sync.py 脚本的标识符。\n例如：`python tavern_sync.py extract 此世界书名称`")
        if not world_name:
            return
        if world_name in world_entries:
            messagebox.showerror("错误", f"世界书名称 '{world_name}' 已存在，请使用不同的名称。")
            return

        result = create_world_entry_dialog(root, root_path, world_name=world_name)
        if result:
            name, data = result
            world_entries[name] = data
            update_treeview()
            save_config()

    def edit_world_entry():
      try:
        selected_item = tree.selection()[0]
        selected_name = tree.item(selected_item, "values")[0]

        if selected_name not in world_entries:
            messagebox.showerror("错误", f"世界书名称 '{selected_name}' 的配置数据不存在。")
            return

        current_data = world_entries[selected_name]

        result = create_world_entry_dialog(root, root_path, world_name=selected_name, entry_data=current_data)
        if result:
            new_name, new_data = result
            if new_name != selected_name:
                if new_name in world_entries:
                    messagebox.showerror("错误", f"世界书名称 '{new_name}' 已存在，请使用不同的名称。")
                    return
                del world_entries[selected_name]
                world_entries[new_name] = new_data
            else:
                world_entries[new_name] = new_data
            update_treeview()
            save_config()
      except IndexError:
        pass
      except KeyError as e:
          messagebox.showerror("错误", f"配置数据错误：{e}。请尝试删除配置文件后重试。")

    def delete_world_entry():
        try:
            selected_item = tree.selection()[0]
            selected_name = tree.item(selected_item, "values")[0]
            if messagebox.askyesno("确认", f"确定要删除世界书 '{selected_name}' 的配置吗？"):
                del world_entries[selected_name]
                update_treeview()
                save_config()
        except IndexError:
            pass

    def copy_command():
       try:
            selected_item = tree.selection()[0]
            selected_name = tree.item(selected_item, "values")[0]
            world_data = world_entries[selected_name]
            # 创建一个新窗口来选择命令类型
            dialog = tk.Toplevel(root)
            dialog.title("复制命令") #  修改标题
            dialog.transient(root)
            dialog.grab_set()
            dialog.geometry("800x450") #  调整弹窗高度

            dialog_frame = tk.Frame(dialog) #  主Frame
            dialog_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
            dialog_frame.columnconfigure(0, weight=1) #  命令列表列
            dialog_frame.columnconfigure(1, weight=1) #  参数选项列
            dialog_frame.columnconfigure(2, weight=1) #  确定按钮列
            dialog_frame.rowconfigure(1, weight=1) #  命令说明行

            # 命令列表 Frame
            commands_frame = tk.Frame(dialog_frame)
            commands_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=5) # 使用 grid 布局, 缩小 pady
            tk.Label(commands_frame, text="命令列表:").pack(anchor=tk.W) #  标题

            # 参数选项 Frame
            options_frame = tk.Frame(dialog_frame)
            options_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=5) # 使用 grid 布局, 缩小 pady
            tk.Label(options_frame, text="参数选项:").pack(anchor=tk.W) # 标题

            # 命令说明 Frame
            description_frame = tk.Frame(dialog_frame) # 命令说明 Frame
            description_frame.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=10, pady=5) # Grid 布局，跨越两列
            tk.Label(description_frame, text="命令说明:").pack(anchor=tk.W) # 命令说明标题
            description_text = tk.Text(description_frame, wrap=tk.WORD, height=5, state=tk.DISABLED) #  Text 组件显示命令说明, 调整高度
            description_text.pack(fill=tk.BOTH, expand=True)

            # 创建一个变量来存储所选的命令
            selected_command = tk.StringVar(value="extract")

            # 创建 Radiobutton 和命令说明联动
            def update_description(*args):
                command = selected_command.get()
                description = COMMAND_DESCRIPTIONS.get(command, "No description available.") #  获取命令说明
                description_text.config(state=tk.NORMAL) #  允许编辑 Text 组件
                description_text.delete("1.0", tk.END) #  清空 Text 组件
                description_text.insert(tk.END, description) #  插入命令说明
                description_text.config(state=tk.DISABLED) #  禁止编辑 Text 组件

            # 创建 Radiobutton
            commands = ["extract", "push", "watch", "pull", "publish", "to_json", "to_yaml"]
            for i, command in enumerate(commands): # 使用 enumerate 获取索引
                rb = tk.Radiobutton(commands_frame, text=command, variable=selected_command, value=command, command=update_description) # 绑定 update_description
                rb.pack(anchor=tk.W) # 使用 pack 布局在 commands_frame 中

            # 复选框和端口输入框
            no_detect_var = tk.BooleanVar(value=False)
            no_detect_check = tk.Checkbutton(options_frame, text="--no_detect (禁用格式检测)", variable=no_detect_var)
            no_detect_check.pack(anchor=tk.W)

            no_trim_var = tk.BooleanVar(value=False)
            no_trim_check = tk.Checkbutton(options_frame, text="--no_trim (不压缩内容)", variable=no_trim_var)
            no_trim_check.pack(anchor=tk.W)

            port_frame = tk.Frame(options_frame) #  port_frame 放在 options_frame 内部
            port_frame.pack(anchor=tk.W)
            tk.Label(port_frame, text="--port (端口):").pack(side=tk.LEFT)
            port_var = tk.StringVar(value="6620")  # 默认端口号
            port_entry = tk.Entry(port_frame, textvariable=port_var, width=5)
            port_entry.pack(side=tk.LEFT)

            confirm_var = tk.BooleanVar(value=False) # 默认需要确认
            confirm_check = tk.Checkbutton(options_frame, text="-y (无需确认)", variable=confirm_var)
            confirm_check.pack(anchor=tk.W)

            # 禁用/启用额外选项的函数
            def update_extra_options(*args):
                no_detect_check.config(state=tk.NORMAL if selected_command.get() == "extract" else tk.DISABLED)
                no_trim_check.config(state=tk.NORMAL if selected_command.get() in ["push", "watch"] else tk.DISABLED)
                port_entry.config(state=tk.NORMAL if selected_command.get() == "watch" else tk.DISABLED)
                confirm_check.config(state=tk.NORMAL if selected_command.get() not in ["watch"] else tk.DISABLED)

            # 初始命令说明
            update_description()
            selected_command.trace_add("write", update_extra_options) # 监听所选命令的变化
            update_extra_options() # 初始化状态 -  移动到 组件定义之后

            # 确定按钮
            def on_ok():
                command_type = selected_command.get()
                extra_args = {}
                if no_detect_var.get():
                    extra_args["no_detect"] = True
                if no_trim_var.get():
                    extra_args["no_trim"] = True
                if port_var.get():
                    extra_args["port"] = port_var.get()
                if confirm_var.get():
                    extra_args["confirm"] = False #  False 相当于 -y 参数

                #  配置验证
                missing_configs_提示信息 = { #  更清晰的提示信息
                    "extract": ["条目文件夹", "世界书 JSON 文件"],
                    "push": ["条目文件夹", "世界书 JSON 文件"],
                    "watch": ["条目文件夹", "世界书 JSON 文件"],
                    "pull": ["条目文件夹", "世界书 JSON 文件"],
                    "to_json": ["条目文件夹", "世界书 JSON 文件"],
                    "to_yaml": ["条目文件夹", "世界书 JSON 文件"],
                    "publish": ["条目文件夹", "世界书 JSON 文件"] 
                }
                necessary_configs = missing_configs_提示信息.get(command_type, []) #  获取当前命令的必要配置

                missing_configs = []
                for config_key_name in necessary_configs: #  循环检查必要配置
                    config_value = None #  根据 config_key_name 获取配置值
                    if config_key_name == "条目文件夹":
                        config_value = world_data.get("directory")
                    elif config_key_name == "世界书 JSON 文件":
                        config_value = world_data.get("json_file")

                    if not config_value: #  检查配置值是否为空
                        missing_configs.append(config_key_name)

                if command_type == "publish": # publish 命令的特殊配置检查 (建议配置)
                    if not world_data.get("publish_directory"):
                        missing_configs.append("发布文件夹 (建议)") #  添加 "(建议)" 提示
                    if not world_data.get("character_card"):
                        missing_configs.append("角色卡 (建议)")
                    if not world_data.get("quick_replies"):
                        missing_configs.append("快速回复 (建议)")
                    if not world_data.get("script_directory"):
                        missing_configs.append("前端脚本文件夹 (建议)")

                if missing_configs:
                    warning_message = f"执行当前命令需要配置: \n\n" + ", ".join(missing_configs) #  更通用的提示信息
                    if "建议" in warning_message:
                        warning_message +=  "\n\n部分为建议配置，缺失可能影响打包完整性。" #  publish 命令的额外提示
                    else:
                        warning_message += "\n\n缺少必要配置将导致脚本运行出错，请检查配置。" #  其他命令的提示

                    # 兼容旧版本 Tkinter，使用 showwarning 或 warning
                    if hasattr(messagebox, 'warning'):
                        messagebox.warning("配置提示", warning_message) #  更友好的标题
                    else:
                        messagebox.showwarning("配置提示", warning_message) #  兼容旧版本

                    return #  阻止复制命令

                command_str = build_command_string(command_type, selected_name, world_data, extra_args)

                root.clipboard_clear()
                root.clipboard_append(command_str)
                messagebox.showinfo("提示", f"命令 '{command_str}' 已复制到剪贴板")
                dialog.destroy()

            ok_button = tk.Button(dialog_frame, text="确定", command=on_ok, width=10) #  放在 dialog_frame 中
            ok_button.grid(row=0, column=2, sticky=tk.NE + tk.S, padx=10, pady=10, rowspan=1) # 使用 grid 布局, 占据一行

            dialog.wait_window(dialog)
       except IndexError:
            pass

    button_width = 15
    description_button = tk.Button(root, text="脚本说明", command=show_description, width=button_width) # 修改按钮文本
    description_button.pack(pady=5)

    add_button = tk.Button(root, text="添加世界书", command=add_world_entry, width=button_width)
    add_button.pack(pady=5)
    edit_button = tk.Button(root, text="编辑世界书", command=edit_world_entry, width=button_width)
    edit_button.pack(pady=5)
    delete_button = tk.Button(root, text="删除世界书", command=delete_world_entry, width=button_width)
    delete_button.pack(pady=5)

    copy_button = tk.Button(root, text="复制命令", command=copy_command, width=button_width, state=tk.DISABLED) #  移除 预览命令 按钮
    copy_button.pack(pady=5)

    def update_button_state(event):
        """根据Treeview的选择状态更新按钮的启用/禁用状态"""
        if tree.selection():
            copy_button.config(state=tk.NORMAL) #  只启用 复制命令 按钮
        else:
            copy_button.config(state=tk.DISABLED) #  只禁用 复制命令 按钮

    tree.bind("<<TreeviewSelect>>", update_button_state)

    def save_config():
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            data_to_save = world_entries.copy()
            data_to_save[DIALOG_POSITIONS_KEY] = dialog_positions
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)

    def deselect_treeview(event):
        if tree.identify_region(event.x, event.y) == "nothing":
            tree.selection_set(())
            update_button_state(None) # 手动调用更新按钮状态，传入 None event

    tree.bind("<Button-1>", deselect_treeview)
    tree.bind("<Double-1>", lambda event: edit_world_entry())

    update_treeview()
    update_button_state(None) # 初始化按钮状态

    scrollbar = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree.configure(yscrollcommand=scrollbar.set)

    def scroll_treeview(event):
        if event.num == 4 or event.delta > 0:
            tree.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            tree.yview_scroll(1, "units")

    tree.bind("<MouseWheel>", scroll_treeview)
    tree.bind("<Button-4>", scroll_treeview)
    tree.bind("<Button-5>", scroll_treeview)

    root.mainloop()

def main():
    config_file_exists = os.path.exists(CONFIG_FILE)
    if not config_file_exists:
        message = f"配置文件 {CONFIG_FILE} 不存在。"
        if os.path.dirname(CONFIG_FILE) != os.getcwd():
            message += f"\n\n且 {CONFIG_FILE} 不在当前目录下。是否在当前目录创建新的配置文件？\n" \
                      f"(或者，请将此脚本移动到配置文件所在目录，然后重新运行)。"
        else:
            message += "\n\n是否创建新的配置文件？"

        response = messagebox.askyesno("提示", message, icon='warning')
        if response:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f)
        else:
            return

    root_path = get_root_path()
    if root_path:
        create_gui(root_path)

if __name__ == "__main__":
    main()