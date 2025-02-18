# 这是一个代码块，用于完整展示代码，请勿省略。
import json
import os
import tkinter as tk
from tkinter import font, scrolledtext, messagebox

config = None #  全局变量存储 config_data, 初始化为 None
filename = None # 全局变量存储 filename

def load_config(filepath):
    # 加载 JSON 配置文件
    global config, filename # 声明使用全局变量
    filename = filepath #  更新全局 filename
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        messagebox.showerror("错误", f"配置文件 {filepath} 未找到。")
        return None
    except json.JSONDecodeError:
        messagebox.showerror("错误", f"配置文件 {filepath} JSON 格式解析失败。")
        return None

def get_prompt_name_by_identifier(identifier): #  移除 config 参数，使用全局 config
    # 根据 identifier 获取 prompts 列表中对应的 name
    global config
    if not config or 'prompts' not in config: # 检查 config 是否加载
        return '配置未加载'
    for prompt in config.get('prompts', []):
        if prompt.get('identifier') == identifier:
            return prompt.get('name', '未知名称')
    return '未找到名称'

def get_prompt_content_by_identifier(identifier): # 移除 config 参数，使用全局 config
    # 根据 identifier 获取 prompts 列表中对应的 content
    global config
    if not config or 'prompts' not in config: # 检查 config 是否加载
        return '配置未加载'
    for prompt in config.get('prompts', []):
        if prompt.get('identifier') == identifier:
            return prompt.get('content', '无内容')
    return '未找到内容'


def format_prompt_order_status_text(): #  移除 config, filename 参数，使用全局变量
    # 格式化 prompt_order 状态文本，用于 GUI Text 组件显示，返回文本内容和 tags 列表
    global config, filename
    if not config or not filename: # 检查 config 和 filename 是否加载
        return [{'text': "未加载配置文件。\n", 'tags': ('warning',)}] # 返回警告信息

    output_text_segments = [] # 存储文本段和 tag 的列表

    output_text_segments.append({'text': f"📜  {filename} - Prompt Order 状态:\n\n", 'tags': ('bold',)}) # 标题, 使用粗体 tag，移除 **
    prompt_order_list = config.get('prompt_order', [])
    if not prompt_order_list:
        output_text_segments.append({'text': "prompt_order 为空。\n", 'tags': ()})
        return output_text_segments

    for char_prompt_order in prompt_order_list:
        char_id = char_prompt_order.get('character_id')
        order_list = char_prompt_order.get('order', [])
        if not order_list:
            continue # 如果 order 为空，跳过当前 character_id，不输出空的角色 ID 行

        has_non_default_prompts = False # 标记是否有非默认 prompt
        prompt_items_segments = [] # 存储当前 character_id 的 prompt item 段
        last_enabled_status = None #  记录上一个 prompt 的启用状态，用于添加间隔

        for prompt_item in order_list:
            identifier = prompt_item.get('identifier')
            enabled = prompt_item.get('enabled')
            prompt_name = get_prompt_name_by_identifier(identifier) #  使用全局 config, 移除 config 参数

            # 排除默认 identifier
            if identifier in ["main", "worldInfoBefore", "charDescription", "charPersonality", "scenario", "enhanceDefinitions", "nsfw", "worldInfoAfter", "dialogueExamples", "chatHistory", "jailbreak"]:
                continue # 跳过默认 prompt

            has_non_default_prompts = True # 发现非默认 prompt，设置标记

            if last_enabled_status is not None and enabled != last_enabled_status: # 状态变化时添加空行
                prompt_items_segments.append({'text': "\n", 'tags': ()}) # 添加空行

            if enabled:
                prompt_items_segments.append({'text': f"- {prompt_name} (启用)\n", 'tags': ()}) # 启用，无特殊 tag
            else:
                prompt_items_segments.append({'text': f"- {prompt_name} (禁用)\n", 'tags': ('disabled',)}) # 禁用，使用 disabled tag

            last_enabled_status = enabled # 更新上一个 prompt 的状态

        if has_non_default_prompts: # 只有当有非默认 prompt 时才输出 角色 ID 行
            prompt_items_segments.insert(0, {'text': f"\n角色 ID: {char_id}:\n", 'tags': ('bold',)}) # 角色ID 粗体，移除 ** , insert to the beginning
            output_text_segments.extend(prompt_items_segments) # 添加 prompt item 段

    return output_text_segments


