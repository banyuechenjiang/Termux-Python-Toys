import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinter import font
from typing import Optional, List, Dict
import re
import sys


class WorldBookManager:
    """世界书数据管理类."""
    # 内部英文位置映射
    POSITION_MAP_ENGLISH = {
        "Before Char Defs": 0, "After Char Defs": 1, "Before Example Messages": 2,
        "After Example Messages": 3, "Top of AN": 4, "Bottom of AN": 5, "@ D": 6,
        "⚙️ - as a system role message": 7, "👤 - as a user role message": 8,
        "🤖 - as an assistant role message": 9
    }
    # 中文显示位置映射
    POSITION_MAP_CHINESE = {
        "角色定义前": "Before Char Defs", "角色定义后": "After Char Defs",
        "示例消息前": "Before Example Messages", "示例消息后": "After Example Messages",
        "作者注释 顶部": "Top of AN", "作者注释 底部": "Bottom of AN", "@ D": "@ D",
        "⚙️ - 系统角色消息": "⚙️ - as a system role message",
        "👤 - 用户角色消息": "👤 - as a user role message",
        "🤖 - 助手角色消息": "🤖 - as an assistant role message"
    }
    # 角色映射
    ROLE_MAP = {"User": 0, "System": 1, "Assistant": 2}
    # 常驻类型映射
    STICKY_MAP = {"否": 0, "是": 1, "直到上下文满": 2}
    # 选择逻辑映射
    SELECTIVE_LOGIC_MAP = {
        "AND ANY": 0, "AND ALL": 1, "NOT ANY": 2, "NOT ALL": 3,
        "与任意关键词匹配": "AND ANY", "与所有关键词匹配": "AND ALL",
        "不含任意关键词": "NOT ANY", "不含所有关键词": "NOT ALL"
    }

    def __init__(self):
        """初始化 WorldBookManager."""
        self.worldbook_data = None
        self.current_file_path = None

        self.position_options = list(self.POSITION_MAP_CHINESE.keys())
        self.role_options = list(self.ROLE_MAP.keys())
        self.sticky_options = list(self.STICKY_MAP.keys())
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
                if key == "position" and value in self.POSITION_MAP_ENGLISH:
                    merged_entry[key] = self.POSITION_MAP_ENGLISH[value]
                elif key == "role" and value in self.ROLE_MAP:
                    merged_entry[key] = self.ROLE_MAP[value]
                elif key == "sticky" and value in self.STICKY_MAP:
                    merged_entry[key] = self.STICKY_MAP[value]
                elif key == "selectiveLogic" and value in self.SELECTIVE_LOGIC_MAP:
                    merged_entry[key] = self.SELECTIVE_LOGIC_MAP[value]
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
                    if key == "position" and value in self.POSITION_MAP_ENGLISH:
                        entry[key] = self.POSITION_MAP_ENGLISH[value]
                    elif key == "role" and value in self.ROLE_MAP:
                        entry[key] = self.ROLE_MAP[value]
                    elif key == "sticky" and value in self.STICKY_MAP:
                        entry[key] = self.STICKY_MAP[value]
                    elif key == "selectiveLogic" and value in self.SELECTIVE_LOGIC_MAP:
                        entry[key] = self.SELECTIVE_LOGIC_MAP[value]
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
        self.root.geometry("1200x700")#窗口大小

        self.style = ttk.Style()
        self.setup_styles()

        self.button_frame = ttk.Frame(self.root)
        self.edit_frame = ttk.Frame(self.root)
        self.notebook = ttk.Notebook(self.edit_frame)

        self.int_entries = {}
        self.str_entries = {}
        self.bool_vars = {}

        self.create_widgets()
        self.create_edit_fields()
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
        top_frame = ttk.Frame(self.root)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        load_button = ttk.Button(top_frame, text="加载 Lorebook", command=self.load_worldbook)
        load_button.pack(side=tk.LEFT, padx=5)

        save_button = ttk.Button(top_frame, text="保存 Lorebook", command=self.save_worldbook)
        save_button.pack(side=tk.LEFT, padx=5)

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


    def create_edit_fields(self):
        """根据编辑模式创建不同的编辑字段."""
        for tab_frame in self.notebook.winfo_children():
            tab_frame.destroy()

        basic_tab = ttk.Frame(self.notebook)
        advanced_tab = ttk.Frame(self.notebook)
        recursion_group_tab = ttk.Frame(self.notebook)
        numerical_bool_tab = ttk.Frame(self.notebook)

        self.notebook.add(basic_tab, text="基本信息")
        self.notebook.add(advanced_tab, text="高级选项")
        self.notebook.add(recursion_group_tab, text="递归 & 分组")
        self.notebook.add(numerical_bool_tab, text="数值 & 布尔")

        self._create_basic_tab(basic_tab)
        self._create_advanced_tab(advanced_tab)
        self._create_recursion_group_tab(recursion_group_tab)
        self._create_numerical_bool_tab(numerical_bool_tab)

    def _create_basic_tab(self, parent_tab):
        parent_tab.grid_columnconfigure(1, weight=1)
        parent_tab.grid_rowconfigure(4, weight=1)
        row, col, colwidth = 0, 0, 12

        ttk.Label(parent_tab, text="关键词:", width=colwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
        self.key_entry = ttk.Entry(parent_tab, width=20)
        self.key_entry.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
        row += 1

        ttk.Label(parent_tab, text="次要关键词:", width=colwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
        self.keysecondary_entry = ttk.Entry(parent_tab, width=20)
        self.keysecondary_entry.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
        row += 1

        ttk.Label(parent_tab, text="注释 (Comment):", width=colwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
        self.comment_entry = ttk.Entry(parent_tab, width=20)
        self.comment_entry.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
        row += 1

        ttk.Label(parent_tab, text="条目内容 (Content):", width=colwidth).grid(row=row, column=col, sticky=tk.NW, padx=5, pady=2)
        self.content_text = scrolledtext.ScrolledText(parent_tab, wrap=tk.WORD, height=12, width=30)
        self.content_text.grid(row=row, column=col + 1, sticky=tk.NSEW, padx=5, pady=2)
        row += 1

        ttk.Label(parent_tab, text="插入位置:", width=colwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
        self.position_combo = ttk.Combobox(parent_tab, values=self.world_book_manager.position_options, width=18)
        self.position_combo.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)

    def _create_advanced_tab(self, parent_tab):
        row, col, colwidth = 0, 0, 12

        self.constant_var = tk.BooleanVar()
        ttk.Checkbutton(parent_tab, variable=self.constant_var, text="设为常驻条目").grid(row=row, column=col, columnspan=2, sticky=tk.W, padx=5, pady=2)
        row += 1

        self.disable_var = tk.BooleanVar()
        ttk.Checkbutton(parent_tab, variable=self.disable_var, text="禁用此条目").grid(row=row, column=col, columnspan=2, sticky=tk.W, padx=5, pady=2)
        row += 1

        ttk.Label(parent_tab, text="角色消息类型:", width=colwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
        self.role_combo = ttk.Combobox(parent_tab, values=self.world_book_manager.role_options, width=18)
        self.role_combo.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
        row += 1

        ttk.Label(parent_tab, text="粘性行为:", width=colwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
        self.sticky_combo = ttk.Combobox(parent_tab, values=self.world_book_manager.sticky_options, width=18)
        self.sticky_combo.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
        row += 1

        ttk.Label(parent_tab, text="选择逻辑规则:", width=colwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
        self.selective_logic_combo = ttk.Combobox(parent_tab, values=self.world_book_manager.selective_logic_options_chinese, width=18)
        self.selective_logic_combo.grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)

    def _create_recursion_group_tab(self, parent_tab):
        row, col, colwidth = 0, 0, 12

        recursion_props = ["excludeRecursion", "preventRecursion", "delayUntilRecursion"]
        self.recursion_vars = {}
        recursion_chinese_names = {
            "excludeRecursion": "本条目不被递归触发",
            "preventRecursion": "阻止条目内容触发递归",
            "delayUntilRecursion": "延迟到递归"
        }
        for prop in recursion_props:
            self.recursion_vars[prop] = tk.BooleanVar()
            check = ttk.Checkbutton(parent_tab, variable=self.recursion_vars[prop], text=recursion_chinese_names[prop])
            check.grid(row=row, column=col, columnspan=2, sticky=tk.W, padx=5, pady=2)
            row += 1

        str_props = {"group": "分组", "automationId": "自动化 ID"}
        self.str_entries = {}
        for prop, name in str_props.items():
            ttk.Label(parent_tab, text=f"{name}:", width=colwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            self.str_entries[prop] = ttk.Entry(parent_tab, width=20)
            self.str_entries[prop].grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)
            row += 1

    def _create_numerical_bool_tab(self, parent_tab):
        bool_props = {
            "vectorized": "向量化", "selective": "选择性", "addMemo": "添加备注",
            "groupOverride": "分组覆盖", "useProbability": "使用概率", "caseSensitive": "区分大小写",
            "matchWholeWords": "匹配整个单词", "useGroupScoring": "使用分组评分"
        }
        self.bool_vars = {}
        row = self._create_grid_of_widgets(parent_tab, bool_props, self.bool_vars, "bool", 0)

        int_props = {
            "order": "插入顺序", "probability": "概率", "groupWeight": "分组权重",
            "cooldown": "冷却时间", "delay": "延迟", "depth": "深度", "scanDepth": "扫描深度"
        }
        self.int_entries = {}
        self._create_grid_of_widgets(parent_tab, int_props, self.int_entries, "int", row)

    def _create_grid_of_widgets(self, parent, props, storage, widget_type, start_row):
        row, col, colwidth = start_row, 0, 12
        col_count = 0
        for prop, name in props.items():
            if widget_type == "bool":
                storage[prop] = tk.BooleanVar()
                widget = ttk.Checkbutton(parent, variable=storage[prop], text=name)
                widget.grid(row=row, column=col, columnspan=2, sticky=tk.W, padx=5, pady=2)
            elif widget_type == "int":
                ttk.Label(parent, text=f"{name}:", width=colwidth).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
                storage[prop] = ttk.Entry(parent, width=20)
                storage[prop].grid(row=row, column=col + 1, sticky=tk.EW, padx=5, pady=2)

            col_count += 1
            if col_count % 2 == 0:
                row += 1
                col = 0
            else:
                col += 2
        return row + (1 if col_count % 2 != 0 else 0)

    def load_worldbook(self):
        """Loads worldbook file."""
        initial_dir = find_sillytavern_worlds_path()
        file_path = filedialog.askopenfilename(
            title="选择 Lorebook JSON 文件", 
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
            title="保存 Lorebook JSON 文件", 
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

        # 修复: 正确渲染插入位置
        position_int = entry.get('position', 1)
        rev_pos_map = {v: k for k, v in self.world_book_manager.POSITION_MAP_ENGLISH.items()}
        english_pos = rev_pos_map.get(position_int)
        if english_pos:
            rev_chinese_map = {v: k for k, v in self.world_book_manager.POSITION_MAP_CHINESE.items()}
            self.position_combo.set(rev_chinese_map.get(english_pos, ""))
        else:
            self.position_combo.set("")

        self.constant_var.set(entry.get('constant', False))
        self.disable_var.set(entry.get('disable', False))
        self.role_combo.set(next((k for k, v in self.world_book_manager.ROLE_MAP.items() if v == entry.get(
            'role', None)), None) or "")
        self.sticky_combo.set(
            next((k for k, v in self.world_book_manager.STICKY_MAP.items() if v == entry.get('sticky', 0)),
                 None) or "")
        self.selective_logic_combo.set(next((k for k, v in
                                             self.world_book_manager.SELECTIVE_LOGIC_MAP.items() if v == entry.get(
                'selectiveLogic', 0)), None) or "")

        for prop, var in self.bool_vars.items():
            value = entry.get(prop)
            var.set(bool(value) if value is not None else False) #  更安全地处理 None 值

        # 修复：填充递归选项的勾选状态
        for prop, var in self.recursion_vars.items():
            default_value = True if prop == "preventRecursion" else False
            var.set(entry.get(prop, default_value))

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

        self.constant_var.set(False)
        self.disable_var.set(False)
        self.role_combo.set("")
        self.sticky_combo.set("")
        self.selective_logic_combo.set("")

        for var in self.bool_vars.values():
            var.set(False)
        # 修复：清空递归选项
        for var in self.recursion_vars.values():
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
            'position': self.world_book_manager.POSITION_MAP_ENGLISH.get(
                self.world_book_manager.POSITION_MAP_CHINESE.get(self.position_combo.get()), 1),
        }

        updated_info['constant'] = self.constant_var.get()
        updated_info['disable'] = self.disable_var.get()

        selected_role = self.role_combo.get()
        updated_info['role'] = self.world_book_manager.ROLE_MAP.get(selected_role)

        selected_sticky = self.sticky_combo.get()
        updated_info['sticky'] = self.world_book_manager.STICKY_MAP.get(selected_sticky, 0)

        selected_logic = self.selective_logic_combo.get()
        updated_info['selectiveLogic'] = self.world_book_manager.SELECTIVE_LOGIC_MAP.get(selected_logic, 0)

        for prop, var in self.bool_vars.items():
            updated_info[prop] = var.get()
        # 修复：保存递归选项的状态
        for prop, var in self.recursion_vars.items():
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


if __name__ == "__main__":
    root = tk.Tk()
    app = WorldBookApp(root)

    # 检查启动模式
    if len(sys.argv) > 1:
        # --- 拖放模式 ---
        input_path = sys.argv[1]

        # 验证路径
        if os.path.isfile(input_path) and input_path.lower().endswith('.json'):
            # 直接加载文件，然后启动UI
            if app.world_book_manager.load_worldbook(input_path):
                app.ui.update_entry_list()
                app.run()
            else:
                # 如果加载失败，app.world_book_manager 内部会显示消息框
                # 此处直接退出即可
                root.destroy()
                sys.exit(1)
        else:
            messagebox.showerror("错误", "请拖放一个有效的 .json 文件。")
            root.destroy()
            sys.exit(1)
    else:
        # --- 交互模式 ---
        app.run()
