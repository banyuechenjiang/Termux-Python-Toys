import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import yaml
import os
import sys
import subprocess
from pathlib import Path
import time
import shutil
import locale

CONFIG_FILE = "tavern_sync_config.yaml"
SCRIPT_DIR = Path(__file__).resolve().parent

SILLY_TAVERN_ROOT_HINT = r"D:\release\SillyTavern"
BASE_FONT_SIZE = 13
ROW_HEIGHT_MULTIPLIER = 2.2

CONFIG_DESCRIPTION = """
GUI 脚本说明 (tavern_sync_gui.py):

本脚本提供一个图形用户界面 (GUI)，用于创建和编辑新版 tavern_sync.py 脚本所需的配置文件 (tavern_sync_config.yaml)，并能直接调用核心脚本执行命令。

关键功能:

- 可视化配置: 通过图形界面管理 YAML 配置文件，无需手动编辑。
- 智能填充: 添加新配置时，选择世界书文件后，会自动填充配置名称和本地文件夹路径。
- 路径管理: 方便地浏览和选择文件与文件夹路径。
- 直接运行: 可在 GUI 中选择命令及参数，并一键在新的 PowerShell 窗口中运行，实时查看输出。
- 快速提取: 提供一个无需配置的“快速提取”功能，可将单个世界书文件快速分解为 .txt 文件，并能处理非法文件名。

配置文件 (tavern_sync_config.yaml) 格式说明:

根对象是一个字典，键是唯一的“配置名称”，值是包含以下字段的字典：

{
  "你的配置名称": {
    "世界书本地文件夹": "path/to/your/lorebook_entries_folder",
    "世界书酒馆文件": "path/to/your/lorebook.json",
    "玩家名": "你的对话内名字",
    "发布目标文件夹": "path/to/your/publish_folder",
    "角色卡": "path/to/your/character_card.png",
    "源文件文件夹": "path/to/your/source_files_for_publishing"
  }
}
"""

COMMAND_DESCRIPTIONS = {
    "extract": "命令: extract <配置名称> [选项]\n\n将世界书提取成独立文件。\n\n- 选项:\n  --no_detect: 禁用格式自动检测，所有条目提取为 .md 文件。\n  --group: 将 标题'合集名&条目名' 格式的条目，合并为合集文件。",
    "push": "命令: push <配置名称> [选项]\n\n将独立文件推送到世界书。\n\n- 选项:\n  --no_trim: 推送时不压缩条目内容。",
    "watch": "命令: watch <配置名称> [选项]\n\n实时监听文件改动并自动推送。\n\n- 选项:\n  --no_trim: 监听推送时不压缩条目内容。\n  --port <端口号>: 指定监听端口 (默认: 6620)。",
    "pull": "命令: pull <配置名称> [选项]\n\n将世界书条目拉取到独立文件。",
    "publish": "命令: publish <配置名称> [选项]\n\n打包世界书及相关资源。\n\n- 选项:\n  --should_zip: 将源文件打包成 zip 文件而不是直接复制文件夹。",
    "to_json": "命令: to_json <配置名称> [选项]\n\n将 YAML 文件转换为 JSON 文件。",
    "to_yaml": "命令: to_yaml <配置名称> [选项]\n\n将 JSON 文件转换为 YAML 文件。",
}

def get_initial_worlds_path() -> str:
    if SILLY_TAVERN_ROOT_HINT:
        try:
            hint_path = Path(SILLY_TAVERN_ROOT_HINT)
            worlds_path = hint_path / "data" / "default-user" / "worlds"
            if worlds_path.exists() and worlds_path.is_dir():
                return str(worlds_path)
        except Exception:
            pass
    return str(SCRIPT_DIR)