def view_prompt_contents_gui(root): # 修改函数名，移除 config, filename 参数
    # 在 GUI 中显示 prompt 内容查看界面，按钮列表可滚动，鼠标滚轮支持, 按 Prompt Order 排序
    global config, filename # 声明使用全局变量

    if not config or not filename: # 检查 config 和 filename 是否加载
        messagebox.showerror("错误", "请先加载配置文件。") # 提示先加载文件
        return

    content_window = tk.Toplevel(root)
    content_window.title(f"{filename} - Prompt 内容查看") # 修改标题

    main_frame = tk.Frame(content_window) # 使用主框架
    main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    button_canvas = tk.Canvas(main_frame, highlightthickness=0) # 使用 Canvas 增加滚动条
    button_canvas.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)

    button_yscrollbar = tk.Scrollbar(main_frame, orient=tk.VERTICAL, command=button_canvas.yview)
    button_yscrollbar.pack(side=tk.LEFT, fill=tk.Y)
    button_canvas.configure(yscrollcommand=button_yscrollbar.set)

    button_frame_inner = tk.Frame(button_canvas)
    button_canvas.create_window((0, 0), window=button_frame_inner, anchor=tk.NW)

    selected_content_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=20)
    selected_content_text.pack(side=tk.LEFT, expand=True, fill=tk.BOTH) # 内容文本区域靠左


    def show_prompt_content(prompt_content): # 修改为接收 prompt_content
        formatted_content = prompt_content.replace('\\n', '\n')
        selected_content_text.config(state=tk.NORMAL)
        selected_content_text.delete(1.0, tk.END)
        selected_content_text.insert(tk.INSERT, f"### Prompt 内容:\n\n", ('bold',)) # 修改标题
        selected_content_text.insert(tk.INSERT, formatted_content)
        selected_content_text.config(state=tk.DISABLED)

    def canvas_yview_scroll_mousewheel_buttons(event): # 按钮区域滚轮滚动
        if event.delta > 0:
            button_canvas.yview_scroll(-1, "units")
        else:
            button_canvas.yview_scroll(1, "units")
        return "break"

    button_canvas.bind("<MouseWheel>", canvas_yview_scroll_mousewheel_buttons)
    button_canvas.bind("<Button-4>", canvas_yview_scroll_mousewheel_buttons)
    button_canvas.bind("<Button-5>", canvas_yview_scroll_mousewheel_buttons)


    prompt_buttons = {} # 存储 prompt 按钮，identifier -> button  映射

    prompt_order_list = config.get('prompt_order', [])
    for char_prompt_order in prompt_order_list:
        order_list = char_prompt_order.get('order', [])

        for prompt_item in order_list:
            identifier = prompt_item.get('identifier')
            prompt_name = get_prompt_name_by_identifier(identifier) # 使用全局 config, 移除 config 参数

            if not is_uuid_like(identifier): # 只处理 UUID 类型的 prompt 按钮
                continue

            prompt_content = get_prompt_content_by_identifier(identifier) # 使用全局 config, 移除 config 参数 # 获取 prompt 内容

            prompt_button = tk.Button(button_frame_inner, text=f"- {prompt_name}", width=25, anchor=tk.W,
                                      command=lambda content=prompt_content: show_prompt_content(content)) # 使用 lambda 传递 prompt 内容
            prompt_button.pack(anchor=tk.W)
            prompt_buttons[identifier] = prompt_button # 存储按钮


    button_frame_inner.update_idletasks()
    button_canvas.configure(scrollregion=button_canvas.bbox("all"))



