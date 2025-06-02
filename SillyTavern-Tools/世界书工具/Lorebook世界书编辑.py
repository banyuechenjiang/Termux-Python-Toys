import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinter import font
from typing import Optional, List, Dict
import re


class WorldBookManager:
    """世界书数据管理类."""

    def __init__(self):
        """初始化 WorldBookManager."""
        self.worldbook_data = None
        self.current_file_path = None

        # 内部英文位置映射
        self.position_map_english = {
            "Before Char Defs": 0,
            "After Char Defs": 1,
            "Before Example Messages": 2,
            "After Example Messages": 3,
            "Top of AN": 4,
            "Bottom of AN": 5,
            "@ D": 6,
            "⚙️ - as a system role message": 7,
            "👤 - as a user role message": 8,
            "🤖 - as an assistant role message": 9,
        }
        # 中文显示位置映射
        self.position_map_chinese = {
            "角色定义前": "Before Char Defs",
            "角色定义后": "After Char Defs",
            "示例消息前": "Before Example Messages",
            "示例消息后": "After Example Messages",
            "作者注释 顶部": "Top of AN",
            "作者注释 底部": "Bottom of AN",
            "@ D": "@ D",
            "⚙️ - 系统角色消息": "⚙️ - as a system role message",
            "👤 - 用户角色消息": "👤 - as a user role message",
            "🤖 - 助手角色消息": "🤖 - as an assistant role message",
        }
        # 角色映射
        self.role_map = {
            "User": 0,
            "System": 1,
            "Assistant": 2,
        }
        # 常驻类型映射
        self.sticky_map = {
            "否": 0,
            "是": 1,
            "直到上下文满": 2,
        }
        # 选择逻辑映射
        self.selective_logic_map = {
            "AND ANY": 0,
            "AND ALL": 1,
            "NOT ANY": 2,
            "NOT ALL": 3,
            "与任意关键词匹配": "AND ANY",
            "与所有关键词匹配": "AND ALL",
            "不含任意关键词": "NOT ANY",
            "不含所有关键词": "NOT ALL",
        }

        self.position_options = list(self.position_map_chinese.keys())
        self.role_options = list(self.role_map.keys())
        self.sticky_options = list(self.sticky_map.keys())
        self.selective_logic_options = list(self.selective_logic_map.keys())
        self.selective_logic_options_chinese = ["与任意关键词匹配", "与所有关键词匹配", "不含任意关键词", "不含所有关键词"]

    def load_worldbook(self, file_path: str) -> bool:
        """从 JSON 文件加载世界书数据."""
        if not file_path:
            return False
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                self.worldbook_data = json.load(f)
                self.current_file_path = file_path
                return True
        except FileNotFoundError:
            messagebox.showerror("错误", f"文件未找到: {file_path}")
            return False
        except json.JSONDecodeError:
            messagebox.showerror("错误", f"JSON 解析错误: {file_path}")
            return False
        except Exception as e:
            messagebox.showerror("错误", f"加载文件时发生错误: {e}")
            return False

    def save_worldbook(self, file_path: Optional[str] = None) -> bool:
        """将世界书数据保存到 JSON 文件."""
        if not self.worldbook_data:
            messagebox.showerror("错误", "没有要保存的数据")
            return False

        if not file_path:
            file_path = self.current_file_path

        if not file_path:
            return False

        try:
            with open(file_path, "w", encoding="utf-8") as outfile:
                json.dump(self.worldbook_data, outfile, indent=2, ensure_ascii=False)
            self.current_file_path = file_path
            return True
        except Exception as e:
            messagebox.showerror("错误", f"保存文件失败: {e}")
            return False

    def create_entry(self, info: Optional[dict] = None) -> dict:
        """
        创建一个世界书条目
        :param info: 条目信息字典
        :return: 世界书条目对象
        """
        default_entry = {
            "uid": self._get_next_uid(),                 # "uid": "唯一 ID，整数类型"
            "key": [],                                   # "key": "触发条目的关键字列表，字符串数组"
            "keysecondary": [],                          # "keysecondary": "次要关键字列表，字符串数组"
            "comment": "",                               # "comment": "条目的注释或标题，字符串类型"
            "content": "",                               # "content": "插入到提示词的文本内容，字符串类型"
            "constant": False,                           # "constant": "是否常驻，布尔类型"
            "vectorized": False,                         # "vectorized": "是否仅向量匹配激活，布尔类型"
            "selective": True,                           # "selective": "是否启用选择性过滤，布尔类型"
            "selectiveLogic": 0,                         # "selectiveLogic": "选择性逻辑，整数类型 (0-3)"
            "addMemo": True,                             # "addMemo": "是否显示备注，布尔类型"
            "order": 100,                                # "order": "插入顺序，整数类型"
            "position": 1,                               # "position": "插入位置，整数类型 (0-9)"
            "disable": False,                            # "disable": "是否禁用，布尔类型"
            "excludeRecursion": False,                   # "excludeRecursion": "是否排除递归扫描，布尔类型"
            "preventRecursion": True,                    # "preventRecursion": "是否阻止递归扫描，布尔类型"
            "delayUntilRecursion": False,                # "delayUntilRecursion": "是否延迟到递归扫描，布尔类型"
            "probability": 100,                          # "probability": "插入概率 (0-100)，整数类型"
            "matchWholeWords": None,                     # "matchWholeWords": "是否匹配整个单词，布尔类型或 null"
            "useProbability": True,                      # "useProbability": "是否使用概率属性，布尔类型"
            "depth": 4,                                  # "depth": "深度，整数类型"
            "group": "",                                 # "group": "分组名称，字符串类型"
            "groupOverride": False,                      # "groupOverride": "是否覆盖分组，布尔类型"
            "groupWeight": 100,                          # "groupWeight": "分组权重，整数类型"
            "scanDepth": None,                           # "scanDepth": "扫描深度，整数类型或 null"
            "caseSensitive": None,                       # "caseSensitive": "是否区分大小写，布尔类型或 null"
            "useGroupScoring": None,                     # "useGroupScoring": "是否使用分组评分，布尔类型或 null"
            "automationId": "",                          # "automationId": "自动化 ID，字符串类型"
            "role": None,                                # "role": "角色消息类型，整数类型 (0-2) 或 null"
            "sticky": 0,                                 # "sticky": "常驻类型，整数类型 (0-2)"
            "cooldown": 0,                               # "cooldown": "冷却时间，整数类型"
            "delay": 0,                                  # "delay": "延迟时间，整数类型"
            "displayIndex": self._get_next_display_index() # "displayIndex": "显示索引，整数类型"
        }
        if info:
            merged_entry = default_entry.copy()
            merged_entry.update(info)
            for key, value in info.items():
                if key == "position" and value in self.position_map_english:
                    merged_entry[key] = self.position_map_english[value]
                elif key == "role" and value in self.role_map:
                    merged_entry[key] = self.role_map[value]
                elif key == "sticky" and value in self.sticky_map:
                    merged_entry[key] = self.sticky_map[value]
                elif key == "selectiveLogic" and value in self.selective_logic_map:
                    merged_entry[key] = self.selective_logic_map[value]
            return merged_entry
        return default_entry

    def update_entry(self, uid: int, updated_info: dict) -> bool:
        """Updates an existing worldbook entry."""
        if not self.worldbook_data or "entries" not in self.worldbook_data:
            messagebox.showerror("错误", "世界书数据未加载")
            return False

        for index, entry in self.worldbook_data["entries"].items():
            if entry["uid"] == uid:
                entry.update(updated_info)
                for key, value in updated_info.items():
                    if key == "position" and value in self.position_map_english:
                        entry[key] = self.position_map_english[value]
                    elif key == "role" and value in self.role_map:
                        entry[key] = self.role_map[value]
                    elif key == "sticky" and value in self.sticky_map:
                        entry[key] = self.sticky_map[value]
                    elif key == "selectiveLogic" and value in self.selective_logic_map:
                        entry[key] = self.selective_logic_map[value]
                return True
        messagebox.showerror("错误", f"未找到 UID 为 {uid} 的条目")
        return False

    def delete_entry(self, uid: int) -> bool:
        """Deletes a worldbook entry by UID."""
        if not self.worldbook_data or "entries" not in self.worldbook_data:
            print("Worldbook 数据未加载或 entries 不存在")
            return False

        print(f"尝试删除 UID: {uid}")
        print(f"当前 entries: {self.worldbook_data['entries'].keys()}")
        deleted = False
        for index, entry in list(self.worldbook_data["entries"].items()):
            if entry["uid"] == uid:
                print(f"找到匹配条目，索引: {index}, UID: {uid}")
                del self.worldbook_data["entries"][index]
                deleted = True
                break
        if deleted:
            print(f"UID: {uid} 删除成功")
            return True
        else:
            print(f"UID: {uid} 未找到")
            return False

    def get_entry_by_uid(self, uid: int) -> Optional[dict]:
        """Retrieves a worldbook entry by UID."""
        if not self.worldbook_data or "entries" not in self.worldbook_data:
            return None
        for entry in self.worldbook_data["entries"].values():
            if entry["uid"] == uid:
                return entry
        return None

    def _get_next_uid(self) -> int:
        """Returns the next available UID."""
        if not self.worldbook_data or "entries" not in self.worldbook_data:
            return 0
        uids = [entry["uid"] for entry in self.worldbook_data["entries"].values()]
        return max(uids) + 1 if uids else 0

    def _get_next_display_index(self) -> int:
        """Returns the next available display index."""
        if not self.worldbook_data or "entries" not in self.worldbook_data:
            return 0
        indices = [entry["displayIndex"]
                   for entry in self.worldbook_data["entries"].values()]
        return max(indices) + 1 if indices else 0

    def get_entries_list_display(self) -> List[str]:
        """Returns a list of entry display strings for UI listbox."""
        if not self.worldbook_data or "entries" not in self.worldbook_data:
            return []

        display_list = []
        for entry in self.worldbook_data["entries"].values():
            prefix = ""
            if entry.get("constant"):
                prefix += "[常驻] "
            if entry.get("disable"):
                prefix += "[禁用] "
            key_display = entry["key"][0] if entry["key"] else ""
            keysecondary_display = entry["keysecondary"][
                0] if entry["keysecondary"] else ""

            display_text = f"{prefix} {entry.get('uid', 'N/A')} - {key_display} - {keysecondary_display} ({entry['comment']})"
            display_list.append(display_text)
        return display_list


