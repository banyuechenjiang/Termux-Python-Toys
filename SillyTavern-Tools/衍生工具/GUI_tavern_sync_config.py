# tavern_sync_config_gui.py (v5.2 - 发布文件夹默认路径修改)

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import json
import os
from pathlib import Path
import sys

CONFIG_FILE = "tavern_sync_config.json"
SCRIPT_DIR = Path(__file__).resolve().parent

CONFIG_DESCRIPTION = """
脚本说明 (tavern_sync_config_gui.py):

本脚本提供一个图形用户界面 (GUI)，用于创建和编辑 tavern_sync.py 脚本所需的配置文件 (tavern_sync_config.json)。

关键功能:

- 可视化配置: 通过友好的图形界面，无需手动编辑 JSON 文件即可管理世界书同步配置。
- 路径管理: 方便地浏览和选择世界书相关的文件和文件夹路径。
- 配置说明: 提供详细的配置字段说明和注意事项 (即本脚本说明)。
- 复制命令: 允许用户选择所有支持的 tavern_sync.py 命令，并可根据需要添加选项 (--no_detect, --no_trim, --port, -y)，一键复制到剪贴板，方便在终端中直接执行。

配置文件 (tavern_sync_config.json) 格式说明:

根对象是一个字典，键是“世界书名称”，值是包含以下字段的字典：

{
  "世界书名称": {
    "directory": "条目文件夹的绝对路径 (必填), 指向存放世界书条目分文件的文件夹",
    "json_file": "世界书 JSON 文件的绝对路径 (必填), 指向 SillyTavern data 目录下的世界书 JSON 文件",
    "user_name": "你的用户名 (可选), 填入后同步时会自动将名字替换为 <user>",
    "publish_directory": "发布文件夹的绝对路径 (可选), 指向希望将打包后的世界书文件存放的文件夹",
    "character_card": "角色卡文件路径 (可选), 角色卡文件路径",
    "quick_replies": [
      "快速回复路径1 (可选)",
      "快速回复路径2 (可选)"
    ],
    "script_directory": "前端助手源文件路径 (可选), 指向 tavern-frontend-助手 的 script 文件夹"
  }
}

字段说明:

- 世界书名称: 用于标识不同的世界书配置，应具有唯一性。在命令行中使用 tavern_sync.py 时，需要用到此名称。
- directory: 条目文件夹 的绝对路径 (必填), 用于存放世界书条目分文件的文件夹, GUI 中会显示为相对于脚本所在目录的相对路径。
    - 注意: `extract` 命令在条目文件夹不为空时无法使用，其他命令在条目文件夹为空时无法使用。
- json_file: 世界书 JSON 文件 的完整路径 (必填), 指向 SillyTavern data 目录下的世界书 JSON 文件, GUI 中仅显示文件名。
- user_name: 用户名 (可选)，你的用户名，同步时会被替换为 `<user>`。
- publish_directory: 发布文件夹 的绝对路径 (可选), 指向希望将打包后的世界书文件存放的文件夹, GUI 中仅显示文件名。
- character_card: 角色卡文件 路径 (可选)，角色卡文件路径，GUI 中仅显示文件名。
- quick_replies: 快速回复文件 路径 (可选)，快速回复文件路径，GUI 中仅显示文件名。
- script_directory: 前端助手源文件 路径 (可选)，指向 tavern-frontend-助手 的 script 文件夹，GUI 中会显示为相对于脚本所在目录的相对路径。

注意事项:

- 本脚本生成的配置文件 (tavern_sync_config.json) 与 tavern_sync.py 脚本配合使用。
- 请确保 SillyTavern 根目录设置正确。
- 配置文件中的路径请使用绝对路径，GUI 会根据情况显示相对路径或文件名以简化界面。
- "条目文件夹" 和 "世界书 JSON 文件"  是 tavern_sync.py 脚本运行的必要配置，请务必正确填写。
- 可选配置项如果值为空，保存时会自动删除对应键，避免 tavern_sync.py 脚本出现意外错误。
- 使用 "复制命令" 功能，您可以方便地将 tavern_sync.py 命令复制到剪贴板，然后在终端中执行。
"""