def manage_prompt_enabling_gui(root, update_status_callback): # 移除 config, filename 参数，添加 update_status_callback
    # 在 GUI 中显示 prompt 管理界面，单列滚动列表，可启用/禁用，无需角色ID分组
    global config, filename # 声明使用全局变量

    if not config or not filename: # 检查 config 和 filename 是否加载
        messagebox.showerror("错误", "请先加载配置文件。") # 提示先加载文件
        return


    content_window = tk.Toplevel(root)
    content_window.title(f"{filename} - Prompt 管理")

    main_frame = tk.Frame(content_window) # 主框架
    main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    prompt_canvas = tk.Canvas(main_frame, height=300, highlightthickness=0) # 限制高度
    prompt_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    yscrollbar = tk.Scrollbar(main_frame, orient=tk.VERTICAL, command=prompt_canvas.yview)
    yscrollbar.pack(side=tk.LEFT, fill=tk.Y)
    prompt_canvas.configure(yscrollcommand=yscrollbar.set)

    prompt_frame_inner = tk.Frame(prompt_canvas)
    prompt_canvas.create_window((0, 0), window=prompt_frame_inner, anchor=tk.NW)

    prompt_checkbox_vars = {} # 存储 Checkbutton 的变量，key 为 identifier

    def update_prompt_enabled_status(identifier, var):
        # 复选框状态改变时调用，更新 config_data
        global config # 声明使用全局 config
        enabled_status = var.get()
        print(f"状态更新: Prompt '{identifier}' 启用状态更改为: {enabled_status}") # 调试输出

        found = False # Flag to track if identifier is found

        for char_order in config['prompt_order']: # 遍历 prompt_order_list
            for item in char_order['order']: # 在 order 列表中查找 identifier
                if item['identifier'] == identifier:
                    item['enabled'] = enabled_status # 更新 enabled 状态
                    print(f"  - config_data 更新: prompt_order - character_id: {char_order.get('character_id')}, identifier: {identifier}, enabled: {enabled_status}") # 调试输出
                    found = True # Set flag to True when found
                    break # 找到 identifier 后跳出内循环
            if found: # If found in inner loop, break outer loop as well
                break

        if not found: # Check flag after outer loop completes
            print(f"  - 警告: Identifier '{identifier}' 未在 config_data 中找到!") # 调试输出


    def canvas_yview_scroll_mousewheel_checkboxes(event): # Checkbox 区域滚轮滚动
        if event.delta > 0:
            prompt_canvas.yview_scroll(-1, "units")
        else:
            prompt_canvas.yview_scroll(1, "units")
        return "break"

    prompt_canvas.bind("<MouseWheel>", canvas_yview_scroll_mousewheel_checkboxes) # 绑定滚轮事件
    prompt_canvas.bind("<Button-4>", canvas_yview_scroll_mousewheel_checkboxes)
    prompt_canvas.bind("<Button-5>", canvas_yview_scroll_mousewheel_checkboxes)


    prompt_order_list = config.get('prompt_order', [])
    for char_prompt_order in prompt_order_list:
        order_list = char_prompt_order.get('order', [])

        for prompt_item in order_list:
            identifier = prompt_item.get('identifier')
            enabled = prompt_item.get('enabled')
            prompt_name = get_prompt_name_by_identifier(identifier) # 使用全局 config, 移除 config 参数

            # 排除默认 identifier
            if identifier in ["main", "worldInfoBefore", "charDescription", "charPersonality", "scenario", "enhanceDefinitions", "nsfw", "worldInfoAfter", "dialogueExamples", "chatHistory", "jailbreak"]:
                continue # 跳过默认 prompt

            prompt_frame = tk.Frame(prompt_frame_inner, cursor="hand2") # 每个 Prompt 用一个 Frame 包裹, 设置手型鼠标
            prompt_frame.pack(anchor=tk.W, pady=5) # 增加 pady

            checkbox_var = tk.BooleanVar(value=enabled) # 创建 BooleanVar，初始值设为当前的 enabled 状态
            prompt_checkbox_vars[identifier] = checkbox_var # 存储变量

            checkbox = tk.Checkbutton(prompt_frame, text="", variable=checkbox_var, command=lambda identifier=identifier, var=checkbox_var: update_prompt_enabled_status_from_checkbox(identifier, var)) # Checkbox command
            checkbox.pack(side=tk.LEFT)

            name_label = tk.Label(prompt_frame, text=f"{prompt_name}", width=30, anchor=tk.W, cursor="hand2") # Match cursor with prompt_frame
            name_label.pack(side=tk.LEFT)

            # Bind click event to Frame AND Label
            prompt_frame.bind("<Button-1>", lambda event, identifier=identifier, var=checkbox_var: update_prompt_enabled_status_from_frame_click(identifier, var))
            name_label.bind("<Button-1>", lambda event, identifier=identifier, var=checkbox_var: update_prompt_enabled_status_from_frame_click(identifier, var))


    def update_prompt_enabled_status_from_checkbox(identifier, checkbox_var):
        # 从 Checkbox 触发的状态更新
        update_prompt_enabled_status(identifier, checkbox_var) #  直接调用状态更新函数
        print(f"Checkbox 点击: Prompt '{identifier}' 触发状态更新") # 调试输出


    def update_prompt_enabled_status_from_frame_click(identifier, checkbox_var):
        # 从 Frame 点击触发的状态更新
        checkbox_var.set(not checkbox_var.get()) # 切换 Checkbox 状态
        update_prompt_enabled_status(identifier, checkbox_var) # 调用状态更新函数
        print(f"Frame 点击: Prompt '{identifier}' 触发状态更新，切换到: {checkbox_var.get()}") # 调试输出


    prompt_frame_inner.update_idletasks()
    prompt_canvas.configure(scrollregion=prompt_canvas.bbox("all"))


    def save_config_command():
        # "保存配置" 按钮的 command 函数
        global config, filename # 声明使用全局变量
        if save_config_to_file(config, filename): # 保存成功后更新主窗口状态
            update_status_callback() # 使用回调函数更新状态，移除参数，这里调用回调函数更新主窗口状态
            messagebox.showinfo("提示", "配置已保存。")


    save_button = tk.Button(main_frame, text="保存配置", command=save_config_command) # "保存配置" 按钮
    save_button.pack(pady=10)



