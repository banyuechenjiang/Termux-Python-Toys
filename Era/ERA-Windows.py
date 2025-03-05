#ErbFileViewer -V2.8
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, messagebox, simpledialog
import re
import os
import ast
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = OrderedDict()

    def get(self, key):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key, value):
        self.cache[key] = value
        self.cache.move_to_end(key)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

erb_files_cache = LRUCache(capacity=10)

class ErbFileViewer:
    def __init__(self, master):
        self.master = master
        master.title("Erb 文件查看器")

        # --- 配置变量 ---
        self.show_content_var = tk.BooleanVar(value=True)
        self.comment_var = tk.BooleanVar(value=True)
        self.variable_var = tk.BooleanVar(value=False)
        self.string_var = tk.BooleanVar(value=True)
        self.print_var = tk.BooleanVar(value=True)
        self.conditional_var = tk.BooleanVar(value=False)
        self.align_var = tk.BooleanVar(value=False)
        self.enable_paging_var = tk.BooleanVar(value=False)
        self.indent_amount_var = tk.StringVar(value="4")
        self.page_size_var = tk.StringVar(value="100")

        # --- 菜单栏 ---
        self.menu_bar = tk.Menu(master)
        master.config(menu=self.menu_bar)

        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.file_menu.add_command(label="选择文件夹", command=self.show_folder_menu)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="退出", command=master.quit)
        self.menu_bar.add_cascade(label="文件", menu=self.file_menu)

        self.options_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.options_menu.add_command(label="打开配置选项", command=self.open_config_window)
        self.menu_bar.add_cascade(label="选项", menu=self.options_menu)

        # --- 工具栏 ---
        self.toolbar_frame = ttk.Frame(master)
        self.toolbar_frame.pack(fill=tk.X)

        self.load_folder_button = tk.Button(self.toolbar_frame, text="选择文件夹", command=self.show_folder_menu)
        self.load_folder_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.process_button = tk.Button(self.toolbar_frame, text="处理并显示", command=self.process_file, state=tk.DISABLED)
        self.process_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.config_button_toolbar = tk.Button(self.toolbar_frame, text="配置选项", command=self.open_config_window)
        self.config_button_toolbar.pack(side=tk.LEFT, padx=5, pady=5)

        # --- ERB 文件列表区域 ---
        self.erb_list_frame = ttk.Frame(master)
        self.erb_list_frame.pack(fill=tk.BOTH, padx=5, pady=5, expand=True)

        self.erb_list_scrollbar_y = ttk.Scrollbar(self.erb_list_frame)
        self.erb_list_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.erb_list_listbox = tk.Listbox(
            self.erb_list_frame,
            yscrollcommand=self.erb_list_scrollbar_y.set,
            exportselection=False
        )
        self.erb_list_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.erb_list_scrollbar_y.config(command=self.erb_list_listbox.yview)

        self.load_selected_file_button = tk.Button(
            self.erb_list_frame, text="加载选中文件", command=self.load_selected_erb_file, state=tk.DISABLED)
        self.load_selected_file_button.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        self.erb_list_listbox.bind('<<ListboxSelect>>', self.on_erb_file_select)

        # --- 主文本区域 ---
        self.text_panel_frame = ttk.Frame(master, borderwidth=2, relief=tk.GROOVE, padding=5)
        self.text_panel_frame.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

        self.text_area = scrolledtext.ScrolledText(self.text_panel_frame, wrap=tk.WORD, width=80, height=20)
        self.text_area.pack(expand=True, fill=tk.BOTH)

        # --- 分页导航框架 ---
        self.navigation_frame = ttk.Frame(master)
        self.navigation_frame.pack(pady=5)

        self.prev_button = tk.Button(self.navigation_frame, text="上一页", command=self.prev_page, state=tk.DISABLED)
        self.prev_button.grid(row=0, column=0, sticky="ew", padx=5)
        self.next_button = tk.Button(self.navigation_frame, text="下一页", command=self.next_page, state=tk.DISABLED)
        self.next_button.grid(row=0, column=2, sticky="ew", padx=5)
        self.page_label = tk.Label(self.navigation_frame, text="页数：0/0")
        self.page_label.grid(row=0, column=1, sticky="ew", padx=5)

        self.navigation_frame.columnconfigure(0, weight=1)
        self.navigation_frame.columnconfigure(1, weight=1)
        self.navigation_frame.columnconfigure(2, weight=1)
        self.navigation_frame.pack_forget()

        # --- 状态栏 ---
        self.status_bar = tk.Label(master, text="未加载文件", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.filename = None
        self.file_content = None
        self.all_lines = []
        self.cached_content = None
        self.processed_content_lines = [] # 初始化 processed_content_lines
        self.base_directory = None
        self.selected_era_folder = None
        self.erb_files = []
        self.config_window = None
        self.indent_entry = None
        self.page_size_entry = None


    def get_erb_files(self, folder_path):
        """获取指定路径下所有 ERB 文件的列表，并缓存结果"""
        cached_files = erb_files_cache.get(folder_path)
        if cached_files is not None:
            return cached_files

        erb_files = []

        def _scandir(path):
            with os.scandir(path) as entries:
                for entry in entries:
                    if entry.is_file() and entry.name.endswith(".ERB"):
                        erb_files.append(entry.path)
                    elif entry.is_dir():
                        _scandir(entry.path)

        _scandir(folder_path)
        erb_files_cache.put(folder_path, erb_files)
        return erb_files


    def display_erb_file_list_in_ui(self, erb_files_list):
        """在 UI 列表框中显示 ERB 文件列表."""
        self.erb_list_listbox.delete(0, tk.END)
        if not erb_files_list:
            messagebox.showinfo("提示", "所选文件夹中没有 ERB 文件。")
            self.load_selected_file_button.config(state=tk.DISABLED)
            return

        for file_path in erb_files_list:
            self.erb_list_listbox.insert(tk.END, os.path.basename(file_path))
        self.load_selected_file_button.config(state=tk.NORMAL)


    def load_selected_erb_file(self):
        """加载用户在 UI 列表中选择的 ERB 文件."""
        selected_indices = self.erb_list_listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("提示", "请先在列表中选择一个 ERB 文件。")
            return

        selected_file_name = self.erb_list_listbox.get(selected_indices[0])
        full_file_path = ""
        for file_path in self.erb_files:
            if os.path.basename(file_path) == selected_file_name:
                full_file_path = file_path
                break

        if full_file_path:
            self.load_erb_file(full_file_path)
        else:
            messagebox.showerror("错误", "无法找到所选文件的完整路径。")


    def on_erb_file_select(self, event):
        """当用户在 ERB 文件列表中选择文件时，启用加载按钮."""
        if self.erb_list_listbox.curselection():
            self.load_selected_file_button.config(state=tk.NORMAL)
        else:
            self.load_selected_file_button.config(state=tk.DISABLED)


    def show_folder_menu(self):
        """显示文件夹选择菜单，并自动打开 D:\game\EraUniverse 目录."""
        default_dir = r"D:\game\EraUniverse"
        if not os.path.isdir(default_dir):
            default_dir = os.getcwd()

        self.base_directory = filedialog.askdirectory(
            initialdir=default_dir,
            title="选择包含多个 Era 游戏目录的文件夹"
        )

        if self.base_directory:
            erb_available_folders = []

            def walk_and_find_erb(directory, depth):
                if depth > 2:
                    return
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if entry.is_dir():
                            if entry.name.lower() == "erb":
                                erb_available_folders.append(directory)
                            else:
                                walk_and_find_erb(entry.path, depth + 1)

            walk_and_find_erb(self.base_directory, 0)
            erb_available_folders = list(set(erb_available_folders))

            if not erb_available_folders:
                messagebox.showinfo("提示", "所选目录及其子目录中没有找到 ERB 文件夹。")
                self.erb_list_listbox.delete(0, tk.END)
                self.load_selected_file_button.config(state=tk.DISABLED)
                return

            folder_options = {str(i + 1): folder for i, folder in enumerate(erb_available_folders)}
            self.selected_era_folder = erb_available_folders[0]
            erb_folder_path = os.path.join(self.selected_era_folder, "ERB")
            self.erb_files = self.get_erb_files(erb_folder_path)
            self.display_erb_file_list_in_ui(self.erb_files)
            self.status_bar.config(text=f"当前目录: {erb_folder_path}")


    def load_erb_file(self, file_path):
        """加载选定的 ERB 文件，并预处理全部内容."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                self.file_content = f.read()
            self.filename = file_path
            self.all_lines = self.file_content.splitlines()
            self.cache_file_content() # 缓存原始文件内容
            processed_text = self.process_erb(self.cached_content) # 处理全部内容
            self.processed_content_lines = processed_text.splitlines() # 缓存处理后的行

            self.total_pages = 0
            self.current_page = 0
            self.update_navigation_buttons()

            if self.enable_paging_var.get():
                self.load_page(0) # 加载第一页处理后的内容
                self.navigation_frame.pack(pady=5)
            else:
                self.text_area.delete("1.0", tk.END)
                self.text_area.insert("1.0", processed_text) # 显示全部处理后的内容
                self.navigation_frame.pack_forget()

            self.status_bar.config(text=f"当前文件: {os.path.basename(self.filename)}")
            self.process_button.config(state=tk.NORMAL)

        except Exception as e:
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert("1.0", f"错误加载文件: {e}")
            self.file_content = None
            self.all_lines = []
            self.processed_content_lines = []
            self.status_bar.config(text=f"错误加载文件: {e}")
            self.process_button.config(state=tk.DISABLED)


    def cache_file_content(self):
        """缓存文件内容，避免重复读取。"""
        if self.file_content:
            self.cached_content = self.file_content


    def open_config_window(self):
        """打开配置选项窗口."""
        if self.config_window and self.config_window.winfo_exists():
            self.config_window.focus()
            return

        self.config_window = tk.Toplevel(self.master)
        self.config_window.title("配置选项")
        self.config_window.protocol("WM_DELETE_WINDOW", self.close_config_window)

        config_options_area = ttk.Frame(self.config_window)
        config_options_area.pack(fill=tk.X, padx=10, pady=10)

        options_frame = ttk.LabelFrame(config_options_area, text="核心功能选项")
        options_frame.pack(fill=tk.X, pady=2)

        filtering_options_frame = ttk.LabelFrame(config_options_area, text="内容过滤")
        filtering_options_frame.pack(fill=tk.X, pady=2)

        print_options_frame = ttk.LabelFrame(config_options_area, text="PRINT 对齐选项")
        print_options_frame.pack(fill=tk.X, pady=2)

        config_frame = ttk.LabelFrame(config_options_area, text="配置调整")
        config_frame.pack(fill=tk.X, pady=2)

        paging_frame = ttk.LabelFrame(config_options_area, text="分页加载 (大型文件)")
        paging_frame.pack(fill=tk.X, pady=2)

        show_content_check = tk.Checkbutton(options_frame, text="显示文件内容", variable=self.show_content_var)
        show_content_check.pack(side=tk.LEFT)

        comment_check = tk.Checkbutton(filtering_options_frame, text="显示注释", variable=self.comment_var)
        comment_check.pack(side=tk.LEFT)

        variable_check = tk.Checkbutton(filtering_options_frame, text="显示变量", variable=self.variable_var)
        variable_check.pack(side=tk.LEFT)

        string_check = tk.Checkbutton(filtering_options_frame, text="显示字符串", variable=self.string_var)
        string_check.pack(side=tk.LEFT)

        print_check = tk.Checkbutton(filtering_options_frame, text="显示 PRINT 输出", variable=self.print_var)
        print_check.pack(side=tk.LEFT)

        conditional_check = tk.Checkbutton(filtering_options_frame, text="显示条件判断", variable=self.conditional_var)
        conditional_check.pack(side=tk.LEFT)

        align_check = tk.Checkbutton(print_options_frame, text="PRINT 左对齐", variable=self.align_var)
        align_check.pack(side=tk.LEFT)

        indent_label = tk.Label(config_frame, text="缩进量:")
        indent_label.pack(side=tk.LEFT)
        indent_entry = tk.Entry(config_frame, width=5, textvariable=self.indent_amount_var)
        indent_entry.pack(side=tk.LEFT)
        self.indent_entry = indent_entry

        enable_paging_check = tk.Checkbutton(paging_frame, text="启用分页", variable=self.enable_paging_var)
        enable_paging_check.pack(side=tk.LEFT)

        page_size_label = tk.Label(paging_frame, text="每页行数:")
        page_size_label.pack(side=tk.LEFT)
        page_size_entry = tk.Entry(paging_frame, width=5, textvariable=self.page_size_var)
        page_size_entry.pack(side=tk.LEFT)
        self.page_size_entry = page_size_entry


    def close_config_window(self):
        """关闭配置选项窗口."""
        if self.config_window:
            self.config_window.destroy()
            self.config_window = None


    def show_config_menu(self):
        """显示配置选项菜单 (now opens config window)."""
        self.open_config_window()


    def toggle_visibility(self, widget):
        """切换小部件的可见性。"""
        if widget.winfo_ismapped():
            widget.pack_forget()
        else:
            widget.pack(fill=tk.X, pady=2)


    def load_page(self, page_num):
        """加载并显示文件的指定页面 (使用预处理后的内容)."""
        page_size = self.get_page_size()
        start_index = page_num * page_size
        end_index = min(start_index + page_size, len(self.processed_content_lines)) # 确保不超过 processed_content_lines 长度
        page_lines = self.processed_content_lines[start_index:end_index]
        page_content = "\n".join(page_lines)
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", page_content)
        self.current_page = page_num
        self.total_pages = (len(self.processed_content_lines) + page_size - 1) // self.get_page_size() if self.get_page_size() > 0 else 1 # Handle case of page_size=0
        self.update_navigation_buttons()


    def prev_page(self):
        """加载上一页。"""
        if self.current_page > 0:
            self.load_page(self.current_page - 1)

    def next_page(self):
        """加载下一页。"""
        if self.current_page < self.total_pages - 1:
            self.load_page(self.current_page + 1)

    def update_navigation_buttons(self):
        """更新导航按钮和页码标签的状态。"""
        self.prev_button.config(state=tk.NORMAL if self.current_page > 0 else tk.DISABLED)
        self.next_button.config(state=tk.NORMAL if self.current_page < self.total_pages - 1 else tk.DISABLED)
        self.page_label.config(text=f"页数：{self.current_page + 1}/{self.total_pages if self.total_pages > 0 else 1}")


    def get_page_size(self):
        """获取每页行数，并进行错误处理。"""
        try:
            page_size = int(self.page_size_var.get())
            if page_size <= 0:
                return 0 # Return 0 if page_size is non-positive
            return page_size
        except ValueError:
            messagebox.showerror("错误", "每页行数必须是正整数，已恢复默认值 (100).")
            self.page_size_var.set("100")
            return 100


    def get_indent_amount(self):
        """获取缩进量，并进行错误处理。"""
        try:
            indent_amount = int(self.indent_amount_var.get())
            return indent_amount
        except ValueError:
            messagebox.showerror("错误", "缩进量必须是整数，已恢复默认值 (4).")
            self.indent_amount_var.set("4")
            return 4


    def process_file(self):
        """处理 ERB 文件的内容 (实际为刷新显示)."""
        if not self.cached_content:
            messagebox.showerror("错误", "未加载任何文件或文件未缓存。")
            return

        processed_text = self.process_erb(self.cached_content) # 重新处理
        self.processed_content_lines = processed_text.splitlines() # 更新 processed_content_lines

        if self.enable_paging_var.get():
            self.load_page(self.current_page) # 加载当前页，会使用最新的 processed_content_lines
        else:
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert("1.0", processed_text) # 显示全部


    def calculate_expression(self, expression, variables):
        """计算表达式的值。"""
        try:
            for var_name, var_value in variables.items():
                if isinstance(var_value, str):
                    expression = expression.replace(var_name, f"'{var_value}'")
                else:
                    expression = expression.replace(var_name, str(var_value))
            return ast.literal_eval(expression)
        except (ValueError, SyntaxError, NameError, TypeError) as e:
            print(f"表达式计算错误: {e}")
            return None


    def evaluate_condition(self, condition, variables):
        """计算布尔条件表达式的值。"""
        try:
            for var_name, var_value in variables.items():
                if isinstance(var_value, str):
                    condition = condition.replace(var_name, f"'{var_value}'")
                else:
                    condition = condition.replace(var_name, str(var_value))
            condition = condition.replace("&&", "and").replace("||", "or")
            result = ast.literal_eval(condition)
            return bool(result)

        except (ValueError, SyntaxError, NameError, TypeError) as e:
            print(f"条件判断错误: {e}")
            return False


    def process_erb(self, erb_content):
        """处理 ERB 文件内容的核心逻辑。"""
        processed_lines = []
        lines = erb_content.splitlines()

        show_content = self.show_content_var.get()
        show_comments = self.comment_var.get()
        show_variables = self.variable_var.get()
        show_strings = self.string_var.get()
        show_print = self.print_var.get()
        show_conditionals = self.conditional_var.get()
        align_print = self.align_var.get()
        indent_amount = self.get_indent_amount()

        variables = {}
        conditional_stack = []

        for line in lines:
            line = line.strip()

            if not show_content:
                continue

            if line.startswith(";") and show_comments:
                processed_lines.append(line)

            elif "=" in line and show_variables:
                try:
                    name, value_expression = line.split("=", 1)
                    name = name.strip()
                    value_expression = value_expression.strip()

                    if ":" in name:
                        array_name, index = name.split(":", 1)
                        array_name = array_name.strip()
                        index = index.strip()

                        if array_name not in variables:
                            variables[array_name] = {}

                        calculated_index = self.calculate_expression(index, variables)
                        if calculated_index is not None:
                            calculated_value = self.calculate_expression(value_expression, variables)
                            if calculated_value is not None:
                                variables[array_name][calculated_index] = calculated_value
                                processed_lines.append(f";变量赋值: {line}") # Modified to show original line as comment

                    else:
                        calculated_value = self.calculate_expression(value_expression, variables)
                        if calculated_value is not None:
                            variables[name] = calculated_value
                            processed_lines.append(f";变量赋值: {line}") # Modified to show original line as comment

                except Exception as e:
                    processed_lines.append(f";变量赋值错误: {line}")

            elif line.startswith(("PRINT", "PRINTL", "PRINTV", "PRINTVL", "PRINTS", "PRINTSL",
                                  "PRINTFORM", "PRINTFORML")):
                if show_print: # Only process if show_print is True
                    if not conditional_stack or all(conditional_stack):
                        match = re.match(r"(PRINT|PRINTL|PRINTV|PRINTVL|PRINTS|PRINTSL|PRINTFORM|PRINTFORML)\s*(.*)", line)
                        if match:
                            command = match.group(1)
                            argument = match.group(2).strip()
                            output = ""

                            if command in ("PRINTV", "PRINTVL"):
                                calculated_value = self.calculate_expression(argument, variables)
                                if calculated_value is not None:
                                    output = str(calculated_value)
                            elif command in ("PRINTS", "PRINTSL"):
                                if argument in variables and isinstance(variables[argument], str):
                                    output = variables[argument]
                                else:
                                    output = f";字符串变量 '{argument}' 未找到或不是字符串类型。"
                            elif command in ("PRINTFORM", "PRINTFORML"):
                                output = argument
                                for var_name, var_value in variables.items():
                                    output = re.sub(r"%"+re.escape(var_name)+"%", str(var_value), output)
                                    output = re.sub(r"\{"+re.escape(var_name)+r"\}", str(var_value), output)
                            else:
                                output = argument

                            if command in ("PRINTL", "PRINTVL", "PRINTSL", "PRINTFORML"):
                                output += "\n"
                            if align_print:
                                output = output.ljust(80 + indent_amount)
                            processed_lines.append(output)
                # else: If show_print is False, skip the line - no action needed here, loop continues

            elif line.startswith("IF") and show_conditionals:
                condition = line[2:].strip()
                evaluation = self.evaluate_condition(condition, variables)
                conditional_stack.append(evaluation)
                if len(conditional_stack) == 1:
                    processed_lines.append(line)
            elif line.startswith("ELSEIF") and show_conditionals:
                if conditional_stack:
                    conditional_stack[-1] = not conditional_stack[-1] and self.evaluate_condition(line[6:].strip(), variables)
                    processed_lines.append(line)
            elif line.startswith("ELSE") and show_conditionals:
                if conditional_stack:
                    conditional_stack[-1] = not conditional_stack[-1]
                    processed_lines.append(line)
            elif line.startswith("ENDIF") and show_conditionals:
                if conditional_stack:
                    conditional_stack.pop()
                    processed_lines.append(line)

            elif line and show_strings and (not conditional_stack or all(conditional_stack)):
                processed_lines.append(line)

        return "\n".join(processed_lines)


root = tk.Tk()
viewer = ErbFileViewer(root)
root.mainloop()