COMMAND_DESCRIPTIONS = {
    "extract": "命令: extract <世界书名称> [选项]\n\n"
               "  将世界书提取成独立文件，条目文件夹 用于存放提取出的文件。\n\n"
               "  -  选项:\n"
               "      --no_detect: 禁用格式自动检测，所有条目提取为 .md 文件。\n"
               "      -y: 免确认执行。",
    "push":    "命令: push <世界书名称> [选项]\n\n"
               "  将独立文件推送到世界书，条目文件夹 指向存放独立文件的位置。\n\n"
               "  -  选项:\n"
               "      --no_trim: 推送时不压缩条目内容。\n"
               "      -y: 免确认执行。",
    "watch":   "命令: watch <世界书名称> [选项]\n\n"
               "  实时监听文件改动并自动推送，条目文件夹 指向存放独立文件的位置。\n\n"
               "  -  选项:\n"
               "      --no_trim: 监听推送时不压缩条目内容。\n"
               "      --port <端口号>: 指定监听端口 (默认: 6620)。",
    "pull":    "命令: pull <世界书名称> [选项]\n\n"
               "  将世界书条目拉取到独立文件，条目文件夹 用于存放拉取的文件。\n\n"
               "  -  选项:\n"
               "      -y: 免确认执行。",
    "publish": "命令: publish <世界书名称> [选项]\n\n"
               "  打包世界书及相关资源，发布文件夹 用于指定打包文件的输出位置。\n\n"
               "  -  选项:\n"
               "      -y: 免确认执行。",
    "to_json": "命令: to_json <世界书名称> [选项]\n\n"
               "  将 YAML 文件转换为 JSON 文件，条目文件夹 指向存放 YAML 文件的位置。\n\n"
               "  -  选项:\n"
               "      -y: 免确认执行。",
    "to_yaml": "命令: to_yaml <世界书名称> [选项]\n\n"
               "  将 JSON 文件转换为 YAML 文件，条目文件夹 指向存放 JSON 文件的位置。\n\n"
               "  -  选项:\n"
               "      -y: 免确认执行。"
}