def show_instructions_gui(root, main_font, button_font): # 接收 button_font
    # 显示说明文档的 GUI 窗口, 字体大小调整
    instruction_window = tk.Toplevel(root)
    instruction_window.title("使用说明")

    instruction_text = scrolledtext.ScrolledText(instruction_window, wrap=tk.WORD, height=25, width=80, font=main_font, spacing3=5) # 应用 main_font 和 spacing3
    instruction_text.pack(padx=20, pady=20, expand=True, fill=tk.BOTH)
    instruction_text.config(state=tk.DISABLED)

    instructions = """
预设文件查看器 - 使用说明

本工具用于查看和管理 sillytavern 预设文件 (Default.json) 中的 Prompt 配置。

主要功能:

1. 查看 Prompt 内容:  展示 *自定义* Prompt 的内容，方便用户查阅。
2. 管理 Prompt 启用/禁用:  允许用户启用或禁用 *自定义* Prompt，并保存配置。
3. 查看 Prompt Order 状态:  在主界面显示当前配置文件的 Prompt Order 状态概览，包括自定义 Prompt 的启用/禁用情况。
4. 查看使用说明:  显示本详细说明文档。

界面说明:

- 主界面:
    - 文件名显示:  顶部显示当前加载的预设文件名。
    - Prompt Order 状态 区域:  显示自定义 Prompt 的启用/禁用状态。被禁用的 Prompt 会以删除线标记。
    - 查看 Prompt 内容 按钮:  点击打开 "Prompt 内容查看" 窗口。
    - 管理 Prompt 启用/禁用 按钮: 点击打开 "Prompt 管理" 窗口。
    - 说明 按钮:  点击打开本使用说明窗口。

- Prompt 内容查看 窗口:
    - Prompt 列表:  以可滚动列表形式显示 *自定义* Prompt 的名称按钮 (UUID 标识符的 Prompt)。
    - 内容显示区域:  点击 Prompt 名称按钮后，右侧区域显示该 Prompt 的详细内容。
    - 排除的 Prompt:  为了避免界面过于复杂，以及默认核心 Prompt 通常不需要用户修改，所以以下 Prompt 类型不在此窗口显示:
        - 默认核心 Prompt (identifier 例如: `main`, `jailbreak`, `worldInfoBefore` 等)
        - 非 UUID 标识符的 Prompt

- Prompt 管理 窗口:
    - Prompt 列表:  以可滚动列表形式显示 *自定义* Prompt 的名称和复选框 (UUID 标识符的Prompt)。
    - 启用/禁用操作:  勾选复选框表示启用该 Prompt，取消勾选表示禁用。 *点击 Prompt 所在行也可以切换启用/禁用状态。*
    - 保存配置 按钮:  点击后保存当前的启用/禁用配置到 JSON 文件。
    - 排除的 Prompt:  与 "Prompt 内容查看 窗口" 相同，默认核心 Prompt 和非 UUID 标识符的 Prompt 不在此窗口显示和管理。

排除的 Prompt 类型 (详细列表):

- 默认核心 Prompt (Identifier 列表):
    - main
    - jailbreak
    - worldInfoBefore
    - charDescription
    - charPersonality
    - scenario
    - enhanceDefinitions
    - nsfw
    - worldInfoAfter
    - dialogueExamples
    - chatHistory

    这些 Prompt 是 sillytavern 预设的核心组成部分，通常不需要用户自定义修改或调整启用/禁用状态。

- 非 UUID 标识符的 Prompt:
    工具主要针对 *自定义* 的 Prompt 进行管理，这些 Prompt 通常具有 UUID 格式的 `identifier`。  非 UUID 标识符的Prompt 可能属于系统或默认配置的一部分，因此被排除。

操作流程建议:

1. 选择预设文件:  启动工具后，首先选择要处理的 JSON 预设文件。
2. 查看 Prompt Order 状态:  在主界面查看当前配置的Prompt 启用/禁用状态概览。
3. 查看 Prompt 内容 (可选):  如果需要查看某个 *自定义*Prompt 的具体内容，点击 "查看 Prompt 内容" 按钮，在弹出的窗口中选择 Prompt 查看。
4. 管理 Prompt 启用/禁用 (可选):  如果需要调整 *自定义*Prompt 的启用/禁用状态，点击 "管理 Prompt 启用/禁用" 按钮，在弹出的窗口中进行勾选/取消勾选操作，完成后点击 "保存配置" 按钮。
5. 查看使用说明 (可选):  如果对工具的使用有疑问，可以点击 "说明" 按钮查看本详细使用说明。

希望以上说明能够帮助您更好地使用本工具。  如有任何疑问或建议，请随时反馈。
    """

    instruction_text.config(state=tk.NORMAL)
    instruction_text.insert(tk.END, instructions)
    instruction_text.config(state=tk.DISABLED)
    instruction_text.mark_set(" DocStart", "1.0") # 确保文档从顶部开始显示


