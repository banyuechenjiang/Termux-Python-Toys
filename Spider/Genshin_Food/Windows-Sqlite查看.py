import sqlite3
import os
from urllib import parse
from bs4 import BeautifulSoup
import html
import textwrap
import tkinter as tk
from tkinter import ttk, filedialog

# --- 配置常量 ---
MAX_VALUE_DISPLAY_LENGTH = 5000  # value列内容显示的最大字符数，超出则截断
TARGET_AUTO_LOAD_TABLE = "responses" # 自动加载的目标表名
ROWS_PER_PAGE = 50 # 每次加载的行数（用于分页）

# --- 全局变量（用于分页状态） ---
current_db_path_for_paging = None
current_table_name_for_paging = None
current_loaded_rows_count = 0
current_total_rows_in_table = 0

def smart_decode(data):
    """智能解码：尝试多种编码，尽可能将字节数据解码为中文，并处理字符串中的转义。"""
    if isinstance(data, bytes):
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return data.decode('gbk')
            except UnicodeDecodeError:
                try:
                    return data.decode('gb2312')
                except UnicodeDecodeError:
                    return data.decode('utf-8', errors='replace')
    elif isinstance(data, str):
        temp_str = data
        if '\\u' in temp_str:
            try:
                # 避免过度解码，例如，如果字符串是 '\\u' 而不是 '\u'
                if not temp_str.startswith('\\\\u') and '\\\\u' not in temp_str:
                    decoded_unicode_escape = temp_str.encode('latin-1', errors='ignore').decode('unicode_escape', errors='ignore')
                    if decoded_unicode_escape != temp_str :
                        temp_str = decoded_unicode_escape
            except Exception:
                pass
        return decode_and_unquote(temp_str)
    else:
        return str(data)

def decode_and_unquote(text):
    """处理字符串类型的“编码”：将 \\x 替换为 %，使用 urllib.parse.unquote() 解码。"""
    if not isinstance(text, str):
        return str(text)
    try:
        processed_text = text.replace('\\x', '%').replace('\\X', '%')
        return parse.unquote(processed_text)
    except Exception:
        return text

def clean_html(html_content):
    """清洗 HTML 内容：去除标签、多余空白、转换实体。"""
    try:
        soup = BeautifulSoup(html_content, "lxml")
        text = soup.get_text(separator=" ", strip=True)
        text = html.unescape(text)
        text = " ".join(text.split())
        return text
    except Exception:
        return html_content