class ConfigManager:
    def __init__(self, config_file):
        self.config_file = SCRIPT_DIR / config_file
        self.configs = {}
        self.load_config()

    def load_config(self):
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                self.configs = yaml.safe_load(f)
            if not isinstance(self.configs, dict):
                self.configs = {}
        except (FileNotFoundError, yaml.YAMLError):
            self.configs = {}

    def save_config(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            yaml.dump(self.configs, f, allow_unicode=True, sort_keys=False, indent=2)

    def get_configs(self):
        return self.configs

    def add_config(self, name, data):
        self.configs[name] = data
        self.save_config()

    def delete_config(self, name):
        if name in self.configs:
            del self.configs[name]
            self.save_config()

class WorldEntryDialog(tk.Toplevel):
    def __init__(self, master, config_manager, config_name=None, entry_data=None):
        super().__init__(master)
        self.master = master
        self.config_manager = config_manager
        self.config_name = config_name
        self.entry_data = entry_data if entry_data is not None else {}
        self.result = None
        self.title("编辑配置" if entry_data else "添加配置")
        self.transient(master)
        self.grab_set()
        self.vars = {
            "config_name": tk.StringVar(value=self.config_name or ""),
            "世界书本地文件夹": tk.StringVar(value=self.entry_data.get("世界书本地文件夹", "")),
            "世界书酒馆文件": tk.StringVar(value=self.entry_data.get("世界书酒馆文件", "")),
            "玩家名": tk.StringVar(value=self.entry_data.get("玩家名", "<user>")),
            "发布目标文件夹": tk.StringVar(value=self.entry_data.get("发布目标文件夹", "")),
            "角色卡": tk.StringVar(value=self.entry_data.get("角色卡", "")),
            "源文件文件夹": tk.StringVar(value=self.entry_data.get("源文件文件夹", "")),
        }
        self._create_widgets()
        self.update_idletasks()
        self._center_window()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.wait_window(self)

    def _center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def _create_widgets(self):
        frame = ttk.Frame(self, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="配置名称 (必填):").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(frame, textvariable=self.vars["config_name"], width=60).grid(row=0, column=1, sticky=tk.EW, pady=3)
        fields = [("世界书本地文件夹", "浏览文件夹", "directory"), ("世界书酒馆文件", "浏览文件", "file"), ("玩家名", None, None), ("发布目标文件夹", "浏览文件夹", "directory"), ("角色卡", "浏览文件", "file"), ("源文件文件夹", "浏览文件夹", "directory")]
        for i, (label, browse_text, browse_type) in enumerate(fields, 1):
            ttk.Label(frame, text=f"{label}:").grid(row=i, column=0, sticky=tk.W, pady=3)
            ttk.Entry(frame, textvariable=self.vars[label], width=60).grid(row=i, column=1, sticky=tk.EW, pady=3)
            if browse_text:
                ttk.Button(frame, text=browse_text, command=lambda v=self.vars[label], t=browse_type, k=label: self._browse(v, t, k)).grid(row=i, column=2, sticky=tk.W, padx=5)
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=len(fields)+1, column=0, columnspan=3, pady=15)
        ttk.Button(button_frame, text="确定", command=self.on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.on_cancel).pack(side=tk.LEFT, padx=5)
        frame.columnconfigure(1, weight=1)

    def _browse(self, var, browse_type, field_key):
        initial_dir = get_initial_worlds_path() if field_key == "世界书酒馆文件" else str(SCRIPT_DIR)
        path = filedialog.askdirectory(initialdir=initial_dir) if browse_type == "directory" else filedialog.askopenfilename(initialdir=initial_dir)
        if path:
            var.set(path)
            if field_key == "世界书酒馆文件":
                file_path = Path(path)
                base_name = file_path.stem
                if not self.vars["config_name"].get().strip():
                    self.vars["config_name"].set(base_name)
                local_folder_path = SCRIPT_DIR / f"{base_name}-本地文件"
                self.vars["世界书本地文件夹"].set(str(local_folder_path))

    def on_ok(self):
        new_name = self.vars["config_name"].get().strip()
        if not new_name:
            messagebox.showerror("错误", "配置名称不能为空。", parent=self)
            return
        data = {}
        for key, var in self.vars.items():
            if key == "config_name": continue
            value = var.get().strip()
            if value: data[key] = value
        
        if not data.get("世界书本地文件夹"):
            messagebox.showerror("错误", "“世界书本地文件夹”为必填项。", parent=self)
            return
            
        self.result = (new_name, data)
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()