def is_uuid_like(identifier):
    # 简化的 UUID 格式判断
    if not identifier:
        return False
    identifier = identifier.replace('-', '')
    return len(identifier) == 32 and all(c in '0123456789abcdef' for c in identifier.lower())


def main_gui(filepath): #  修改为接收 filepath 而不是 filename,  load_config 在这里调用
    # 主 GUI 窗口
    root = tk.Tk()
    root.title("预设文件查看器")

    if not load_config(filepath): # 加载配置文件，如果失败则退出
        return


    #  主窗口字体
    main_font = font.Font(size=11) #  加大字体
    bold_main_font = font.Font(weight='bold', size=11) # 加粗字体
    button_font_large = font.Font(size=10) # 按钮稍大字体


    status_text_widget = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=15, font=main_font, spacing3=5) # 使用 Text 组件显示状态, 应用字体, spacing3 增加行间距

    # 配置 tags
    status_text_widget.tag_config('bold', font=bold_main_font) # 粗体 tag，应用加粗字体
    status_text_widget.tag_config('disabled', overstrike=True) # 删除线 tag
    status_text_widget.tag_config('warning', foreground='orange') # 警告 tag，例如橙色


    def update_main_window_status(): #  更新主窗口状态函数, 移除参数
        status_segments = format_prompt_order_status_text() # 移除参数，使用全局变量
        status_text_widget.config(state=tk.NORMAL)
        status_text_widget.delete(1.0, tk.END)
        for segment in status_segments:
            text = segment['text']
            tags = segment['tags']
            status_text_widget.insert(tk.END, text, tags) #  移除 pady
        status_text_widget.config(state=tk.DISABLED)


    filename_label = tk.Label(root, text=f"当前文件: {filename}", font=bold_main_font) # 文件名加粗, 应用加粗字体
    filename_label.pack(pady=10)
    status_text_widget.pack(padx=20, pady=10, fill=tk.BOTH, expand=True) # Pack 放在 filename_label 之后

    update_main_window_status() # 初始加载状态，移除参数
    status_text_widget.config(state=tk.DISABLED) # 设置为只读


    # 使用 Frame 组织按钮
    button_frame_main = tk.Frame(root)
    button_frame_main.pack(pady=10)

    content_button = tk.Button(button_frame_main, text="查看 Prompt 内容", font=button_font_large, # 查看内容按钮, 应用字体
                                command=lambda: view_prompt_contents_gui(root)) # 移除参数
    content_button.pack(side=tk.LEFT, padx=10)

    manage_button = tk.Button(button_frame_main, text="管理 Prompt 启用/禁用", font=button_font_large, # 管理启用禁用按钮, 应用字体
                                 command=lambda: manage_prompt_enabling_gui(root, update_main_window_status)) # 传递 update_main_window_status
    manage_button.pack(side=tk.LEFT, padx=10)

    instruction_button = tk.Button(button_frame_main, text="说明", font=button_font_large, # 说明按钮, 应用字体
                                command=lambda: show_instructions_gui(root, main_font, button_font_large)) # 传递 main_font, button_font_large
    instruction_button.pack(side=tk.LEFT, padx=10)


    root.mainloop()


