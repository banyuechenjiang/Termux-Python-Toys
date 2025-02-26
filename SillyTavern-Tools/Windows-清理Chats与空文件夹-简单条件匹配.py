import os
import shutil
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

class ExclusionManager:
    """
    管理文件排除规则的类。
    """
    def __init__(self, default_exclusions=None):
        self.exclusions = []
        if default_exclusions:
            for exclusion in default_exclusions:
                self.add_exclusion(exclusion)

    def add_exclusion(self, exclusion_string):
        """添加一个排除规则。"""
        if exclusion_string and exclusion_string not in self.exclusions:
            self.exclusions.append(exclusion_string)

    def remove_exclusion(self, exclusion_string):
        """删除一个排除规则"""
        if exclusion_string in self.exclusions:
            self.exclusions.remove(exclusion_string)

    def clear_exclusions(self):
        """清空所有排除规则。"""
        self.exclusions = []

    def matches_any(self, filename):
        """检查文件名是否与任何排除规则匹配。"""
        for exclusion in self.exclusions:
            # 简单的字符串包含检查
            if exclusion in filename:
                return True
        return False

    def get_exclusions(self):
        """返回当前的排除条件列表"""
        return self.exclusions


def find_sillytavern_chats_path(initial_dir=None):
    # 查找 SillyTavern chats 目录路径 (允许手动选择/切换)
    if initial_dir and os.path.exists(initial_dir):
        return initial_dir  # 使用传入的初始目录

    documents_path = os.path.expanduser("~/Documents")  # 兼容 Windows, macOS, Linux
    if not os.path.exists(documents_path):
        documents_path = os.path.expanduser("~/文档")  # 兼容中文 Windows
    if not os.path.exists(documents_path):
        documents_path = os.path.expanduser("~")  # 实在找不到，用用户根目录兜底

    print(f"\n在目录: {documents_path} 下查找 SillyTavern 文件夹...")
    sillytavern_dir_path = None
    for root, dirs, _ in os.walk(documents_path):
        if "SillyTavern" in dirs:
            sillytavern_dir_path = os.path.join(root, "SillyTavern")
            break

    if sillytavern_dir_path:
        chats_path = os.path.join(sillytavern_dir_path, "data", "default-user", "chats")
        if os.path.exists(chats_path):
            print(f"找到 chats 目录: {chats_path}")
            return chats_path

    # 未找到或用户希望手动选择
    messagebox.showinfo("提示", "未自动找到 chats 目录或要手动选择，请选择 SillyTavern 的 chats 目录。")
    chats_path = filedialog.askdirectory(title="请选择 SillyTavern 的 chats 目录")
    return chats_path  # 无论是否选择，都返回