class WorldBookUI:
    """构建 SillyTavern 世界书编辑器 (Lorebook Editor) 的 Tkinter 用户界面."""

    def __init__(self, root, world_book_manager):
        """初始化 WorldBookUI."""
        self.world_book_manager = world_book_manager
        self.root = root
        self.root.title("SillyTavern 世界书编辑器") # 标题明确为世界书编辑器 (Lorebook Editor)
        self.root.geometry("1400x750")

        self.style = ttk.Style()
        self.setup_styles()

        self.use_advanced_mode = tk.BooleanVar(value=False)

        self.button_frame = ttk.Frame(self.root)
        self.edit_frame = ttk.Frame(self.root)
        self.notebook = ttk.Notebook(self.edit_frame)

        self.int_entries = {}
        self.str_entries = {}
        self.bool_vars = {}

        self.create_widgets()
        self.switch_edit_mode()
        self.update_entry_list()
        self.entry_listbox.bind("<<ListboxSelect>>", self.on_entry_select)

    def setup_styles(self):
        """Sets up UI styles."""
        self.style.configure("TButton", font=("Arial", 11))
        self.style.configure("TLabel", font=("Arial", 11))
        self.style.configure("TEntry", font=("Arial", 11))
        self.style.configure("Header.TLabel", font=("Arial", 16, "bold"))
        self.style.configure("TListbox", font=("Arial", 11))
        self.style.configure("TCombobox", font=("Arial", 11))
        self.style.configure("Section.TLabel", font=("Arial", 13, "bold"))

    def create_widgets(self):
        """Creates and arranges UI widgets."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="加载 Lorebook", command=self.load_worldbook) # 菜单项使用 Lorebook
        file_menu.add_command(label="保存 Lorebook", command=self.save_worldbook) # 菜单项使用 Lorebook
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="使用说明", command=self.show_instructions_gui)

        ttk.Label(self.root, text="SillyTavern 世界书编辑器 (Lorebook Editor)", # 标题明确为世界书编辑器 (Lorebook Editor)
                  style="Header.TLabel").pack(pady=10)

        self.entry_listbox = tk.Listbox(
            self.root, height=20, width=15, selectmode=tk.SINGLE, exportselection=False)
        self.entry_listbox.pack(side=tk.LEFT, padx=5,
                                 pady=10, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(
            self.root, orient="vertical", command=self.entry_listbox.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.entry_listbox.config(yscrollcommand=scrollbar.set)

        self.button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        self.create_button_widgets()

        self.edit_frame.pack(side=tk.RIGHT, padx=10,
                             pady=10, fill=tk.BOTH, expand=True)

        self.mode_check = ttk.Checkbutton(self.edit_frame, text="高级模式", variable=self.use_advanced_mode,
                                          command=self.switch_edit_mode)
        self.mode_check.pack(pady=5)

        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.create_edit_fields()

    def create_button_widgets(self):
        """创建按钮并放置在 button_frame 中"""
        self.save_button = ttk.Button(
            self.button_frame, text="保存条目", command=self.save_entry, state=tk.DISABLED
        )
        self.save_button.pack(side=tk.LEFT, padx=5)
        self.delete_button = ttk.Button(
            self.button_frame, text="删除条目", command=self.delete_entry, state=tk.DISABLED
        )
        self.delete_button.pack(side=tk.LEFT, padx=5)
        self.new_button = ttk.Button(
            self.button_frame, text="新建条目", command=self.new_entry
        )
        self.new_button.pack(side=tk.LEFT, padx=5)

    def switch_edit_mode(self):
        """切换简易/高级编辑模式."""
        self.create_edit_fields()
        selected_index = self.entry_listbox.curselection()
        if selected_index:
            selected_text = self.entry_listbox.get(selected_index[0])
            uid_match = re.search(r'(\d+) -', selected_text)
            if uid_match:
                uid = int(uid_match.group(1))
                entry = self.world_book_manager.get_entry_by_uid(uid)
                if entry:
                    self.populate_edit_fields(entry)

    def create_edit_fields(self):
        """根据编辑模式创建不同的编辑字段."""
        for tab_frame in self.notebook.winfo_children():
            tab_frame.destroy()

        basic_tab = ttk.Frame(self.notebook)
        advanced_tab = ttk.Frame(self.notebook)
        recursion_group_tab = ttk.Frame(self.notebook)
        numerical_bool_tab = ttk.Frame(self.notebook)

        self.notebook.add(basic_tab, text="基本信息")
        if self.use_advanced_mode.get():
            self.notebook.add(advanced_tab, text="高级选项")
            self.notebook.add(recursion_group_tab, text="递归 & 分组")
            self.notebook.add(numerical_bool_tab, text="数值 & 布尔")

        basic_tab.grid_columnconfigure(1, weight=1)
        basic_tab.grid_rowconfigure(4, weight=1)

        row = 0
        col = 0
        columnwidth = 12

        ttk.Label(basic_tab, text="关键词:", width=columnwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
        self.key_entry = ttk.Entry(basic_tab, width=20)
        self.key_entry.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
        row += 1

        ttk.Label(basic_tab, text="次要关键词:", width=columnwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
        self.keysecondary_entry = ttk.Entry(basic_tab, width=20)
        self.keysecondary_entry.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
        row += 1

        ttk.Label(basic_tab, text="注释 (Comment):", width=columnwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2) #  注释label 更加明确
        self.comment_entry = ttk.Entry(basic_tab, width=20)
        self.comment_entry.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
        row += 1

        ttk.Label(basic_tab, text="条目内容 (Content):", width=columnwidth).grid(row=row, column=col, sticky=tk.NW, padx=5, pady=2) # 条目内容label 更加明确
        self.content_text = scrolledtext.ScrolledText(basic_tab, wrap=tk.WORD, height=12, width=30)
        self.content_text.grid(row=row, column=col + 1, sticky=tk.NSEW, padx=5, pady=2)
        row += 1

        ttk.Label(basic_tab, text="插入位置:", width=columnwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
        self.position_combo = ttk.Combobox(basic_tab, values=self.world_book_manager.position_options, width=18)
        self.position_combo.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
        row += 1

        if self.use_advanced_mode.get():
            row = 0
            col = 0

            ttk.Label(advanced_tab, text="设为常驻条目:", width=columnwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            self.constant_var = tk.BooleanVar()
            self.constant_check = ttk.Checkbutton(advanced_tab, variable=self.constant_var, text="常驻")
            self.constant_check.grid(row=row, column=col + 1, sticky=tk.W, padx=5, pady=2)
            row += 1

            ttk.Label(advanced_tab, text="禁用此条目:", width=columnwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            self.disable_var = tk.BooleanVar()
            self.disable_check = ttk.Checkbutton(advanced_tab, variable=self.disable_var, text="禁用")
            self.disable_check.grid(row=row, column=col + 1, sticky=tk.W, padx=5, pady=2)
            row += 1

            ttk.Label(advanced_tab, text="角色消息类型:", width=columnwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            self.role_combo = ttk.Combobox(advanced_tab, values=self.world_book_manager.role_options, width=18)
            self.role_combo.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
            row += 1

            ttk.Label(advanced_tab, text="粘性行为:", width=columnwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            self.sticky_combo = ttk.Combobox(advanced_tab, values=self.world_book_manager.sticky_options, width=18)
            self.sticky_combo.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
            row += 1

            ttk.Label(advanced_tab, text="选择逻辑规则:", width=columnwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            self.selective_logic_combo = ttk.Combobox(advanced_tab,
                                                      values=self.world_book_manager.selective_logic_options_chinese,
                                                      width=18)
            self.selective_logic_combo.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
            row += 1

            row = 0
            col = 0

            recursion_props = ["excludeRecursion", "preventRecursion", "delayUntilRecursion"]
            self.recursion_vars = {}
            recursion_chinese_names = {
                "excludeRecursion": "本条目不被递归触发", #  更准确的中文翻译
                "preventRecursion": "阻止条目内容触发递归", #  更准确的中文翻译
                "delayUntilRecursion": "延迟到递归"
            }
            for prop in recursion_props:
                ttk.Label(recursion_group_tab,
                          text=f"{recursion_chinese_names[prop]}:", # 应用更准确的翻译
                          width=columnwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
                self.recursion_vars[prop] = tk.BooleanVar()
                check = ttk.Checkbutton(recursion_group_tab, variable=self.recursion_vars[prop],
                                        text=recursion_chinese_names[prop])
                check.grid(row=row, column=col + 1, sticky=tk.W, padx=5, pady=2)
                row += 1

            str_props = ["group", "automationId"]
            self.str_entries = {}
            str_chinese_names = {
                "group": "分组",
                "automationId": "自动化 ID"
            }
            for prop in str_props:
                ttk.Label(recursion_group_tab, text=f"{str_chinese_names[prop]}:", width=columnwidth).grid(row=row, column=col,
                                                                                                    sticky=tk.W, padx=5,
                                                                                                    pady=2)
                self.str_entries[prop] = ttk.Entry(recursion_group_tab, width=20)
                self.str_entries[prop].grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
                row += 1

            row = 0
            col = 0

            bool_props = ["vectorized", "selective", "addMemo", "groupOverride", "useProbability", "caseSensitive",
                          "matchWholeWords", "useGroupScoring"]
            self.bool_vars = {}
            col_count = 0
            bool_chinese_names = {
                "vectorized": "向量化",
                "selective": "选择性",
                "addMemo": "添加备注",
                "groupOverride": "分组覆盖",
                "useProbability": "使用概率",
                "caseSensitive": "区分大小写",
                "matchWholeWords": "匹配整个单词",
                "useGroupScoring": "使用分组评分"
            }
            for prop in bool_props:
                ttk.Label(numerical_bool_tab, text=f"{bool_chinese_names[prop]}:", width=columnwidth).grid(row=row, column=col,
                                                                                                    sticky=tk.W, padx=5,
                                                                                                    pady=2)
                self.bool_vars[prop] = tk.BooleanVar()
                check = ttk.Checkbutton(numerical_bool_tab, variable=self.bool_vars[prop], text=bool_chinese_names[prop])
                check.grid(row=row, column=col + 1, sticky=tk.W, padx=5, pady=2)


                col_count += 1
                if col_count % 2 == 0:
                    row += 1
                    col = 0
                else:
                    col += 2

            row = max(row, 4)
            col = 0

            int_props = ["order", "probability", "groupWeight", "cooldown", "delay",
                         "depth", "scanDepth"]
            self.int_entries = {}
            col_count = 0
            int_chinese_names = {
                "order": "插入顺序", #  更准确的中文翻译
                "probability": "概率",
                "groupWeight": "分组权重",
                "cooldown": "冷却时间",
                "delay": "延迟",
                "depth": "深度",
                "scanDepth": "扫描深度"
            }
            for prop in int_props:
                ttk.Label(numerical_bool_tab, text=f"{int_chinese_names[prop]}:", width=columnwidth).grid(row=row, column=col,
                                                                                                    sticky=tk.W, padx=5,
                                                                                                    pady=2)
                self.int_entries[prop] = ttk.Entry(numerical_bool_tab, width=20)
                self.int_entries[prop].grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)

                col_count += 1
                if col_count % 2 == 0:
                    row += 1
                    col = 0
                else:
                    col += 2

    def load_worldbook(self):
        """Loads worldbook file."""
        initial_dir = find_sillytavern_worlds_path()
        file_path = filedialog.askopenfilename(
            title="选择 Lorebook JSON 文件", #  对话框标题使用 Lorebook
            filetypes=[("JSON files", "*.json")],
            initialdir=initial_dir
        )
        if file_path:
            if self.world_book_manager.load_worldbook(file_path):
                self.update_entry_list()
                messagebox.showinfo("成功", f"已加载: {file_path}")

    def save_worldbook(self):
        """Saves worldbook file."""
        if self.world_book_manager.current_file_path:
            if self.world_book_manager.save_worldbook():
                messagebox.showinfo("成功", "已保存")
        else:
            self.save_worldbook_as()

    def save_worldbook_as(self):
        """Saves worldbook file as new file."""
        initial_dir = find_sillytavern_worlds_path()
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            title="保存 Lorebook JSON 文件", #  对话框标题使用 Lorebook
            initialdir=initial_dir
        )
        if file_path:
            if self.world_book_manager.save_worldbook(file_path):
                messagebox.showinfo("成功", f"已保存到: {file_path}")

    def on_entry_select(self, event):
        """Handles entry selection from listbox."""
        selected_index = self.entry_listbox.curselection()
        if selected_index:
            selected_text = self.entry_listbox.get(selected_index[0])
            uid_match = re.search(r'(\d+) -', selected_text)
            if uid_match:
                uid = int(uid_match.group(1))
                entry = self.world_book_manager.get_entry_by_uid(uid)
                if entry:
                    self.populate_edit_fields(entry)
                    self.save_button.config(state=tk.NORMAL)
                    self.delete_button.config(state=tk.NORMAL)

    def populate_edit_fields(self, entry: dict):
        """Populates edit fields with selected entry data."""
        self.clear_edit_fields()

        self.key_entry.insert(0, ", ".join(entry.get('key', [])))
        self.keysecondary_entry.insert(0, ", ".join(entry.get('keysecondary', [])))
        self.comment_entry.insert(0, entry.get('comment', ''))
        self.content_text.insert(tk.INSERT, entry.get('content', ''))
        self.position_combo.set(
            next((key for key, value in self.world_book_manager.position_map_chinese.items() if value == entry.get(
                'position', 1)), None) or "")

        if self.use_advanced_mode.get():
            self.constant_var.set(entry.get('constant', False))
            self.disable_var.set(entry.get('disable', False))
            self.role_combo.set(next((key for key, value in self.world_book_manager.role_map.items() if value == entry.get(
                'role', None)), None) or "")
            self.sticky_combo.set(
                next((key for key, value in self.world_book_manager.sticky_map.items() if value == entry.get('sticky',
                                                                                                             0)),
                     None) or "")
            self.selective_logic_combo.set(next((key for key, value in
                                                 self.world_book_manager.selective_logic_map.items() if value == entry.get(
                    'selectiveLogic', 0)), None) or "")

            for prop, var in self.bool_vars.items():
                value = entry.get(prop)
                var.set(bool(value) if value is not None else False) #  更安全地处理 None 值

            for prop, entry_field in self.int_entries.items():
                entry_field.insert(0, str(entry.get(prop, 0)))

            for prop, entry_field in self.str_entries.items():
                entry_field.insert(0, entry.get(prop, ''))

    def clear_edit_fields(self):
        """Clears all edit fields."""
        self.key_entry.delete(0, tk.END)
        self.keysecondary_entry.delete(0, tk.END)
        self.comment_entry.delete(0, tk.END)
        self.content_text.delete(1.0, tk.END)
        self.position_combo.set("")

        if self.use_advanced_mode.get():
            self.constant_var.set(False)
            self.disable_var.set(False)
            self.role_combo.set("")
            self.sticky_combo.set("")
            self.selective_logic_combo.set("")

            for var in self.bool_vars.values():
                var.set(False)
            for entry_field in self.int_entries.values():
                entry_field.delete(0, tk.END)
            for entry_field in self.str_entries.values():
                entry_field.delete(0, tk.END)

    def save_entry(self):
        """Saves current entry data to worldbook data."""
        selected_index = self.entry_listbox.curselection()
        if not selected_index:
            return

        selected_text = self.entry_listbox.get(selected_index[0])
        uid_match = re.search(r'(\d+) -', selected_text)
        if uid_match:
            uid = int(uid_match.group(1))
            if uid is None:
                messagebox.showerror("错误", "无法获取条目 UID")
                return

        updated_info = {
            'key': [k.strip() for k in self.key_entry.get().split(',') if k.strip()],
            'keysecondary': [k.strip() for k in self.keysecondary_entry.get().split(',') if
                             k.strip()],
            'comment': self.comment_entry.get(),
            'content': self.content_text.get(1.0, tk.END).strip(),
            'position': self.world_book_manager.position_map_english[
                self.position_combo.get()] if self.position_combo.get() else 1,
        }

        if self.use_advanced_mode.get():
            updated_info['constant'] = self.constant_var.get()
            updated_info['disable'] = self.disable_var.get()
            updated_info['role'] = self.role_combo.get()
            updated_info['sticky'] = self.sticky_combo.get()
            updated_info['selectiveLogic'] = self.world_book_manager.selective_logic_map[
                self.selective_logic_combo.get()] if self.selective_logic_combo.get() else 0

            for prop, var in self.bool_vars.items():
                updated_info[prop] = var.get()
            for prop, entry_field in self.int_entries.items():
                try:
                    updated_info[prop] = int(entry_field.get())
                except ValueError:
                    updated_info[prop] = 0
            for prop, entry_field in self.str_entries.items():
                updated_info[prop] = entry_field.get()

        if self.world_book_manager.update_entry(uid, updated_info):
            self.update_entry_list()
            messagebox.showinfo("成功", "条目已保存")

    def delete_entry(self):
        """Deletes the currently selected entry."""
        selected_index = self.entry_listbox.curselection()
        print(f"选中的索引: {selected_index}")
        if not selected_index:
            return

        selected_text = self.entry_listbox.get(selected_index[0])
        print(f"选中的文本: {selected_text}")
        uid_match = re.search(r'(\d+) -', selected_text)
        if uid_match:
            uid = int(uid_match.group(1))
            print(f"解析出的 UID: {uid}")
            if uid is None:
                messagebox.showerror("错误", "无法获取条目 UID")
                return

            if messagebox.askyesno("确认", "确定要删除此条目吗？"):
                print(f"准备删除 UID: {uid}")
                if self.world_book_manager.delete_entry(uid):
                    print(f"WorldBookManager 删除成功")
                    self.update_entry_list()
                    self.clear_edit_fields()
                    self.save_button.config(state=tk.DISABLED)
                    self.delete_button.config(state=tk.DISABLED)
                    messagebox.showinfo("成功", "条目已删除")
                else:
                    print(f"WorldBookManager 删除失败")
        else:
            print(f"未找到匹配的 UID")
            messagebox.showerror("错误", "无法解析条目 UID")

    def new_entry(self):
        """Creates a new worldbook entry."""
        new_entry_data = self.world_book_manager.create_entry()
        if self.world_book_manager.worldbook_data is None:
            self.world_book_manager.worldbook_data = {'entries': {}}
        self.world_book_manager.worldbook_data['entries'][str(new_entry_data['uid'])] = new_entry_data
        self.update_entry_list()
        self.populate_edit_fields(new_entry_data)
        self.save_button.config(state=tk.NORMAL)
        self.delete_button.config(state=tk.NORMAL)

    def update_entry_list(self):
        """Updates the entry listbox with current worldbook entries."""
        self.entry_listbox.delete(0, tk.END)
        display_texts = self.world_book_manager.get_entries_list_display()
        for text in display_texts:
            self.entry_listbox.insert(tk.END, text)

    def show_instructions_gui(self):
        """Displays the instructions GUI."""
        instruction_window = tk.Toplevel(self.root)
        instruction_window.title("使用说明")

        instruction_text = scrolledtext.ScrolledText(instruction_window, wrap=tk.WORD, height=25, width=80,
                                                     font=font.Font(size=11), spacing3=5)
        instruction_text.pack(padx=20, pady=20, expand=True, fill=tk.BOTH)
        instruction_text.config(state=tk.DISABLED)

        instructions = """
    SillyTavern 世界书编辑器 (Lorebook Editor) - 使用说明

    本工具用于编辑 SillyTavern 的世界书 (Lorebook) JSON 文件。

    世界信息 (Lorebooks) 增强 AI 对世界细节的理解。
    它像动态字典，仅当消息文本出现与条目相关的关键词时，
    条目信息才被插入。SillyTavern 引擎激活 Lore 并无缝整合到提示词，
    为 AI 提供背景信息。

    **注意**: 世界信息引导 AI 找到期望 Lore，但不保证出现在输出消息中。

    **进阶提示**:
    - AI 不在上下文中插入触发关键词。
    - 每个世界书条目应是全面、独立的描述。
    - 条目间可相互链接和参考，构建丰富世界传说 (world lore)。
    - 为节约 Token，条目内容应简洁，建议每条不超过 50 Token。

    **角色 Lore (Character Lore)**:
    - 可将世界书文件分配给角色，作为其所有对话 (含群组) 的专用 Lore 源。
    - 在“角色管理”面板，点击“地球仪”按钮，选择“世界信息”并“确定”即可。

    **角色 Lore 插入策略**:
    生成 AI 回复时，角色世界书条目与全局世界书条目结合：
    - **均匀排序 (默认)**: 所有条目按插入顺序排序，忽略源文件。
    - **角色 Lore 优先**: 角色世界书条目先包含并排序，后接全局世界书条目。
    - **全局 Lore 优先**: 全局世界书条目先包含并排序，后接角色世界书条目。

    **世界书条目字段说明**:

    - **关键词 (Keywords)**: 触发条目的关键词列表，不区分大小写 (可配置)。
    - **次要关键词 (Secondary Keywords)**: 与主关键词联用的补充关键词列表 (见“选择性”)。
    - **条目内容 (Content)**: 条目激活时插入提示词的文本。
    - **插入顺序 (Order)**: 数值，定义多条目同时激活时的优先级，值越大优先级越高，越靠近上下文末尾。
    - **插入位置 (Position)**:
        - 角色定义前: 条目在角色描述和场景前插入，对对话影响适中。
        - 角色定义后: 条目在角色描述和场景后插入，对对话影响较大。
    - **注释 (Comment)**: 文本注释，不发送给 AI，仅为方便用户编辑。
    - **常驻 (Constant)**: 启用后，条目始终出现在提示词中。
    - **选择性 (Selective)**: 启用后，需同时激活关键词和次要关键词才插入条目 (无次要关键词则忽略)。
    - **扫描深度 (Scan Depth)**: 定义扫描多少条消息记录以查找关键词 (最多 10 组消息)。
    - **Token 预算 (Token Budget)**: 条目一次可用 Token 数量 (超出预算则停止激活更多条目)。
        - 常驻条目优先插入，其次是高优先级条目，直接提及关键词的条目优先级更高。
    - **递归扫描 (Recursive Scanning)**: 允许条目通过在内容中提及关键词来激活其他条目。
    - **关键词区分大小写 (Case Sensitive Keywords)**: 启用后，关键词需与条目定义的大小写匹配。
    - **匹配整个单词 (Match Whole Words)**: 启用后，仅匹配搜索文本中的整个单词。

        """ #  使用 Markdown 格式化说明文档
        instruction_text.config(state=tk.NORMAL)
        instruction_text.insert(tk.END, instructions)
        instruction_text.config(state=tk.DISABLED)
        instruction_text.mark_set(" DocStart", "1.0")


class WorldBookApp:
    """Main application class for WorldBook Editor."""
    def __init__(self, root):
        """Initializes WorldBookApp."""
        self.root = root
        self.world_book_manager = WorldBookManager()
        self.ui = WorldBookUI(root, self.world_book_manager)

    def run(self):
        """Runs the main application loop."""
        self.root.mainloop()


def find_sillytavern_worlds_path(initial_dir=None):
    """Finds SillyTavern worlds path, similar to settings path logic."""
    if initial_dir and os.path.exists(initial_dir):
        return initial_dir

    documents_path = os.path.expanduser("~/Documents")
    if not os.path.exists(documents_path):
        documents_path = os.path.expanduser("~/文档")
    if not os.path.exists(documents_path):
        documents_path = os.path.expanduser("~")

    print(f"\n在目录: {documents_path} 下查找 SillyTavern 文件夹...")
    sillytavern_dir_path = None
    for root, dirs, _ in os.walk(documents_path):
        if "SillyTavern" in dirs:
            sillytavern_dir_path = os.path.join(root, "SillyTavern")
            break

    if sillytavern_dir_path:
        worlds_path = os.path.join(sillytavern_dir_path, "data", "worlds")
        if os.path.exists(worlds_path):
            print(f"找到 worlds 目录: {worlds_path}")
            return worlds_path

    return None


import re

if __name__ == "__main__":
    root = tk.Tk()
    app = WorldBookApp(root)
    app.run()