def save_config_to_file(config_data, filepath):
    # 保存 config_data 到 JSON 文件
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        print(f"配置文件已保存到: {filepath}")
        return True
    except Exception as e:
        messagebox.showerror("错误", f"保存配置文件失败: {e}")
        print(f"保存配置文件出错: {e}")
        return False


def main():
    # 文件选择主逻辑
    json_files = [f for f in os.listdir() if f.endswith('.json')]

    if not json_files:
        messagebox.showinfo("提示", "当前目录下没有 JSON 文件。")
        return

    file_selector_root = tk.Tk()
    file_selector_root.title("选择 JSON 配置文件")

    # 文件选择窗口字体
    selector_font = font.Font(size=10)

    file_list_frame = tk.Frame(file_selector_root)
    file_list_frame.pack(pady=20, padx=20)

    def open_selected_file(filepath): #  修改为传递 filepath
        file_selector_root.destroy()
        main_gui(filepath) #  传递 filepath

    file_label = tk.Label(file_list_frame, text="请选择要处理的 JSON 文件:", font=selector_font) # 应用字体
    file_label.pack()

    for index, filename in enumerate(json_files):
        file_button = tk.Button(file_list_frame, text=f"{index + 1}. {filename}", width=30, font=selector_font, # 应用字体
                                 command=lambda fn=filename: open_selected_file(fn)) #  lambda 传递 filename,  open_selected_file 接收 filepath
        file_button.pack(anchor=tk.W)

    file_selector_root.mainloop()


if __name__ == "__main__":
    main()