class ConfigManager:
    """配置管理器，负责 tavern_sync_config.json 文件的加载和保存"""
    def __init__(self, config_file):
        self.config_file = config_file
        self.world_entries = {}
        self.load_config()

    def load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                self.world_entries = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.world_entries = {}

    def save_config(self):
        """保存配置文件"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.world_entries, f, indent=4, ensure_ascii=False)

    def get_world_entries(self):
        """获取世界书配置条目"""
        return self.world_entries

    def add_world_entry(self, name, data):
        """添加世界书配置条目"""
        self.world_entries[name] = data
        self.save_config()

    def update_world_entry(self, name, data):
        """更新世界书配置条目"""
        self.world_entries[name] = data
        self.save_config()

    def delete_world_entry(self, name):
        """删除世界书配置条目"""
        if name in self.world_entries:
            del self.world_entries[name]
            self.save_config()


class WorldEntryDialog(tk.Toplevel):
    """世界书配置条目编辑对话框"""
    def __init__(self, master, root_path, config_manager, world_name=None, entry_data=None):
        super().__init__(master)
        self.master = master
        self.root_path = root_path
        self.config_manager = config_manager
        self.world_name = world_name
        self.entry_data = entry_data
        self.result = None
        self.title("编辑世界书配置" if entry_data else "添加世界书配置")
        self.transient(master)
        self.grab_set()

        self._create_widgets()
        self._center_window() # 居中显示窗口

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.wait_window(self)

    def _center_window(self):
        """窗口居中显示"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"+{x}+{y}")


    def _create_widgets(self):
        """创建对话框组件"""
        frame = tk.Frame(self, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)
        # --- 世界书名称 ---
        tk.Label(frame, text="世界书名称:").grid(row=0, column=0, sticky=tk.W)
        self.name_var = tk.StringVar(value=self.world_name if self.world_name else "")
        name_entry = tk.Entry(frame, textvariable=self.name_var)
        name_entry.grid(row=0, column=1, sticky=tk.EW)
        if not self.world_name:
            tk.Label(frame, text="提示：此名称将作为 tavern_sync.py 脚本的标识符。\n例如：`python tavern_sync.py extract 此世界书名称`").grid(row=0, column=2, sticky=tk.W)

        # --- 条目文件夹 (directory) ---
        tk.Label(frame, text="条目文件夹 (directory):").grid(row=1, column=0, sticky=tk.W, pady=5)
        if self.entry_data:
            directory_path = self.entry_data.get("directory", "")
            if os.path.isabs(directory_path):
                try:
                    relative_path = os.path.relpath(directory_path, SCRIPT_DIR)
                    if not relative_path.startswith(".."):
                        directory_path = relative_path
                except ValueError:
                    pass
            self.directory_var = tk.StringVar(value=directory_path)
        else:
            default_dir_name = "【条目文件】" + "/" + (self.world_name if self.world_name else "")
            self.directory_var = tk.StringVar(value=str(Path(default_dir_name)))

        directory_entry = tk.Entry(frame, textvariable=self.directory_var)
        directory_entry.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=5)
        self._create_browse_button(frame, "浏览文件夹", 2, 2, lambda: self.directory_var.get(), self.directory_var)

        # --- 世界书 JSON 文件 (json_file) ---
        tk.Label(frame, text="世界书 JSON 文件 (json_file):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.json_file_var = tk.StringVar()
        if self.entry_data:
            json_file_path = self.entry_data.get("json_file", "")
            if json_file_path:
                self.json_file_var.set(os.path.basename(json_file_path))
        json_file_entry = tk.Entry(frame, textvariable=self.json_file_var)
        json_file_entry.grid(row=4, column=0, columnspan=2, sticky=tk.EW, padx=5)
        self._create_browse_button(frame, "浏览文件", 4, 2, lambda: str(Path(self.root_path) / "data" / "default-user" / "worlds"), self.json_file_var)

        # --- 用户名 (user_name) ---
        tk.Label(frame, text="用户名 (user_name):").grid(row=5, column=0, sticky=tk.W)
        self.user_name_var = tk.StringVar(value=self.entry_data.get("user_name", "<user>") if self.entry_data else "<user>")
        user_name_entry = tk.Entry(frame, textvariable=self.user_name_var)
        user_name_entry.grid(row=5, column=1, sticky=tk.EW)
        tk.Label(frame, text="提示：填入你<user>的名字，则同步时会自动将名字替换成<user>").grid(row=5, column=2, sticky=tk.W)

        # --- 发布文件夹 (publish_directory) ---
        tk.Label(frame, text="发布文件夹 (publish_directory):").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.publish_directory_var = tk.StringVar()
        if self.entry_data:
            publish_directory_path = self.entry_data.get("publish_directory", "")
            if publish_directory_path:
                self.publish_directory_var.set(os.path.basename(publish_directory_path))
        publish_directory_entry = tk.Entry(frame, textvariable=self.publish_directory_var)
        publish_directory_entry.grid(row=7, column=0, columnspan=2, sticky=tk.EW, padx=5)
        self._create_browse_button(frame, "浏览文件夹", 7, 2, lambda: str(SCRIPT_DIR), self.publish_directory_var) # 修改了这里

        # --- 角色卡 (character_card) ---
        tk.Label(frame, text="角色卡 (character_card):").grid(row=8, column=0, sticky=tk.W, pady=5)
        self.character_card_var = tk.StringVar()
        if self.entry_data:
            character_card_path = self.entry_data.get("character_card", "")
            if character_card_path:
                self.character_card_var.set(os.path.basename(character_card_path))
        character_card_entry = tk.Entry(frame, textvariable=self.character_card_var)
        character_card_entry.grid(row=9, column=0, columnspan=2, sticky=tk.EW, padx=5)
        self._browse_character_card(frame, 9, 2, lambda: str(Path(self.root_path) / "data" / "default-user" / "characters"), self.character_card_var)

        # --- 快速回复 (quick_replies) ---
        tk.Label(frame, text="快速回复 (quick_replies):").grid(row=10, column=0, sticky=tk.W)
        quick_replies_filenames = [os.path.basename(path) for path in self.entry_data.get("quick_replies", [])] if self.entry_data else []
        self.quick_replies_list_var = tk.Variable(value=quick_replies_filenames)
        self.quick_replies_listbox = tk.Listbox(frame, listvariable=self.quick_replies_list_var, height=3, selectmode=tk.SINGLE)
        self.quick_replies_listbox.grid(row=11, column=0, columnspan=4, sticky=tk.EW)

        add_button = tk.Button(frame, text="添加", command=self._add_quick_reply)
        add_button.grid(row=12, column=1, sticky="ew")
        remove_button = tk.Button(frame, text="移除", command=self._remove_quick_reply)
        remove_button.grid(row=12, column=2, sticky="ew")

        # --- 前端脚本文件夹 (script_directory) ---
        tk.Label(frame, text="前端脚本文件夹 (script_directory):").grid(row=13, column=0, sticky=tk.W, pady=5)
        if self.entry_data:
            script_directory_path = self.entry_data.get("script_directory", "")
            if os.path.isabs(script_directory_path):
                try:
                    relative_path = os.path.relpath(script_directory_path, SCRIPT_DIR)
                    if not relative_path.startswith(".."):
                        script_directory_path = relative_path
                except ValueError:
                    pass
            self.script_directory_var = tk.StringVar(value=script_directory_path)
        else:
            self.script_directory_var = tk.StringVar(value="")
        script_directory_entry = tk.Entry(frame, textvariable=self.script_directory_var)
        script_directory_entry.grid(row=14, column=0, columnspan=2, sticky=tk.EW, padx=5)
        self._create_browse_button(frame, "浏览文件夹", 14, 2, lambda: "", self.script_directory_var)

        # --- 确定/取消 按钮 ---
        button_width = 10
        ok_button = tk.Button(frame, text="确定", command=self.on_ok, width=button_width)
        ok_button.grid(row=15, column=1, sticky=tk.E, pady=5)
        cancel_button = tk.Button(frame, text="取消", command=self.on_cancel, width=button_width)
        cancel_button.grid(row=15, column=2, sticky=tk.W, pady=5)

        for i in range(4):
            frame.columnconfigure(i, weight=1)

        def update_default_directory(*args):
            default_directory = Path("【条目文件】") / self.name_var.get()
            self.directory_var.set(str(default_directory))
        self.name_var.trace_add("write", update_default_directory)

    def _create_browse_button(self, parent, text, row, column, initialdir_func, target_var, filetypes=[("JSON Files", "*.json")]):
        """创建浏览按钮"""
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

    def _browse_character_card(self, parent, row, column, initialdir_func, target_var):
        """创建角色卡浏览按钮"""
        def browse():
            initialdir = initialdir_func()
            selected_path = filedialog.askopenfilename(
                initialdir=initialdir if initialdir and os.path.exists(initialdir) else ""
            )
            if selected_path:
                target_var.set(selected_path)
                target_var.set(os.path.basename(selected_path))

        button = tk.Button(parent, text="浏览文件", command=browse)
        button.grid(row=row, column=column)

    def _add_quick_reply(self):
        """添加快速回复文件"""
        initialdir = Path(self.root_path) / "data" / "default-user" / "QuickReplies"
        file_path = filedialog.askopenfilename(initialdir=initialdir if initialdir.exists() else self.root_path, filetypes=[("JSON Files", "*.json")])
        if file_path:
            filename = os.path.basename(file_path)
            current_replies = list(self.quick_replies_list_var.get())
            if filename not in current_replies:
                current_replies.append(filename)
                self.quick_replies_list_var.set(current_replies)

    def _remove_quick_reply(self):
        """移除快速回复文件"""
        selected_indices = self.quick_replies_listbox.curselection()
        if selected_indices:
            current_replies = list(self.quick_replies_list_var.get())
            current_replies.pop(selected_indices[0])
            self.quick_replies_list_var.set(current_replies)

    def on_ok(self):
        """点击确定按钮"""
        new_world_name = self.name_var.get()
        directory_path = self.directory_var.get()
        if not os.path.isabs(directory_path):
            directory_path = os.path.abspath(os.path.join(SCRIPT_DIR, directory_path))

        publish_directory_path = self.publish_directory_var.get()
        if publish_directory_path:
            if not os.path.isabs(publish_directory_path):
                publish_directory_path = os.path.abspath(os.path.join(SCRIPT_DIR, publish_directory_path))

        quick_replies_filenames = list(self.quick_replies_list_var.get())
        quick_replies_full_paths = []

        if self.entry_data and "quick_replies" in self.entry_data:
            for filename in quick_replies_filenames:
                original_path = next((path for path in self.entry_data["quick_replies"] if os.path.basename(path) == filename), None)
                quick_replies_full_paths.append(original_path or os.path.join(self.root_path, "data", "default-user", "QuickReplies", filename))
        else:
            quick_replies_full_paths = [os.path.join(self.root_path, "data", "default-user", "QuickReplies", filename) for filename in quick_replies_filenames]

        # 获取 json_file, character_card 的完整路径
        json_file_full_path = self.entry_data.get("json_file", "") if self.entry_data else ""
        if self.json_file_var.get():
            input_filename = self.json_file_var.get()
            if self.entry_data and "json_file" in self.entry_data and os.path.basename(self.entry_data["json_file"]) == input_filename:
                json_file_full_path = self.entry_data["json_file"]
            else:
                json_file_full_path = os.path.join(self.root_path, "data", "default-user", "worlds", input_filename)

        character_card_full_path = self.entry_data.get("character_card", "") if self.entry_data else ""
        if self.character_card_var.get():
            input_filename = self.character_card_var.get()
            if self.entry_data and "character_card" in self.entry_data and os.path.basename(self.entry_data["character_card"]) == input_filename:
                character_card_full_path = self.entry_data["character_card"]
            else:
                character_card_full_path = os.path.join(self.root_path, "data", "default-user", "characters", input_filename)

        script_directory_path = self.script_directory_var.get()
        if script_directory_path:
            if not os.path.isabs(script_directory_path):
                script_directory_path = os.path.abspath(os.path.join(SCRIPT_DIR, script_directory_path))

        entry_data_result = {
            "directory": directory_path,
            "json_file": json_file_full_path,
        }

        if self.user_name_var.get():
            entry_data_result["user_name"] = self.user_name_var.get()
        if publish_directory_path:
            entry_data_result["publish_directory"] = publish_directory_path
        if self.character_card_var.get():
            entry_data_result["character_card"] = character_card_full_path
        if quick_replies_full_paths:
            entry_data_result["quick_replies"] = quick_replies_full_paths
        if script_directory_path:
            entry_data_result["script_directory"] = script_directory_path

        # 删除值为空的可选配置项
        keys_to_delete = []
        for key, value in entry_data_result.items():
            if key not in ["directory", "json_file"] and not value: # 排除必填项
                keys_to_delete.append(key)
        for key in keys_to_delete:
            del entry_data_result[key]


        if not new_world_name or not entry_data_result["directory"] or not entry_data_result["json_file"]:
            messagebox.showerror("错误", "世界书名称、条目文件夹、JSON 文件为必填项。")
            return

        self.result = (new_world_name, entry_data_result)
        self.destroy()

    def on_cancel(self):
        """点击取消按钮"""
        self.result = None
        self.destroy()


class CommandDialog(tk.Toplevel):
    """复制命令对话框"""
    def __init__(self, master, world_name, world_data):
        super().__init__(master)
        self.master = master
        self.world_name = world_name
        self.world_data = world_data
        self.title("复制命令")
        self.transient(master)
        self.grab_set()
        self.geometry("800x500")

        self._create_widgets()
        self.wait_window(self)

    def _create_widgets(self):
        """创建对话框组件"""
        dialog_frame = tk.Frame(self)
        dialog_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        dialog_frame.columnconfigure(0, weight=1)
        dialog_frame.columnconfigure(1, weight=1)
        dialog_frame.columnconfigure(2, weight=1)
        dialog_frame.rowconfigure(1, weight=1)

        # 命令列表 Frame
        commands_frame = tk.Frame(dialog_frame)
        commands_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=5)
        tk.Label(commands_frame, text="命令列表:").pack(anchor=tk.W)

        # 参数选项 Frame
        options_frame = tk.Frame(dialog_frame)
        options_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=5)
        tk.Label(options_frame, text="参数选项:").pack(anchor=tk.W)

        # 命令说明 Frame
        description_frame = tk.Frame(dialog_frame)
        description_frame.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=10, pady=5)
        tk.Label(description_frame, text="命令说明:").pack(anchor=tk.W)
        self.description_text = tk.Text(description_frame, wrap=tk.WORD, height=5, state=tk.DISABLED)
        self.description_text.pack(fill=tk.BOTH, expand=True)

        self.selected_command = tk.StringVar(value="extract")

        def update_description(*args):
            command = self.selected_command.get()
            description = COMMAND_DESCRIPTIONS.get(command, "No description available.")
            self.description_text.config(state=tk.NORMAL)
            self.description_text.delete("1.0", tk.END)
            self.description_text.insert(tk.END, description)
            self.description_text.config(state=tk.DISABLED)

        commands = ["extract", "push", "watch", "pull", "publish", "to_json", "to_yaml"]
        for i, command in enumerate(commands):
            rb = tk.Radiobutton(commands_frame, text=command, variable=self.selected_command, value=command, command=update_description)
            rb.pack(anchor=tk.W)

        self.no_detect_var = tk.BooleanVar(value=False)
        no_detect_check = tk.Checkbutton(options_frame, text="--no_detect (禁用格式检测)", variable=self.no_detect_var)
        no_detect_check.pack(anchor=tk.W)

        self.no_trim_var = tk.BooleanVar(value=False)
        no_trim_check = tk.Checkbutton(options_frame, text="--no_trim (不压缩内容)", variable=self.no_trim_var)
        no_trim_check.pack(anchor=tk.W)

        port_frame = tk.Frame(options_frame)
        port_frame.pack(anchor=tk.W)
        tk.Label(port_frame, text="--port (端口):").pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value="6620")
        port_entry = tk.Entry(port_frame, textvariable=self.port_var, width=5)
        port_entry.pack(side=tk.LEFT)

        self.confirm_var = tk.BooleanVar(value=False)
        confirm_check = tk.Checkbutton(options_frame, text="-y (无需确认)", variable=self.confirm_var)
        confirm_check.pack(anchor=tk.W)

        def update_extra_options(*args):
            no_detect_check.config(state=tk.NORMAL if self.selected_command.get() == "extract" else tk.DISABLED)
            no_trim_check.config(state=tk.NORMAL if self.selected_command.get() in ["push", "watch"] else tk.DISABLED)
            port_entry.config(state=tk.NORMAL if self.selected_command.get() == "watch" else tk.DISABLED)
            confirm_check.config(state=tk.NORMAL if self.selected_command.get() not in ["watch"] else tk.DISABLED)

        update_description()
        self.selected_command.trace_add("write", update_extra_options)
        update_extra_options()

        ok_button = tk.Button(dialog_frame, text="确定", command=self.on_ok, width=10)
        ok_button.grid(row=0, column=2, sticky=tk.NE + tk.S, padx=10, pady=10, rowspan=1)

    def build_command_string(self, command_type, world_name, world_data, extra_args=None):
        """构建命令行字符串"""
        command = ["python", "tavern_sync.py", command_type, world_name]

        if extra_args:
           if extra_args.get("no_detect"):
                command.append("--no_detect")
           if extra_args.get("no_trim"):
                command.append("--no_trim")
           if command_type == "watch" and extra_args.get("port"):
                command.extend(["--port", str(extra_args.get("port"))])
           if extra_args.get("confirm") is False:
                command.append("-y")
        return " ".join(command)

    def on_ok(self):
        """点击确定按钮，复制命令到剪贴板"""
        command_type = self.selected_command.get()
        extra_args = {}
        if self.no_detect_var.get():
            extra_args["no_detect"] = True
        if self.no_trim_var.get():
            extra_args["no_trim"] = True
        if self.port_var.get():
            extra_args["port"] = self.port_var.get()
        if self.confirm_var.get():
            extra_args["confirm"] = False

        command_str = self.build_command_string(command_type, self.world_name, self.world_data, extra_args)

        self.master.clipboard_clear()
        self.master.clipboard_append(command_str)
        messagebox.showinfo("提示", f"命令 '{command_str}' 已复制到剪贴板")
        self.destroy()