def select_folders_and_files(chats_path):
    # 手动选择要删除的文件夹和文件
    if not chats_path:
        return [], []

    folder_names = [
        d for d in os.listdir(chats_path) if os.path.isdir(os.path.join(chats_path, d))
    ]
    if not folder_names:
        messagebox.showinfo("提示", "chats 目录下没有子文件夹。")
        return [], []

    def toggle_select_all_folders():
        # 全选/取消全选 文件夹
        for i in range(len(folder_names)):
            folder_vars[i].set(select_all_folders_var.get())
        update_file_list()

    def update_file_list():
        # 更新文件列表（使用滚动列表）
        file_list.delete(0, tk.END)
        selected_folders = [
            folder_names[i] for i, var in enumerate(folder_vars) if var.get()
        ]

        for folder_name in selected_folders:
            folder_path = os.path.join(chats_path, folder_name)
            file_names = [
                f
                for f in os.listdir(folder_path)
                if os.path.isfile(os.path.join(folder_path, f)) and f.endswith(".jsonl")
            ]
            for file_name in file_names:
                file_list.insert(tk.END, f"{folder_name}/{file_name}")

    def get_selected_items():
        selected_folders = [folder_names[i] for i, var in enumerate(folder_vars) if var.get()]
        selected_files = [file_list.get(i) for i in file_list.curselection()]
        return selected_folders, selected_files

     # 创建主窗口
    window = tk.Tk()
    window.title("选择要删除的文件夹和文件")
    window.geometry("800x650")  # 扩大窗口
    style = ttk.Style()
    style.configure("TLabel", font=("Arial", 12))
    style.configure("TButton", font=("Arial", 12))
    style.configure("TCheckbutton", font=("Arial", 12))

    # 文件夹选择区域（使用带滚动条的 Listbox）
    folder_frame = ttk.LabelFrame(window, text="文件夹 (选择后在右侧显示文件)")
    folder_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    select_all_folders_var = tk.BooleanVar()
    select_all_folders_check = ttk.Checkbutton(
        folder_frame,
        text="全选/取消全选",
        variable=select_all_folders_var,
        command=toggle_select_all_folders,
    )
    select_all_folders_check.pack(anchor=tk.W)

    # 使用 Listbox 替换 Checkbutton 列表，并添加滚动条
    folder_listbox = tk.Listbox(folder_frame, selectmode=tk.MULTIPLE, font=("Arial", 12), exportselection=False)
    folder_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    folder_scrollbar = ttk.Scrollbar(folder_frame, command=folder_listbox.yview)
    folder_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    folder_listbox.config(yscrollcommand=folder_scrollbar.set)

    folder_vars = []
    for folder_name in folder_names:
        var = tk.BooleanVar(value=False)
        folder_vars.append(var)
        folder_listbox.insert(tk.END, folder_name)

        def on_folder_select(event, index=len(folder_vars)-1, var=var):
            if folder_listbox.curselection():
                var.set(index in folder_listbox.curselection())
                update_file_list()

        folder_listbox.bind("<<ListboxSelect>>", on_folder_select)

    # 文件选择区域
    file_frame = ttk.LabelFrame(window, text="文件 (仅显示 .jsonl 文件)")
    file_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    file_list = tk.Listbox(file_frame, selectmode=tk.MULTIPLE, font=("Arial", 12))
    file_list.pack(fill=tk.BOTH, expand=True)
    file_scrollbar = ttk.Scrollbar(file_frame, command=file_list.yview)
    file_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    file_list.config(yscrollcommand=file_scrollbar.set)

    def confirm_selection():
        selected_folders, selected_files = get_selected_items()
        window.destroy()
        if not selected_folders and not selected_files:
            messagebox.showinfo("提示", "未选择任何文件夹或文件。")
            return

        confirm_window = tk.Toplevel()
        confirm_window.title("确认删除")
        confirm_window.geometry("500x400")

        confirm_text = (
            "确定删除以下项目吗？\n\n文件夹:\n"
            + "\n".join(selected_folders)
            + "\n\n文件:\n"
            + "\n".join(selected_files)
        )

        text_widget = scrolledtext.ScrolledText(confirm_window, wrap=tk.WORD, font=("Arial", 12))
        text_widget.insert(tk.END, confirm_text)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        def execute_deletion():
            confirm_window.destroy()
            delete_selected_folders_and_files(chats_path, selected_folders, selected_files)
            update_stats()

        confirm_button = ttk.Button(confirm_window, text="确认删除", command=execute_deletion)
        confirm_button.pack(pady=10)

    confirm_button = ttk.Button(window, text="确认选择", command=confirm_selection)
    confirm_button.pack(pady=10)

    update_file_list()
    window.mainloop()