def display_table_content(db_path, table_name, text_widget, clean_html_var, search_term=None,
                          offset=0, limit=ROWS_PER_PAGE, append_mode=False, status_bar_update_func=None,
                          load_more_button_update_func=None, paging_info_label_update_func=None):
    """
    显示指定 SQLite 表的内容，支持分页、HTML 清洗和搜索。
    append_mode: True 表示追加内容，False 表示清空并加载第一页。
    """
    global current_db_path_for_paging, current_table_name_for_paging
    global current_loaded_rows_count, current_total_rows_in_table

    text_widget.config(state=tk.NORMAL)
    if not append_mode:
        text_widget.delete("1.0", tk.END)
        current_loaded_rows_count = 0 # 重置已加载行数
        current_total_rows_in_table = 0 # 重置总行数

    if not db_path or not table_name:
        text_widget.insert(tk.END, "请先选择数据库文件和表。\n")
        text_widget.config(state=tk.DISABLED)
        if status_bar_update_func: status_bar_update_func("请先选择数据库和表")
        if load_more_button_update_func: load_more_button_update_func(tk.DISABLED, "加载更多")
        if paging_info_label_update_func: paging_info_label_update_func("")
        return

    # 更新全局分页状态变量
    current_db_path_for_paging = db_path
    current_table_name_for_paging = table_name

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if not append_mode:
            # 获取总行数
            cursor.execute(f"SELECT COUNT(*) FROM \"{table_name}\";")
            current_total_rows_in_table = cursor.fetchone()[0]

            # 显示表头和列信息 (仅在首次加载时)
            text_widget.insert(tk.END, f"表: {table_name} (总行数: {current_total_rows_in_table})\n{'-' * (len(table_name) + 6)}\n")
            cursor.execute(f"PRAGMA table_info(\"{table_name}\");")
            columns_info = cursor.fetchall()
            if not columns_info:
                text_widget.insert(tk.END, "无法获取列信息或表为空结构。\n")
                text_widget.config(state=tk.DISABLED)
                if status_bar_update_func: status_bar_update_func("无法获取列信息")
                if load_more_button_update_func: load_more_button_update_func(tk.DISABLED, "加载更多")
                if paging_info_label_update_func: paging_info_label_update_func("")
                return
            columns = [col[1] for col in columns_info]
            text_widget.insert(tk.END, "列: " + ", ".join(columns) + "\n" + "-" * 20 + "\n")
        else: # append_mode
            # 需要从某处获取列名，或者假设它们在第一次加载时已设置
            # 简单起见，这里我们假设非追加模式总会先运行
            # 更健壮的做法是在GUI中存储列名
            # For now, we'll just proceed. If columns are needed for append, this needs adjustment.
            pass

        # 获取列名 (再次获取，确保在 append_mode 下也可用)
        cursor.execute(f"PRAGMA table_info(\"{table_name}\");")
        columns = [col[1] for col in cursor.fetchall()]


        # 分页查询数据
        query = f"SELECT * FROM \"{table_name}\" LIMIT ? OFFSET ?;"
        cursor.execute(query, (limit, offset))
        rows = cursor.fetchall()

        if rows:
            for row_num_in_page, row_data in enumerate(rows):
                actual_row_num = offset + row_num_in_page + 1
                text_widget.insert(tk.END, f"--- 行 {actual_row_num} ---\n")
                for col_num, item in enumerate(row_data):
                    current_column_name = columns[col_num]
                    decoded_item = smart_decode(item)
                    display_item_str = str(decoded_item)

                    if current_column_name.lower() == 'value':
                        original_len = len(display_item_str)
                        if clean_html_var.get():
                            if "<" in display_item_str and ">" in display_item_str :
                                cleaned_value = clean_html(display_item_str)
                                if len(cleaned_value) > MAX_VALUE_DISPLAY_LENGTH:
                                    display_item_str = cleaned_value[:MAX_VALUE_DISPLAY_LENGTH] + \
                                        f"\n... (已清洗, 原长 {original_len}, 清洗后 {len(cleaned_value)}, 显示前 {MAX_VALUE_DISPLAY_LENGTH} 字符)"
                                else:
                                    display_item_str = cleaned_value
                            elif original_len > MAX_VALUE_DISPLAY_LENGTH:
                                display_item_str = display_item_str[:MAX_VALUE_DISPLAY_LENGTH] + \
                                    f"\n... (原长 {original_len}, 显示前 {MAX_VALUE_DISPLAY_LENGTH} 字符)"
                        elif original_len > MAX_VALUE_DISPLAY_LENGTH:
                             display_item_str = display_item_str[:MAX_VALUE_DISPLAY_LENGTH] + \
                                f"\n... (内容未清洗, 原长 {original_len}, 显示前 {MAX_VALUE_DISPLAY_LENGTH} 字符)"

                    if clean_html_var.get() and \
                       (current_column_name.lower() != 'value' or \
                        (current_column_name.lower() == 'value' and not ("... (已清洗" in display_item_str or "... (内容未清洗" in display_item_str))) and \
                       ("<" in display_item_str and ">" in display_item_str) :
                        cleaned_item = clean_html(display_item_str)
                        wrapped_item = textwrap.fill(cleaned_item, width=80, subsequent_indent='    ')
                        text_widget.insert(tk.END, f"  列 {current_column_name}:\n{wrapped_item}\n")
                    else:
                        wrapped_item = textwrap.fill(display_item_str, width=80, subsequent_indent='    ')
                        text_widget.insert(tk.END, f"  列 {current_column_name}: {wrapped_item}\n")
                text_widget.insert(tk.END, "-" * 20 + "\n")
            
            current_loaded_rows_count = offset + len(rows)
            if status_bar_update_func: status_bar_update_func(f"已加载 {current_loaded_rows_count} / {current_total_rows_in_table} 行")
        
        elif not append_mode and not rows: # 首次加载但表为空
            text_widget.insert(tk.END, "表中没有数据。\n")
            if status_bar_update_func: status_bar_update_func(f"表 '{table_name}' 为空")
            current_loaded_rows_count = 0


        # 更新分页信息和加载更多按钮状态
        if paging_info_label_update_func:
            paging_info_label_update_func(f"已显示: {current_loaded_rows_count} / {current_total_rows_in_table} 行")

        if load_more_button_update_func:
            if current_loaded_rows_count < current_total_rows_in_table:
                load_more_button_update_func(tk.NORMAL, f"加载下 {min(ROWS_PER_PAGE, current_total_rows_in_table - current_loaded_rows_count)} 行")
            else:
                load_more_button_update_func(tk.DISABLED, "已加载全部")
                if status_bar_update_func and current_total_rows_in_table > 0:
                    status_bar_update_func(f"已加载全部 {current_total_rows_in_table} 行")

    except sqlite3.Error as e:
        text_widget.insert(tk.END, f"SQLite 错误: {e}\n")
        if status_bar_update_func: status_bar_update_func(f"SQLite 错误: {e}")
        if load_more_button_update_func: load_more_button_update_func(tk.DISABLED, "加载更多")
        if paging_info_label_update_func: paging_info_label_update_func("错误")
    finally:
        if conn:
            conn.close()
        text_widget.config(state=tk.DISABLED) # 禁用编辑

    if search_term and text_widget.get("1.0", tk.END).strip(): # 确保有内容才搜索
        search_text(text_widget, search_term, highlight_only=True)