class MainApp(tk.Tk):
    """主应用程序类"""
    def __init__(self, root_path):
        super().__init__()
        self.root_path = root_path
        self.title("Tavern Sync 配置助手")
        self.geometry("800x600")
        font_size = 12
        default_font = ("微软雅黑", font_size) # 默认字体设置为 微软雅黑
        self.default_font = default_font
        self.option_add("*Font", default_font)

        style = ttk.Style()
        style.configure("Treeview.Heading", font=('微软雅黑', font_size)) # Treeview Heading 字体设置为 微软雅黑
        style.configure("Treeview", font=('微软雅黑', font_size), rowheight=int(font_size * 2.2)) # Treeview 字体设置为 微软雅黑

        self.config_manager = ConfigManager(CONFIG_FILE)
        self.world_entries = self.config_manager.get_world_entries()

        tk.Label(self, text="双击条目进行编辑", font=("微软雅黑", font_size, "italic")).pack(pady=5)

        self.tree = ttk.Treeview(self, columns=("世界书名称",), show="headings")
        self.tree.heading("世界书名称", text="世界书名称")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.description_button = tk.Button(self, text="脚本说明", command=self.show_description, width=15)
        self.description_button.pack(pady=5)
        self.add_button = tk.Button(self, text="添加世界书", command=self.add_world_entry, width=15)
        self.add_button.pack(pady=5)
        self.edit_button = tk.Button(self, text="编辑世界书", command=self.edit_world_entry, width=15)
        self.edit_button.pack(pady=5)
        self.delete_button = tk.Button(self, text="删除世界书", command=self.delete_world_entry, width=15)
        self.delete_button.pack(pady=5)
        self.copy_button = tk.Button(self, text="复制命令", command=self.copy_command, width=15, state=tk.DISABLED)
        self.copy_button.pack(pady=5)

        self.tree.bind("<<TreeviewSelect>>", self.update_button_state)
        self.tree.bind("<Button-1>", self.deselect_treeview)
        self.tree.bind("<Double-1>", lambda event: self.edit_world_entry())

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<MouseWheel>", self.scroll_treeview)
        self.tree.bind("<Button-4>", self.scroll_treeview)
        self.tree.bind("<Button-5>", self.scroll_treeview)

        self.update_treeview()
        self.update_button_state(None)

    def update_treeview(self):
        """更新 Treeview 显示"""
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.world_entries = self.config_manager.get_world_entries()
        for name in self.world_entries:
            self.tree.insert("", tk.END, values=(name,))

    def show_description(self):
        """显示脚本说明"""
        desc_window = tk.Toplevel(self)
        desc_window.title("脚本说明")
        text_widget = tk.Text(desc_window, wrap=tk.WORD, padx=10, pady=10, font=self.default_font) # 脚本说明 Text 组件也使用默认字体 (微软雅黑)
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


    def add_world_entry(self):
        """添加世界书配置条目"""
        world_name = simpledialog.askstring("输入", "请输入世界书名称:\n此名称将作为 tavern_sync.py 脚本的标识符。\n例如：`python tavern_sync.py extract 此世界书名称`")
        if not world_name:
            return
        if world_name in self.world_entries:
            messagebox.showerror("错误", f"世界书名称 '{world_name}' 已存在，请使用不同的名称。")
            return

        dialog = WorldEntryDialog(self, self.root_path, self.config_manager, world_name=world_name)
        if dialog.result:
            name, data = dialog.result
            self.config_manager.add_world_entry(name, data)
            self.update_treeview()

    def edit_world_entry(self):
        """编辑世界书配置条目"""
        try:
            selected_item = self.tree.selection()[0]
            selected_name = self.tree.item(selected_item, "values")[0]

            if selected_name not in self.world_entries:
                messagebox.showerror("错误", f"世界书名称 '{selected_name}' 的配置数据不存在。")
                return

            current_data = self.world_entries[selected_name]

            dialog = WorldEntryDialog(self, self.root_path, self.config_manager, world_name=selected_name, entry_data=current_data)
            if dialog.result:
                new_name, new_data = dialog.result
                if new_name != selected_name:
                    if new_name in self.world_entries:
                        messagebox.showerror("错误", f"世界书名称 '{new_name}' 已存在，请使用不同的名称。")
                        return
                    self.config_manager.delete_world_entry(selected_name)
                    self.config_manager.add_world_entry(new_name, new_data)
                else:
                    self.config_manager.update_world_entry(new_name, new_data)
                self.update_treeview()
        except IndexError:
            pass
        except KeyError as e:
            messagebox.showerror("错误", f"配置数据错误：{e}。请尝试删除配置文件后重试。")

    def delete_world_entry(self):
        """删除世界书配置条目"""
        try:
            selected_item = self.tree.selection()[0]
            selected_name = self.tree.item(selected_item, "values")[0]
            if messagebox.askyesno("确认", f"确定要删除世界书 '{selected_name}' 的配置吗？"):
                self.config_manager.delete_world_entry(selected_name)
                self.update_treeview()
        except IndexError:
            pass

    def copy_command(self):
        """复制命令"""
        try:
            selected_item = self.tree.selection()[0]
            selected_name = self.tree.item(selected_item, "values")[0]
            world_data = self.world_entries[selected_name]

            dialog = CommandDialog(self, selected_name, world_data)

        except IndexError:
            pass

    def update_button_state(self, event):
        """更新按钮状态"""
        if self.tree.selection():
            self.copy_button.config(state=tk.NORMAL)
        else:
            self.copy_button.config(state=tk.DISABLED)

    def deselect_treeview(self, event):
        """取消 Treeview 选择"""
        if self.tree.identify_region(event.x, event.y) == "nothing":
            self.tree.selection_set(())
            self.update_button_state(None)

    def scroll_treeview(self, event):
        """滚动 Treeview"""
        if event.num == 4 or event.delta > 0:
            self.tree.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.tree.yview_scroll(1, "units")


def get_root_path():
    """获取 SillyTavern 根路径"""
    def extract_root_from_path(file_path):
        current_path = Path(file_path)
        while current_path != current_path.parent:
            expected_path = current_path / "data" / "default-user" / "worlds"
            if expected_path.exists() and expected_path.is_dir():
                return str(current_path)
            current_path = current_path.parent
        return None

    try:
        config_manager = ConfigManager(CONFIG_FILE)
        world_entries = config_manager.get_world_entries()
        for entry_data in world_entries.values():
            json_file = entry_data.get("json_file")
            if json_file:
                root_path = extract_root_from_path(json_file)
                if root_path:
                    return root_path
    except:
        pass

    def find_worlds_dir():
        """查找 worlds 目录"""
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


def main():
    """主函数"""
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

    config_manager = ConfigManager(CONFIG_FILE)
    root_path = get_root_path()
    if root_path:
        app = MainApp(root_path)
        app.mainloop()

if __name__ == "__main__":
    main()