def delete_selected_folders_and_files(chats_path, selected_folders, selected_files):
    # 删除选定的文件夹和文件
    total_size = 0
    deleted_count = 0
    # 删除文件夹
    for folder_name in selected_folders:
        folder_path = os.path.join(chats_path, folder_name)
        try:
            folder_size = get_folder_size(folder_path)
            shutil.rmtree(folder_path)
            total_size += folder_size
            deleted_count += 1
            print(f"已删除文件夹: {folder_name}")
        except Exception as e:
            print(f"删除文件夹 {folder_name} 失败: {e}")

    # 删除文件
    for file_path_rel in selected_files:
        file_path = os.path.join(chats_path, file_path_rel)
        try:
            file_size = os.path.getsize(file_path)
            os.remove(file_path)
            total_size += file_size
            deleted_count += 1
            print(f"已删除文件: {file_path_rel}")
        except Exception as e:
            print(f"删除文件 {file_path_rel} 失败: {e}")
    messagebox.showinfo(
        "提示",
        f"已删除 {deleted_count} 个项目, 共节省 {total_size / 1024:.2f} KB ({total_size / (1024 * 1024):.2f} MB) 空间。",
    )


def get_folder_size(folder_path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size


def auto_delete_empty_folders(chats_path):
    # 自动检查空文件夹删除 (仅处理空文件夹)
    if not chats_path:
        return
    print("\n--- 自动检查空文件夹删除 ---")
    deleted_folders = []
    for root, dirs, files in os.walk(
        chats_path, topdown=False
    ):  # topdown=False 保证先删除子文件夹
        for dir_name in dirs:
            folder_path = os.path.join(root, dir_name)
            if not os.listdir(folder_path):  # 检查文件夹是否为空
                try:
                    os.rmdir(folder_path)  # 只删除空文件夹
                    deleted_folders.append(folder_path)
                except Exception as e:
                    print(f"删除空文件夹 {folder_path} 失败: {e}")

    if deleted_folders:
        messagebox.showinfo("提示", "已删除以下空文件夹:\n" + "\n".join(deleted_folders))
    else:
        messagebox.showinfo("提示", "没有找到空文件夹。")


def delete_small_old_jsonl_files(chats_path):
    if not chats_path:
        return

    print("\n--- 删除小于/大于 指定大小 且 修改时间早于/晚于 指定时间 的 .jsonl 文件 ---")

    def get_size_and_date_criteria():
        # 获取用户输入的大小和时间条件以及排除规则的窗口
        def apply_criteria():
            # 应用条件并关闭窗口
            try:
                size_limit = float(size_entry.get())
                size_comparison = size_comparison_var.get()
                date_limit_str = date_entry.get()
                date_comparison = date_comparison_var.get()

                # 验证日期格式
                datetime.datetime.strptime(date_limit_str, "%Y-%m-%d")
                criteria_window.destroy()

                nonlocal size_limit_kb, date_limit, size_comp, date_comp
                size_limit_kb = size_limit
                date_limit = date_limit_str
                size_comp = size_comparison
                date_comp = date_comparison

            except ValueError:
                messagebox.showerror("错误", "请输入有效的数字大小(KB)和日期(YYYY-MM-DD)。")

        # 设置默认值
        size_limit_kb = 10.0
        date_limit = (datetime.datetime.now() - datetime.timedelta(days=90)).strftime(
            "%Y-%m-%d"
        )
        size_comp = "<="  # 默认小于等于
        date_comp = "<"  # 默认早于

        criteria_window = tk.Toplevel()
        criteria_window.title("设置文件大小和时间条件")
        criteria_window.geometry("480x420")  # 增大窗口以容纳排除规则部分

        # 文件大小
        size_frame = ttk.Frame(criteria_window, padding=10)
        size_frame.pack(fill=tk.X)
        ttk.Label(size_frame, text="文件大小 (KB):").pack(side=tk.LEFT)
        size_entry = ttk.Entry(size_frame, width=10)
        size_entry.insert(0, str(size_limit_kb))  # 默认值
        size_entry.pack(side=tk.LEFT, padx=5)

        size_comparison_var = tk.StringVar(value=size_comp)  # 默认小于等于
        ttk.Radiobutton(
            size_frame, text="小于等于", variable=size_comparison_var, value="<="
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(size_frame, text="大于", variable=size_comparison_var, value=">").pack(
            side=tk.LEFT
        )

        # 修改时间
        date_frame = ttk.Frame(criteria_window, padding=10)
        date_frame.pack(fill=tk.X)
        ttk.Label(date_frame, text="修改时间 (YYYY-MM-DD):").pack(side=tk.LEFT)
        date_entry = ttk.Entry(date_frame, width=15)
        date_entry.insert(0, date_limit)  # 默认值
        date_entry.pack(side=tk.LEFT, padx=5)

        date_comparison_var = tk.StringVar(value=date_comp)  # 默认早于
        ttk.Radiobutton(date_frame, text="早于", variable=date_comparison_var, value="<").pack(
            side=tk.LEFT
        )
        ttk.Radiobutton(
            date_frame, text="晚于", variable=date_comparison_var, value=">="
        ).pack(side=tk.LEFT)

        # 排除规则部分
        exclusion_frame = ttk.Frame(criteria_window, padding=10)
        exclusion_frame.pack(fill=tk.X)
        ttk.Label(exclusion_frame, text="排除条件 (部分匹配文件名):").pack()

        exclusion_manager = ExclusionManager()

        default_exclusions = ["碧蓝", "航线", "档案", "世界", "食堂", "新闻"]

        # 使用 Combobox
        exclusion_combobox = ttk.Combobox(exclusion_frame, values=default_exclusions, width=20)
        exclusion_combobox.pack(pady=5)

        def update_exclusion_combobox():
            available_exclusions = [
                item for item in default_exclusions if item not in exclusion_manager.get_exclusions()
            ]
            exclusion_combobox['values'] = available_exclusions
            if available_exclusions:
                exclusion_combobox.set(available_exclusions[0])
            else:
                exclusion_combobox.set("")

        def update_exclusion_display():
            exclusion_list.delete(0, tk.END)
            for item in exclusion_manager.get_exclusions():
                exclusion_list.insert(tk.END, item)

        def add_exclusion_command():
            exclusion_text = exclusion_combobox.get().strip()
            if exclusion_text:
                exclusion_manager.add_exclusion(exclusion_text)
                update_exclusion_display()
                update_exclusion_combobox()

        add_button = ttk.Button(exclusion_frame, text="添加", command=add_exclusion_command)
        add_button.pack()

        # 删除选中 和 清空 按钮的 Frame
        button_frame = ttk.Frame(exclusion_frame)
        button_frame.pack(pady=5)

        def remove_selected_exclusion():
            selected_index = exclusion_list.curselection()
            if selected_index:
                selected_exclusion = exclusion_list.get(selected_index[0])
                exclusion_manager.remove_exclusion(selected_exclusion)
                update_exclusion_display()
                update_exclusion_combobox()

        remove_button = ttk.Button(button_frame, text="删除选中", command=remove_selected_exclusion)
        remove_button.pack(side=tk.LEFT, padx=2)

        def clear_exclusions_command():
            exclusion_manager.clear_exclusions()
            update_exclusion_display()
            update_exclusion_combobox()

        clear_button = ttk.Button(button_frame, text="清空", command=clear_exclusions_command)
        clear_button.pack(side=tk.LEFT, padx=2)

        # 排除条件显示 (Listbox)
        exclusion_list = tk.Listbox(criteria_window, height=4, width=50)
        exclusion_list.pack(pady=5)
        update_exclusion_display()
        update_exclusion_combobox()

        apply_button = ttk.Button(criteria_window, text="应用", command=apply_criteria)
        apply_button.pack(pady=10)

        criteria_window.wait_window()

        return size_limit_kb, date_limit, size_comp, date_comp, exclusion_manager

    size_limit_kb, date_limit_str, size_comparison, date_comparison, exclusion_manager = (
        get_size_and_date_criteria()
    )
    date_limit = datetime.datetime.strptime(date_limit_str, "%Y-%m-%d")

    def show_file_selection_window(files_to_delete):
        window = tk.Toplevel()
        window.title("选择要删除的文件")
        window.geometry("900x700")
        style = ttk.Style()
        style.configure("TLabel", font=("Arial", 12))
        style.configure("TButton", font=("Arial", 12))
        style.configure("TCheckbutton", font=("Arial", 12))

        def select_all_files():
            listbox.select_set(0, tk.END)

        select_all_button = ttk.Button(window, text="全选", command=select_all_files)
        select_all_button.pack(pady=5)

        listbox = tk.Listbox(
            window, selectmode=tk.MULTIPLE, width=100, height=15, font=("Arial", 12)
        )
        listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(window)
        button_frame.pack(pady=10)

        def update_file_list():
            listbox.delete(0, tk.END)
            for file_info in files_to_delete:
                if not exclusion_manager.matches_any(file_info['name']):
                    listbox.insert(
                        tk.END,
                        f"{file_info['name']} (修改时间: {file_info['modified_time'].strftime('%Y-%m-%d %H:%M:%S')}, 大小: {file_info['size_kb']:.2f} KB)",
                    )
                    listbox.itemconfig(tk.END, fg="blue")

        def delete_selected_files():
            selected_indices = listbox.curselection()
            selected_files = [files_to_delete[i] for i in selected_indices]

            window.destroy()

            if not selected_files:
                messagebox.showinfo("提示", "未选择任何文件。")
                return

            confirm_window = tk.Toplevel()
            confirm_window.title("确认删除")
            confirm_window.geometry("500x400")

            total_size_kb = sum(file_info["size_kb"] for file_info in selected_files)
            delete_text = "以下文件将被删除：\n"
            for file_info in selected_files:
                delete_text += f"- {file_info['name']}, 修改时间: {file_info['modified_time'].strftime('%Y-%m-%d %H:%M:%S')}, 大小: {file_info['size_kb']:.2f} KB\n"
            delete_text += f"\n总大小: {total_size_kb:.2f} KB ({total_size_kb/1024:.2f} MB)"

            text_widget = scrolledtext.ScrolledText(
                confirm_window, wrap=tk.WORD, font=("Arial", 12)
            )
            text_widget.insert(tk.END, delete_text)
            text_widget.config(state=tk.DISABLED)
            text_widget.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

            def confirm_deletion():
                confirm_window.destroy()
                deleted_count = 0
                deleted_size_kb = 0
                for file_info in selected_files:
                    try:
                        os.remove(file_info["path"])
                        deleted_count += 1
                        deleted_size_kb += file_info["size_kb"]
                    except Exception as e:
                        print(f"删除文件 {file_info['name']} 失败: {e}")
                messagebox.showinfo(
                    "提示",
                    f"已删除 {deleted_count} 个文件, 共节省 {deleted_size_kb:.2f} KB ({deleted_size_kb/1024:.2f} MB) 空间。",
                )
                update_stats()

            confirm_button = ttk.Button(
                confirm_window, text="确认删除", command=confirm_deletion
            )
            confirm_button.pack(pady=10)
            confirm_window.wait_window()

        delete_button = ttk.Button(button_frame, text="删除所选文件", command=delete_selected_files)
        delete_button.pack()

        update_file_list()
        window.wait_window()

    # 在进入 show_file_selection_window 之前，先根据条件初步筛选文件
    preliminary_files_to_delete = []
    for root, _, files in os.walk(chats_path):
        for file_name in files:
            if file_name.endswith(".jsonl"):
                file_path = os.path.join(root, file_name)
                try:
                    file_size_kb = os.path.getsize(file_path) / 1024
                    modified_time = datetime.datetime.fromtimestamp(
                        os.path.getmtime(file_path)
                    )

                    size_condition = (
                        file_size_kb <= size_limit_kb
                        if size_comparison == "<="
                        else file_size_kb > size_limit_kb
                    )
                    date_condition = (
                        modified_time < date_limit
                        if date_comparison == "<"
                        else modified_time >= date_limit
                    )

                    if size_condition and date_condition:
                        preliminary_files_to_delete.append(
                            {
                                "name": file_name,
                                "path": file_path,
                                "modified_time": modified_time,
                                "size_kb": file_size_kb,
                            }
                        )
                except Exception as e:
                    print(f"处理文件 {file_name} 时出错：{e}")

    if not preliminary_files_to_delete:
        messagebox.showinfo(
            "提示",
            f"没有找到符合条件的文件 ({'小于等于' if size_comparison == '<=' else '大于'} {size_limit_kb} KB 且 {'早于' if date_comparison == '<' else '晚于'} {date_limit_str})。",
        )
        return
    show_file_selection_window(preliminary_files_to_delete)

def main():
    # 主函数 - 使用 Tkinter 菜单, 并允许切换 chats 目录
    def select_new_chats_path():
        # 选择新的 chats 目录
        nonlocal chats_path
        new_chats_path = filedialog.askdirectory(title="请选择 SillyTavern 的 chats 目录")
        if new_chats_path:  # 只要用户选择了路径，就更新
            chats_path = new_chats_path
            messagebox.showinfo("提示", f"已切换到 chats 目录: {chats_path}")
            chats_path_label.config(text=f"当前 chats 目录: {chats_path}")  # 更新标签
            update_stats()

    chats_path = find_sillytavern_chats_path()  # 初始查找
    if not chats_path:
        messagebox.showerror("错误", "无法执行清理操作，请检查 chats 目录路径。")
        return

    def show_manual_delete_window():
        select_folders_and_files(chats_path)
        update_stats()

    def show_auto_delete_empty_folders():
        auto_delete_empty_folders(chats_path)
        update_stats()  # 删除后更新统计

    def show_delete_small_old_files():
        delete_small_old_jsonl_files(chats_path)
        update_stats()  # 更新统计信息

    # 更新统计信息
    def update_stats():
        nonlocal chats_path
        num_folders = 0
        num_jsonl_files = 0
        if chats_path and os.path.exists(chats_path):
            for _, dirs, files in os.walk(chats_path):
                num_folders += len(dirs)
                num_jsonl_files += sum(1 for f in files if f.endswith(".jsonl"))

        stats_label.config(
            text=f"文件夹数量: {num_folders},  .jsonl 文件数量: {num_jsonl_files}"
        )

    root = tk.Tk()
    root.title("SillyTavern Chats 清理工具")
    root.geometry("500x450")  # 扩大窗口
    style = ttk.Style()
    style.configure("TLabel", font=("Arial", 12))  # 设置字体大小
    style.configure("TButton", font=("Arial", 12))
    style.configure("TCheckbutton", font=("Arial", 12))

    # 创建菜单
    menu_bar = tk.Menu(root)
    root.config(menu=menu_bar)

    file_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="文件", menu=file_menu)
    file_menu.add_command(label="选择 chats 目录", command=select_new_chats_path)  # 添加选择目录选项
    file_menu.add_command(label="退出", command=root.destroy)

    options_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="选项", menu=options_menu)
    options_menu.add_command(label="手动选择删除", command=show_manual_delete_window)
    options_menu.add_command(label="自动删除空文件夹", command=show_auto_delete_empty_folders)
    options_menu.add_command(
        label="删除符合条件的 .jsonl 文件", command=show_delete_small_old_files
    )

    # 添加当前 chats 目录显示标签, 初始就显示
    chats_path_label = ttk.Label(
        root, text=f"当前 chats 目录: {chats_path}", wraplength=480
    )  # 限制宽度自动换行
    chats_path_label.pack(pady=5)

    # 统计信息标签
    stats_label = ttk.Label(root, text="")
    stats_label.pack(pady=5)
    update_stats()  # 初始更新统计信息

    # 创建主界面按钮（可选）
    manual_button = ttk.Button(root, text="手动选择删除", command=show_manual_delete_window)
    manual_button.pack(pady=10)

    auto_button = ttk.Button(
        root, text="自动删除空文件夹", command=show_auto_delete_empty_folders
    )
    auto_button.pack(pady=10)

    auto_small_button = ttk.Button(
        root, text="删除符合条件的 .jsonl 文件", command=show_delete_small_old_files
    )
    auto_small_button.pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    main()