# ... (search_text function remains the same)
def search_text(text_widget, search_term, highlight_only=False):
    text_widget.config(state=tk.NORMAL)
    text_widget.tag_remove("search", "1.0", tk.END)

    if not search_term:
        text_widget.config(state=tk.DISABLED)
        return 0 # 返回找到的数量

    start_index = "1.0"
    first_match_index = None
    count = 0

    while True:
        pos = text_widget.search(search_term, start_index, stopindex=tk.END, nocase=True, count=tk.IntVar())
        if not pos:
            break
        
        if first_match_index is None:
            first_match_index = pos
            
        end_pos = f"{pos}+{len(search_term)}c"
        text_widget.tag_add("search", pos, end_pos)
        start_index = end_pos
        count +=1

    if first_match_index and not highlight_only:
        text_widget.mark_set(tk.INSERT, first_match_index) # 将光标移到第一个匹配项
        text_widget.see(first_match_index) # 滚动到第一个匹配项
        text_widget.focus_set() # 设置焦点，以便用户可以按Ctrl+F等
    
    text_widget.config(state=tk.DISABLED)
    return count

def create_gui():
    root = tk.Tk()
    root.title("SQLite 查看器")
    root.geometry("1000x750") # 稍微增加高度以容纳新控件

    current_file_path = tk.StringVar()
    # current_table_name is now handled by global current_table_name_for_paging for data loading
    # We can still use a local one for GUI state if needed, or rely on treeview selection
    gui_current_table_name = tk.StringVar() # For display/logic tied to treeview selection
    clean_html_var = tk.BooleanVar(value=True)
    search_term_var = tk.StringVar()

    status_bar = ttk.Label(root, text="准备就绪", relief=tk.SUNKEN, anchor=tk.W)
    status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def update_status(message):
        status_bar.config(text=message)
        root.update_idletasks()

    top_frame = ttk.Frame(root, padding=5)
    top_frame.pack(fill=tk.X)

    open_button = ttk.Button(top_frame, text="打开文件", command=lambda: open_file_action())
    open_button.pack(side=tk.LEFT, padx=5)

    clean_html_check = ttk.Checkbutton(top_frame, text="清洗 HTML", variable=clean_html_var, command=lambda: reload_current_view_action())
    clean_html_check.pack(side=tk.LEFT, padx=5)

    search_entry = ttk.Entry(top_frame, textvariable=search_term_var, width=30)
    search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    search_entry.bind("<Return>", lambda event: search_action())

    search_button = ttk.Button(top_frame, text="搜索", command=lambda: search_action())
    search_button.pack(side=tk.LEFT, padx=5)

    main_paned_window = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
    main_paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    left_frame = ttk.Frame(main_paned_window, padding=5)
    main_paned_window.add(left_frame, weight=1) # 调整权重，左侧窄一些

    table_tree_label = ttk.Label(left_frame, text="数据库表:")
    table_tree_label.pack(anchor=tk.NW)

    table_tree = ttk.Treeview(left_frame, show="headings", columns=("table_name",))
    table_tree.heading("table_name", text="表名")
    table_tree.column("table_name", anchor=tk.W, width=180)
    table_tree.pack(fill=tk.BOTH, expand=True, pady=(0,5))

    right_frame = ttk.Frame(main_paned_window, padding=5)
    main_paned_window.add(right_frame, weight=4) # 右侧宽一些

    text_widget = tk.Text(right_frame, wrap=tk.WORD, undo=True, state=tk.DISABLED, font=("Consolas", 10))
    text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    text_widget.tag_configure("search", background="yellow", foreground="black")

    scrollbar = ttk.Scrollbar(right_frame, command=text_widget.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    text_widget['yscrollcommand'] = scrollbar.set
    
    # --- Paging controls ---
    paging_controls_frame = ttk.Frame(right_frame, padding=(0, 5)) # Add padding below text_widget
    paging_controls_frame.pack(fill=tk.X, side=tk.BOTTOM)

    paging_info_label = ttk.Label(paging_controls_frame, text="未加载数据")
    paging_info_label.pack(side=tk.LEFT, padx=5)

    load_more_button = ttk.Button(paging_controls_frame, text="加载更多", state=tk.DISABLED,
                                 command=lambda: load_more_data_action())
    load_more_button.pack(side=tk.RIGHT, padx=5)

    def update_load_more_button(state, text):
        load_more_button.config(state=state, text=text)

    def update_paging_info_label(text):
        paging_info_label.config(text=text)


    def load_table_list(db_path):
        table_tree.delete(*table_tree.get_children())
        text_widget.config(state=tk.NORMAL)
        text_widget.delete("1.0", tk.END)
        text_widget.config(state=tk.DISABLED)
        gui_current_table_name.set("")
        update_load_more_button(tk.DISABLED, "加载更多")
        update_paging_info_label("未加载数据")
        global current_loaded_rows_count, current_total_rows_in_table
        current_loaded_rows_count = 0
        current_total_rows_in_table = 0


        if not db_path:
            update_status("未选择数据库文件")
            return

        conn = None
        auto_load_table_iid = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            tables = cursor.fetchall()

            if not tables:
                update_status(f"数据库 '{os.path.basename(db_path)}' 中没有表。")
                return

            for table_name_tuple in tables:
                table_name_str = table_name_tuple[0]
                iid = table_tree.insert("", tk.END, values=(table_name_str,), iid=table_name_str)
                if table_name_str.lower() == TARGET_AUTO_LOAD_TABLE.lower():
                    auto_load_table_iid = iid
            
            update_status(f"已加载 {len(tables)} 个表从 {os.path.basename(db_path)}")

            if auto_load_table_iid:
                table_tree.selection_set(auto_load_table_iid)
                table_tree.focus(auto_load_table_iid)
                # Manually trigger selection event logic (on_table_select will be called by <<TreeviewSelect>>)
                # The selection_set should trigger the event. If not, call on_table_select(None)
                # It seems selection_set does trigger the event, so direct call to display_table_content is removed here.
                # on_table_select will handle the initial load.
        except sqlite3.Error as e:
            update_status(f"SQLite 错误: {e}")
            text_widget.config(state=tk.NORMAL)
            text_widget.insert(tk.END, f"SQLite 错误: {e}\n")
            text_widget.config(state=tk.DISABLED)
        finally:
            if conn:
                conn.close()

    def on_table_select(event): # event can be None if called manually
        selected_item_iid = table_tree.focus() # Get focused item (which is usually the selected one)
        if not selected_item_iid: return # No item focused/selected

        selected_table_name = table_tree.item(selected_item_iid)['values'][0]
        
        # Check if the selected table is different from the one currently being paged
        # This prevents reloading the first page if the user clicks the same table again
        # while it's already displayed and potentially paged through.
        global current_table_name_for_paging
        if selected_table_name == current_table_name_for_paging and current_loaded_rows_count > 0:
             # Optional: Maybe just ensure search is reapplied if term exists
             # For now, do nothing if same table is re-selected and data is already loaded.
            if search_term_var.get():
                search_text(text_widget, search_term_var.get(), highlight_only=True)
            update_status(f"表 '{selected_table_name}' 已显示。")
            return

        gui_current_table_name.set(selected_table_name)
        update_status(f"正在加载表: {selected_table_name}...")
        
        # Load first page
        display_table_content(
            current_file_path.get(),
            selected_table_name,
            text_widget,
            clean_html_var,
            search_term_var.get(), # Pass search term for initial highlighting
            offset=0,
            limit=ROWS_PER_PAGE,
            append_mode=False, # This is a new table selection, so clear and load
            status_bar_update_func=update_status,
            load_more_button_update_func=update_load_more_button,
            paging_info_label_update_func=update_paging_info_label
        )
        # scroll to top
        text_widget.see("1.0")

    table_tree.bind("<<TreeviewSelect>>", on_table_select)

    def open_file_action():
        initial_dir = os.path.dirname(current_file_path.get()) if current_file_path.get() else os.path.dirname(os.path.abspath(__file__))
        file_path = filedialog.askopenfilename(
            title="选择 SQLite 文件",
            initialdir=initial_dir,
            filetypes=[("SQLite files", "*.sqlite *.db *.sqlite3"), ("All files", "*.*")],
        )
        if file_path:
            current_file_path.set(file_path)
            root.title(f"SQLite 查看器 - {os.path.basename(file_path)}")
            update_status(f"正在打开文件: {os.path.basename(file_path)}...")
            load_table_list(file_path)
        else:
            update_status("取消打开文件")

    def reload_current_view_action(): # Used by "Clean HTML" checkbox
        global current_db_path_for_paging, current_table_name_for_paging
        if current_db_path_for_paging and current_table_name_for_paging:
            update_status(f"重新加载表: {current_table_name_for_paging}...")
            # Reload from the beginning (offset 0) with the new clean_html setting
            display_table_content(
                current_db_path_for_paging,
                current_table_name_for_paging,
                text_widget,
                clean_html_var,
                search_term_var.get(),
                offset=0, # Reload from the start
                limit=ROWS_PER_PAGE, # Load first page
                append_mode=False, # Clear existing content
                status_bar_update_func=update_status,
                load_more_button_update_func=update_load_more_button,
                paging_info_label_update_func=update_paging_info_label
            )
            text_widget.see("1.0")
        elif not current_file_path.get():
            update_status("请先打开一个数据库文件")
        else:
            update_status("请先选择一个表")

    def load_more_data_action():
        global current_db_path_for_paging, current_table_name_for_paging, current_loaded_rows_count
        if current_db_path_for_paging and current_table_name_for_paging and current_loaded_rows_count < current_total_rows_in_table:
            update_status(f"加载更多数据 ({current_table_name_for_paging})...")
            display_table_content(
                current_db_path_for_paging,
                current_table_name_for_paging,
                text_widget,
                clean_html_var,
                search_term_var.get(),
                offset=current_loaded_rows_count, # Start from where we left off
                limit=ROWS_PER_PAGE,
                append_mode=True, # Append to existing content
                status_bar_update_func=update_status,
                load_more_button_update_func=update_load_more_button,
                paging_info_label_update_func=update_paging_info_label
            )
            # scroll to near the newly added content
            text_widget.see(f"end -{ROWS_PER_PAGE*5}l") # Heuristic to scroll up a bit from the absolute end
        else:
            update_status("没有更多数据可加载或未选择表。")


    def search_action():
        global current_table_name_for_paging
        if current_file_path.get() and current_table_name_for_paging:
            term = search_term_var.get()
            # If search term is cleared, just remove highlights from current view
            if not term:
                text_widget.config(state=tk.NORMAL)
                text_widget.tag_remove("search", "1.0", tk.END)
                text_widget.config(state=tk.DISABLED)
                update_status("搜索词为空，已清除高亮")
                return

            update_status(f"在当前视图中搜索 '{term}'...")
            # Search only in the currently loaded content
            # For a full DB search, it would be more complex, potentially requiring a new query
            count = search_text(text_widget, term) # search_text now handles its own state changes
            update_status(f"在当前加载的 '{current_table_name_for_paging}' 内容中找到 {count} 个 '{term}' 匹配项")

        elif not current_file_path.get():
             update_status("请先打开文件并选择表以进行搜索")
        else:
            update_status("请先选择一个表以进行搜索")

    return root

def main():
    root = create_gui()
    root.mainloop()

if __name__ == "__main__":
    main()