class CommandDialog(tk.Toplevel):
    def __init__(self, master, config_name):
        super().__init__(master)
        self.master = master
        self.config_name = config_name
        self.action = None
        self.command_string = ""
        self.selected_command_str = ""
        self.title(f"为 '{config_name}' 选择命令")
        self.transient(master)
        self.grab_set()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.wait_window(self)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        left_pane = ttk.Frame(main_frame)
        left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        right_pane = ttk.Frame(main_frame)
        right_pane.pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Label(left_pane, text="选择命令:").pack(anchor=tk.W)
        self.selected_command = tk.StringVar(value="push")
        for cmd in COMMAND_DESCRIPTIONS.keys():
            ttk.Radiobutton(left_pane, text=cmd, variable=self.selected_command, value=cmd, command=self._update_ui).pack(anchor=tk.W)
        ttk.Label(left_pane, text="\n参数选项:").pack(anchor=tk.W)
        self.vars = {"no_detect": tk.BooleanVar(value=True), "no_trim": tk.BooleanVar(value=True), "should_zip": tk.BooleanVar(value=True), "y": tk.BooleanVar(value=True), "port": tk.StringVar(value="6620"), "group": tk.BooleanVar(value=False)}
        self.checks = {
            "no_detect": ttk.Checkbutton(left_pane, text="--no_detect", variable=self.vars["no_detect"]), 
            "group": ttk.Checkbutton(left_pane, text="--group (合并合集)", variable=self.vars["group"]),
            "no_trim": ttk.Checkbutton(left_pane, text="--no_trim", variable=self.vars["no_trim"]), 
            "should_zip": ttk.Checkbutton(left_pane, text="--should_zip", variable=self.vars["should_zip"])
        }
        for check in self.checks.values(): check.pack(anchor=tk.W)
        port_frame = ttk.Frame(left_pane)
        port_frame.pack(anchor=tk.W, pady=2)
        ttk.Label(port_frame, text="--port:").pack(side=tk.LEFT)
        self.port_entry = ttk.Entry(port_frame, textvariable=self.vars["port"], width=8)
        self.port_entry.pack(side=tk.LEFT)
        ttk.Checkbutton(left_pane, text="-y (免确认)", variable=self.vars["y"]).pack(anchor=tk.W)
        desc_frame = ttk.LabelFrame(right_pane, text="命令说明", padding="10")
        desc_frame.pack(fill=tk.BOTH, expand=True)
        self.desc_text = tk.Text(desc_frame, wrap=tk.WORD, width=50, height=15, relief=tk.FLAT)
        self.desc_text.pack(fill=tk.BOTH, expand=True)
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(15, 0))
        ttk.Button(button_frame, text="运行", command=lambda: self.on_ok("run")).pack(side=tk.LEFT, expand=True, padx=5, ipady=5)
        ttk.Button(button_frame, text="复制", command=lambda: self.on_ok("copy")).pack(side=tk.LEFT, expand=True, padx=5, ipady=5)
        self._update_ui()

    def _update_ui(self):
        cmd = self.selected_command.get()
        self.desc_text.config(state=tk.NORMAL)
        self.desc_text.delete("1.0", tk.END)
        self.desc_text.insert("1.0", COMMAND_DESCRIPTIONS.get(cmd, ""))
        self.desc_text.config(state=tk.DISABLED)
        self.checks["no_detect"].config(state=tk.NORMAL if cmd == "extract" else tk.DISABLED)
        self.checks["group"].config(state=tk.NORMAL if cmd == "extract" else tk.DISABLED)
        self.checks["no_trim"].config(state=tk.NORMAL if cmd in ["push", "watch"] else tk.DISABLED)
        self.checks["should_zip"].config(state=tk.NORMAL if cmd == "publish" else tk.DISABLED)
        self.port_entry.config(state=tk.NORMAL if cmd == "watch" else tk.DISABLED)

    def on_ok(self, action_type):
        cmd = self.selected_command.get()
        self.selected_command_str = cmd
        parts = ["python", "tavern_sync.py", cmd, f'"{self.config_name}"']
        if self.vars["no_detect"].get() and cmd == "extract": parts.append("--no_detect")
        if self.vars["group"].get() and cmd == "extract": parts.append("--group")
        if self.vars["no_trim"].get() and cmd in ["push", "watch"]: parts.append("--no_trim")
        if self.vars["should_zip"].get() and cmd == "publish": parts.append("--should_zip")
        if cmd == "watch": parts.append(f'--port {self.vars["port"].get()}')
        if self.vars["y"].get(): parts.append("-y")
        self.command_string = " ".join(parts)
        self.action = action_type
        self.destroy()

    def on_cancel(self):
        self.action = None
        self.destroy()

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tavern Sync 配置与运行助手 (v5.0)")
        self.geometry("900x650")
        default_font = ("微软雅黑", BASE_FONT_SIZE)
        self.option_add("*Font", default_font)
        style = ttk.Style(self)
        style.configure("Treeview.Heading", font=(default_font[0], BASE_FONT_SIZE, 'bold'))
        style.configure("Treeview", font=default_font, rowheight=int(BASE_FONT_SIZE * ROW_HEIGHT_MULTIPLIER))
        style.configure("Accent.TButton", foreground="blue")
        style.configure("TRadiobutton", font=default_font)
        style.configure("TCheckbutton", font=default_font)
        self.config_manager = ConfigManager(CONFIG_FILE)
        top_frame = ttk.Frame(self, padding="15 10")
        top_frame.pack(fill=tk.X)
        ttk.Label(top_frame, text="配置列表 (双击编辑)", font=(default_font[0], BASE_FONT_SIZE, "italic")).pack(side=tk.LEFT)
        center_frame = ttk.Frame(self, padding="15 0")
        center_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(center_frame, columns=("配置名称",), show="headings")
        self.tree.heading("配置名称", text="配置名称")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(center_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        button_frame = ttk.Frame(self, padding="15 15")
        button_frame.pack(fill=tk.X)
        button_padding = {"side": tk.LEFT, "padx": 5, "ipady": 5}
        ttk.Button(button_frame, text="快速提取", command=self.quick_extract, style="Accent.TButton").pack(**button_padding)
        ttk.Button(button_frame, text="脚本说明", command=self.show_description).pack(**button_padding)
        ttk.Button(button_frame, text="添加配置", command=self.add_config_entry).pack(**button_padding)
        ttk.Button(button_frame, text="编辑配置", command=self.edit_config_entry).pack(**button_padding)
        ttk.Button(button_frame, text="删除配置", command=self.delete_config_entry).pack(**button_padding)
        self.run_button = ttk.Button(button_frame, text="运行命令", command=self.run_command, state=tk.DISABLED)
        self.run_button.pack(side=tk.RIGHT, padx=5, ipady=5)
        self.tree.bind("<<TreeviewSelect>>", self.update_button_state)
        self.tree.bind("<Double-1>", lambda event: self.edit_config_entry())
        self.update_treeview()
        self.update_button_state(None)

    def _execute_powershell(self, command_str: str, wait: bool = False):
        if sys.platform != "win32":
            messagebox.showerror("错误", "此功能目前仅在 Windows 上受支持。", parent=self)
            return None
        try:
            pause_logic = "if ($LASTEXITCODE -ne 0) { pause }" if wait else ""
            full_command = f'powershell -Command "cd \'{SCRIPT_DIR}\'; {command_str}; {pause_logic}"'
            
            creation_flags = subprocess.CREATE_NEW_CONSOLE
            if wait:
                return subprocess.run(full_command, creationflags=creation_flags, check=False, capture_output=True, text=True, encoding=locale.getpreferredencoding(False))
            else:
                subprocess.Popen(full_command, creationflags=creation_flags)
                return None
        except Exception as e:
            messagebox.showerror("执行失败", f"无法启动 PowerShell 进程:\n{e}", parent=self)
            return subprocess.CompletedProcess(args=full_command, returncode=1) if wait else None

    def quick_extract(self):
        source_file = filedialog.askopenfilename(title="请选择世界书文件", initialdir=get_initial_worlds_path(), filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not source_file: return
        source_file_path = Path(source_file)
        target_path = SCRIPT_DIR / f"{source_file_path.stem}-快速提取"
        try:
            if not target_path.exists():
                target_path.mkdir(parents=True)
            elif any(target_path.iterdir()):
                if messagebox.askyesno("确认", f"目标文件夹 '{target_path}' 已存在且不是空的！\n是否要清空并继续？", parent=self):
                    shutil.rmtree(target_path)
                    target_path.mkdir()
                else:
                    return
        except OSError as e:
            messagebox.showerror("错误", f"无法创建或清空文件夹：\n{e}", parent=self)
            return
        temp_config_name = f"_quick_extract_{int(time.time())}"
        temp_config_data = {"世界书酒馆文件": str(source_file_path), "世界书本地文件夹": str(target_path)}
        try:
            self.config_manager.add_config(temp_config_name, temp_config_data)
            command_str = f'python tavern_sync.py extract "{temp_config_name}" --no_detect -y'
            result = self._execute_powershell(command_str, wait=True)
            if result and result.returncode == 0:
                renamed_count = self._rename_files_in_dir(target_path, ".md", ".txt")
                messagebox.showinfo("成功", f"提取成功！\n\n共 {renamed_count} 个文件已提取并重命名为 .txt，\n保存在：'{target_path}'", parent=self)
            elif result:
                error_output = result.stderr or result.stdout
                messagebox.showerror("提取失败", f"执行提取命令时发生错误。\n\n{error_output.strip()}", parent=self)
        finally:
            self.config_manager.load_config()
            self.config_manager.delete_config(temp_config_name)

    def _rename_files_in_dir(self, directory: Path, old_ext: str, new_ext: str) -> int:
        count = 0
        try:
            for filepath in directory.rglob(f"*{old_ext}"):
                if filepath.is_file():
                    new_filepath = filepath.with_suffix(new_ext)
                    filepath.rename(new_filepath)
                    count += 1
        except Exception as e:
            messagebox.showerror("重命名失败", f"重命名文件时出错: {e}", parent=self)
        return count

    def update_treeview(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        configs = self.config_manager.get_configs()
        for name in sorted(configs.keys()):
            if not name.startswith("_quick_extract_"):
                self.tree.insert("", tk.END, values=(name,), iid=name)

    def show_description(self):
        desc_window = tk.Toplevel(self)
        desc_window.title("脚本说明")
        width, height = 800, 600
        x, y = (self.winfo_screenwidth() // 2) - (width // 2), (self.winfo_screenheight() // 2) - (height // 2)
        desc_window.geometry(f'{width}x{height}+{x}+{y}')
        text_widget = tk.Text(desc_window, wrap=tk.WORD, padx=15, pady=15, relief=tk.FLAT, bg=desc_window.cget('bg'))
        text_widget.insert(tk.END, CONFIG_DESCRIPTION)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(fill=tk.BOTH, expand=True)

    def add_config_entry(self):
        dialog = WorldEntryDialog(self, self.config_manager)
        if dialog.result:
            name, data = dialog.result
            if name in self.config_manager.get_configs():
                messagebox.showerror("错误", f"配置名称 '{name}' 已存在。", parent=self)
                return
            self.config_manager.add_config(name, data)
            self.update_treeview()
            self.tree.selection_set(name)

    def edit_config_entry(self):
        selected_items = self.tree.selection()
        if not selected_items: return
        selected_name = selected_items[0]
        current_data = self.config_manager.get_configs().get(selected_name, {})
        dialog = WorldEntryDialog(self, self.config_manager, config_name=selected_name, entry_data=current_data)
        if dialog.result:
            new_name, new_data = dialog.result
            if new_name != selected_name:
                if new_name in self.config_manager.get_configs():
                    messagebox.showerror("错误", f"配置名称 '{new_name}' 已存在。", parent=self)
                    return
                self.config_manager.delete_config(selected_name)
            self.config_manager.add_config(new_name, new_data)
            self.update_treeview()
            self.tree.selection_set(new_name)

    def delete_config_entry(self):
        selected_items = self.tree.selection()
        if not selected_items: return
        selected_name = selected_items[0]
        if messagebox.askyesno("确认", f"确定要删除配置 '{selected_name}' 吗？", parent=self):
            self.config_manager.delete_config(selected_name)
            self.update_treeview()

    def _validate_config(self, config_data, command):
        def check_path(key, is_dir=False, is_file=False, must_exist=True):
            if key not in config_data or not config_data.get(key):
                return f"配置文件缺少 '{key}'"
            path = Path(config_data[key])
            if must_exist and not path.exists():
                return f"路径不存在: '{path}' (配置项: '{key}')"
            if is_dir and not path.is_dir():
                return f"路径不是一个文件夹: '{path}' (配置项: '{key}')"
            if is_file and not path.is_file():
                return f"路径不是一个文件: '{path}' (配置项: '{key}')"
            return None

        error = None
        if command in ['push', 'pull', 'watch', 'to_json', 'to_yaml']:
            error = check_path('世界书本地文件夹', is_dir=True)
        elif command == 'extract':
             error = check_path('世界书酒馆文件', is_file=True)
        elif command == 'publish':
            error = check_path('发布目标文件夹', must_exist=False)
            if not error and '角色卡' not in config_data and '源文件文件夹' not in config_data:
                error = "无可发布内容，需配置 '角色卡' 或 '源文件文件夹'"
            if not error and '角色卡' in config_data:
                error = check_path('角色卡', is_file=True)
            if not error and '源文件文件夹' in config_data:
                error = check_path('源文件文件夹', is_dir=True)
        
        if error: return False, error
        
        if command in ['push', 'pull', 'extract']:
             error = check_path('世界书酒馆文件', is_file=True)
        elif command == 'watch':
            if '世界书酒馆文件' not in config_data and '世界书名称' not in config_data:
                error = "watch 功能需要配置 '世界书酒馆文件' 或 '世界书名称'"
            elif '世界书酒馆文件' in config_data:
                 error = check_path('世界书酒馆文件', is_file=True)
        
        if error: return False, error

        return True, None

    def run_command(self):
        selected_items = self.tree.selection()
        if not selected_items: return
        selected_name = selected_items[0]
        dialog = CommandDialog(self, selected_name)
        if dialog.action:
            if dialog.action == "run":
                config_data = self.config_manager.get_configs()[selected_name]
                command_to_run = dialog.selected_command_str

                is_valid, error_msg = self._validate_config(config_data, command_to_run)
                if not is_valid:
                    messagebox.showerror("配置检查失败", f"无法执行 '{command_to_run}' 命令:\n\n{error_msg}", parent=self)
                    return 

                if command_to_run == 'extract':
                    lorebook_dir_str = config_data.get("世界书本地文件夹")
                    try:
                        Path(lorebook_dir_str).mkdir(parents=True, exist_ok=True)
                    except OSError as e:
                        messagebox.showerror("错误", f"无法创建文件夹：\n{lorebook_dir_str}\n\n{e}", parent=self)
                        return

                should_wait = command_to_run != 'watch'
                result = self._execute_powershell(dialog.command_string, wait=should_wait)

                if should_wait and result:
                    if result.returncode == 0:
                        messagebox.showinfo("成功", f"命令 '{dialog.selected_command_str}' 已成功执行。", parent=self)
                    else:
                        error_output = result.stderr or result.stdout
                        messagebox.showerror("失败", f"命令 '{dialog.selected_command_str}' 执行失败。\n请检查配置或查看终端输出。\n\n错误信息:\n{error_output.strip()}", parent=self)
                        
            elif dialog.action == "copy":
                self.clipboard_clear()
                self.clipboard_append(dialog.command_string)
                messagebox.showinfo("成功", f"命令已复制到剪贴板:\n\n{dialog.command_string}", parent=self)

    def update_button_state(self, event):
        self.run_button.config(state=tk.NORMAL if self.tree.selection() else tk.DISABLED)

def main():
    if not (SCRIPT_DIR / "tavern_sync.py").exists():
         messagebox.showwarning("警告", f"未在当前目录找到 'tavern_sync.py'。\n\n请确保本 GUI 脚本与 'tavern_sync.py' 放在同一文件夹下。")
    if not (SCRIPT_DIR / CONFIG_FILE).exists():
        if messagebox.askyesno("提示", f"配置文件 '{CONFIG_FILE}' 不存在，是否要创建一个空的配置文件？"):
            try:
                with open(SCRIPT_DIR / CONFIG_FILE, "w", encoding='utf-8') as f: yaml.dump({}, f)
            except IOError as e:
                messagebox.showerror("创建失败", f"无法创建配置文件: {e}")
                return
    app = MainApp()
    app.mainloop()

if __name__ == "__main__":
    main()
