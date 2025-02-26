import json
import os
import tkinter as tk
from tkinter import font, scrolledtext, messagebox, filedialog
from tkinter import ttk


class ConfigManager:
    """
    管理配置文件的加载和保存。
    """

    def __init__(self):
        self.config = None
        self.filename = None
        self.filepath = None

    def load_config(self, filepath):
        """加载 JSON 配置文件"""
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            return self.config
        except FileNotFoundError:
            messagebox.showerror("错误", f"配置文件 {filepath} 未找到。")
            return None
        except json.JSONDecodeError:
            messagebox.showerror("错误", f"配置文件 {filepath} JSON 格式解析失败。")
            return None

    def save_config(self):
        """保存 config_data 到 JSON 文件"""
        if self.config is None or self.filepath is None:
            messagebox.showerror("错误", "没有加载配置文件或文件路径为空。")
            return False
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            print(f"配置文件已保存到: {self.filepath}")
            return True
        except Exception as e:
            messagebox.showerror("错误", f"保存配置文件失败: {e}")
            print(f"保存配置文件出错: {e}")
            return False

    def get_prompt_name_by_identifier(self, identifier):
        """根据 identifier 获取 prompts 列表中对应的 name"""
        if not self.config or 'prompts' not in self.config:
            return '配置未加载'
        for prompt in self.config.get('prompts', []):
            if prompt.get('identifier') == identifier:
                return prompt.get('name', '未知名称')
        return '未找到名称'

    def get_prompt_content_by_identifier(self, identifier):
        """根据 identifier 获取 prompts 列表中对应的 content"""
        if not self.config or 'prompts' not in self.config:
            return '配置未加载'
        for prompt in self.config.get('prompts', []):
            if prompt.get('identifier') == identifier:
                return prompt.get('content', '无内容')
        return '未找到内容'

    def update_prompt_enabled_status(self, identifier, enabled_status):
        """
        更新指定 identifier 的 prompt 的 enabled 状态。
        """
        if not self.config or 'prompt_order' not in self.config:
            print("配置未加载或 'prompt_order' 键不存在。")
            return

        found = False
        for char_order in self.config['prompt_order']:
            for item in char_order['order']:
                if item['identifier'] == identifier:
                    prompt_name = self.get_prompt_name_by_identifier(
                        identifier)  # 获取 Prompt 名称
                    item['enabled'] = enabled_status
                    print(
                        f"  - config_data 更新: prompt_order - character_id: {char_order.get('character_id')}, prompt_name: {prompt_name}, enabled: {enabled_status}")
                    found = True
                    break
            if found:
                break

        if not found:
            prompt_name = self.get_prompt_name_by_identifier(
                identifier)  # 获取 Prompt 名称
            print(
                f"  - 警告: Prompt '{prompt_name}' (identifier: {identifier}) 未在 config_data 中找到!")


class PromptManager:
    """
    管理 Prompt 相关的操作。
    """

    def __init__(self, config_manager):
        self.config_manager = config_manager

    def format_prompt_order_status_text(self):
        """格式化 prompt_order 状态文本，用于 GUI Text 组件显示，返回文本内容和 tags 列表"""
        config = self.config_manager.config
        filename = self.config_manager.filename

        if not config or not filename:
            return [{'text': "未加载配置文件。\n", 'tags': ('warning',)}]

        output_text_segments = []
        output_text_segments.append(
            {'text': f"📜  {filename} - Prompt Order 状态:\n\n", 'tags': ('bold',)})
        prompt_order_list = config.get('prompt_order', [])

        if not prompt_order_list:
            output_text_segments.append({'text': "prompt_order 为空。\n", 'tags': ()})
            return output_text_segments

        for char_prompt_order in prompt_order_list:
            char_id = char_prompt_order.get('character_id')
            order_list = char_prompt_order.get('order', [])
            if not order_list:
                continue

            has_non_default_prompts = False
            prompt_items_segments = []
            last_enabled_status = None

            for prompt_item in order_list:
                identifier = prompt_item.get('identifier')
                enabled = prompt_item.get('enabled')
                prompt_name = self.config_manager.get_prompt_name_by_identifier(
                    identifier)

                if identifier in ["main", "worldInfoBefore", "charDescription", "charPersonality", "scenario",
                                  "enhanceDefinitions", "nsfw", "worldInfoAfter", "dialogueExamples", "chatHistory",
                                  "jailbreak"]:
                    continue

                has_non_default_prompts = True

                if last_enabled_status is not None and enabled != last_enabled_status:
                    prompt_items_segments.append({'text': "\n", 'tags': ()})

                if enabled:
                    prompt_items_segments.append(
                        {'text': f"- {prompt_name} (启用)\n", 'tags': ()})
                else:
                    prompt_items_segments.append(
                        {'text': f"- {prompt_name} (禁用)\n", 'tags': ('disabled',)})

                last_enabled_status = enabled

            if has_non_default_prompts:
                prompt_items_segments.insert(
                    0, {'text': f"\n角色 ID: {char_id}:\n", 'tags': ('bold',)})
                output_text_segments.extend(prompt_items_segments)

        return output_text_segments

    def is_uuid_like(self, identifier):
        """简化的 UUID 格式判断"""
        if not identifier:
            return False
        identifier = identifier.replace('-', '')
        return len(identifier) == 32 and all(c in '0123456789abcdef' for c in identifier.lower())


class UIBuilder:
    """
    构建用户界面。
    """

    def __init__(self, config_manager, prompt_manager):
        self.config_manager = config_manager
        self.prompt_manager = prompt_manager
        self.root = tk.Tk()
        self.root.title("预设文件查看器")

        # 字体
        self.main_font = font.Font(size=11)
        self.bold_main_font = font.Font(weight='bold', size=11)
        self.button_font_large = font.Font(size=10)

        # 初始化界面
        self.setup_main_window()

    def setup_main_window(self):
        """设置主窗口"""
        self.status_text_widget = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=15, font=self.main_font,
                                                           spacing3=5)
        self.status_text_widget.tag_config('bold', font=self.bold_main_font)
        self.status_text_widget.tag_config('disabled', overstrike=True)
        self.status_text_widget.tag_config('warning', foreground='orange')

        self.filename_label = tk.Label(self.root, text=f"当前文件: {self.config_manager.filename}",
                                       font=self.bold_main_font)
        self.filename_label.pack(pady=10)
        self.status_text_widget.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

        self.update_main_window_status()
        self.status_text_widget.config(state=tk.DISABLED)

        button_frame_main = tk.Frame(self.root)
        button_frame_main.pack(pady=10)

        content_button = tk.Button(button_frame_main, text="查看 Prompt 内容", font=self.button_font_large,
                                   command=self.show_prompt_contents_gui)
        content_button.pack(side=tk.LEFT, padx=10)

        manage_button = tk.Button(button_frame_main, text="管理 Prompt 启用/禁用", font=self.button_font_large,
                                  command=lambda: self.show_manage_prompt_enabling_gui(
                                      self.update_main_window_status))
        manage_button.pack(side=tk.LEFT, padx=10)

        instruction_button = tk.Button(button_frame_main, text="说明", font=self.button_font_large,
                                       command=self.show_instructions_gui)
        instruction_button.pack(side=tk.LEFT, padx=10)

        # 添加手动切换文件按钮
        change_file_button = tk.Button(
            button_frame_main, text="切换文件", font=self.button_font_large, command=self.change_file)
        change_file_button.pack(side=tk.LEFT, padx=10)

    def change_file(self):
        """手动切换文件"""
        filepath = filedialog.askopenfilename(
            title="选择 JSON 配置文件",
            filetypes=[("JSON files", "*.json")],
            initialdir=find_sillytavern_openai_settings_path()  # 设置初始目录
        )
        if filepath:
            self.config_manager.load_config(filepath)
            self.filename_label.config(
                text=f"当前文件: {self.config_manager.filename}")  # 更新文件名标签
            self.update_main_window_status()  # 更新状态显示

    def update_main_window_status(self):
        """更新主窗口状态"""
        status_segments = self.prompt_manager.format_prompt_order_status_text()
        self.status_text_widget.config(state=tk.NORMAL)
        self.status_text_widget.delete(1.0, tk.END)
        for segment in status_segments:
            text = segment['text']
            tags = segment['tags']
            self.status_text_widget.insert(tk.END, text, tags)
        self.status_text_widget.config(state=tk.DISABLED)

    def show_prompt_contents_gui(self):
        """显示 Prompt 内容查看界面"""

        if not self.config_manager.config or not self.config_manager.filename:
            messagebox.showerror("错误", "请先加载配置文件。")
            return

        content_window = tk.Toplevel(self.root)
        content_window.title(f"{self.config_manager.filename} - Prompt 内容查看")

        main_frame = tk.Frame(content_window)
        main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        button_canvas = tk.Canvas(main_frame, highlightthickness=0)
        button_canvas.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)

        button_yscrollbar = tk.Scrollbar(
            main_frame, orient=tk.VERTICAL, command=button_canvas.yview)
        button_yscrollbar.pack(side=tk.LEFT, fill=tk.Y)
        button_canvas.configure(yscrollcommand=button_yscrollbar.set)

        button_frame_inner = tk.Frame(button_canvas)
        button_canvas.create_window(
            (0, 0), window=button_frame_inner, anchor=tk.NW)

        selected_content_text = scrolledtext.ScrolledText(
            main_frame, wrap=tk.WORD, height=20)
        selected_content_text.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        def show_prompt_content(prompt_content):
            formatted_content = prompt_content.replace('\\n', '\n')
            selected_content_text.config(state=tk.NORMAL)
            selected_content_text.delete(1.0, tk.END)
            selected_content_text.insert(
                tk.INSERT, f"### Prompt 内容:\n\n", ('bold',))
            selected_content_text.insert(tk.INSERT, formatted_content)
            selected_content_text.config(state=tk.DISABLED)

        def canvas_yview_scroll_mousewheel_buttons(event):
            if event.delta > 0:
                button_canvas.yview_scroll(-1, "units")
            else:
                button_canvas.yview_scroll(1, "units")
            return "break"

        button_canvas.bind("<MouseWheel>", canvas_yview_scroll_mousewheel_buttons)
        button_canvas.bind("<Button-4>", canvas_yview_scroll_mousewheel_buttons)
        button_canvas.bind("<Button-5>", canvas_yview_scroll_mousewheel_buttons)

        prompt_buttons = {}

        prompt_order_list = self.config_manager.config.get('prompt_order', [])
        for char_prompt_order in prompt_order_list:
            order_list = char_prompt_order.get('order', [])
            for prompt_item in order_list:
                identifier = prompt_item.get('identifier')
                prompt_name = self.config_manager.get_prompt_name_by_identifier(
                    identifier)
                if not self.prompt_manager.is_uuid_like(identifier):
                    continue
                prompt_content = self.config_manager.get_prompt_content_by_identifier(
                    identifier)
                prompt_button = tk.Button(button_frame_inner, text=f"- {prompt_name}", width=25, anchor=tk.W,
                                          command=lambda content=prompt_content: show_prompt_content(content))
                prompt_button.pack(anchor=tk.W)
                prompt_buttons[identifier] = prompt_button

        button_frame_inner.update_idletasks()
        button_canvas.configure(scrollregion=button_canvas.bbox("all"))

    def show_manage_prompt_enabling_gui(self, update_status_callback):
        """显示 Prompt 管理界面"""
        if not self.config_manager.config or not self.config_manager.filename:
            messagebox.showerror("错误", "请先加载配置文件。")
            return

        content_window = tk.Toplevel(self.root)
        content_window.title(f"{self.config_manager.filename} - Prompt 管理")

        main_frame = tk.Frame(content_window)
        main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        prompt_canvas = tk.Canvas(main_frame, height=300, highlightthickness=0)
        prompt_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        yscrollbar = tk.Scrollbar(
            main_frame, orient=tk.VERTICAL, command=prompt_canvas.yview)
        yscrollbar.pack(side=tk.LEFT, fill=tk.Y)
        prompt_canvas.configure(yscrollcommand=yscrollbar.set)

        prompt_frame_inner = tk.Frame(prompt_canvas)
        prompt_canvas.create_window(
            (0, 0), window=prompt_frame_inner, anchor=tk.NW)
        prompt_checkbox_vars = {}

        def canvas_yview_scroll_mousewheel_checkboxes(event):
            if event.delta > 0:
                prompt_canvas.yview_scroll(-1, "units")
            else:
                prompt_canvas.yview_scroll(1, "units")
            return "break"

        prompt_canvas.bind("<MouseWheel>",
                           canvas_yview_scroll_mousewheel_checkboxes)
        prompt_canvas.bind("<Button-4>",
                           canvas_yview_scroll_mousewheel_checkboxes)
        prompt_canvas.bind("<Button-5>",
                           canvas_yview_scroll_mousewheel_checkboxes)

        prompt_order_list = self.config_manager.config.get('prompt_order', [])
        for char_prompt_order in prompt_order_list:
            order_list = char_prompt_order.get('order', [])

            for prompt_item in order_list:
                identifier = prompt_item.get('identifier')
                enabled = prompt_item.get('enabled')
                prompt_name = self.config_manager.get_prompt_name_by_identifier(
                    identifier)

                if identifier in ["main", "worldInfoBefore", "charDescription", "charPersonality", "scenario",
                                  "enhanceDefinitions", "nsfw", "worldInfoAfter", "dialogueExamples", "chatHistory",
                                  "jailbreak"]:
                    continue

                prompt_frame = tk.Frame(prompt_frame_inner, cursor="hand2")
                prompt_frame.pack(anchor=tk.W, pady=5)

                checkbox_var = tk.BooleanVar(value=enabled)
                prompt_checkbox_vars[identifier] = checkbox_var

                checkbox = tk.Checkbutton(prompt_frame, text="", variable=checkbox_var,
                                          command=lambda identifier=identifier, var=checkbox_var: self.update_prompt_enabled_status_from_checkbox(
                                              identifier, var))
                checkbox.pack(side=tk.LEFT)

                name_label = tk.Label(prompt_frame, text=f"{prompt_name}", width=30, anchor=tk.W,
                                      cursor="hand2")
                name_label.pack(side=tk.LEFT)

                prompt_frame.bind("<Button-1>",
                                  lambda event, identifier=identifier, var=checkbox_var: self.update_prompt_enabled_status_from_frame_click(
                                      identifier, var))
                name_label.bind("<Button-1>",
                                 lambda event, identifier=identifier, var=checkbox_var: self.update_prompt_enabled_status_from_frame_click(
                                     identifier, var))

        def update_prompt_enabled_status_from_checkbox(self, identifier, checkbox_var):
            prompt_name = self.config_manager.get_prompt_name_by_identifier(
                identifier)  # 获取 Prompt 名称
            self.config_manager.update_prompt_enabled_status(
                identifier, checkbox_var.get())
            print(f"Checkbox 点击: Prompt '{prompt_name}' 触发状态更新")
            self.update_main_window_status()  # 更新主窗口状态

        def update_prompt_enabled_status_from_frame_click(self, identifier, checkbox_var):
            prompt_name = self.config_manager.get_prompt_name_by_identifier(
                identifier)  # 获取 Prompt 名称
            checkbox_var.set(not checkbox_var.get())
            self.config_manager.update_prompt_enabled_status(
                identifier, checkbox_var.get())
            print(
                f"Frame 点击: Prompt '{prompt_name}' 触发状态更新，切换到: {checkbox_var.get()}")
            self.update_main_window_status()  # 更新主窗口状态

        prompt_frame_inner.update_idletasks()
        prompt_canvas.configure(scrollregion=prompt_canvas.bbox("all"))

        save_button = tk.Button(main_frame, text="保存配置",
                                command=lambda: self.save_config_command(update_status_callback))
        save_button.pack(pady=10)

    def save_config_command(self, update_status_callback):
        """保存配置并更新状态"""
        if self.config_manager.save_config():
            update_status_callback()  # 使用回调函数更新状态
            messagebox.showinfo("提示", "配置已保存。")

    def show_instructions_gui(self):
        """显示使用说明,并根据代码更新"""
        instruction_window = tk.Toplevel(self.root)
        instruction_window.title("使用说明")

        instruction_text = scrolledtext.ScrolledText(instruction_window, wrap=tk.WORD, height=25, width=80,
                                                     font=self.main_font, spacing3=5)
        instruction_text.pack(padx=20, pady=20, expand=True, fill=tk.BOTH)
        instruction_text.config(state=tk.DISABLED)

        instructions = """
    预设文件查看器 - 使用说明

    本工具用于查看和管理 SillyTavern 预设文件 (位于 OpenAI Settings 目录下的 .json 文件) 中的 Prompt 配置。

    主要功能:

    1.  查看 Prompt 内容:  展示 *自定义* Prompt 的内容，方便用户查阅。
    2.  管理 Prompt 启用/禁用:  允许用户启用或禁用 *自定义* Prompt，并保存配置。
    3.  查看 Prompt Order 状态:  在主界面显示当前配置文件的 Prompt Order 状态概览，包括自定义 Prompt 的启用/禁用情况。
    4.  切换文件:  允许用户手动选择并加载其他的 JSON 配置文件。
    5.  查看使用说明:  显示本详细说明文档。

    界面说明:

    -   主界面:
        -   文件名显示:  顶部显示当前加载的预设文件名。
        -   Prompt Order 状态 区域:  显示自定义 Prompt 的启用/禁用状态。被禁用的 Prompt 会以删除线标记。
        -   查看 Prompt 内容 按钮:  点击打开 "Prompt 内容查看" 窗口。
        -   管理 Prompt 启用/禁用 按钮: 点击打开 "Prompt 管理" 窗口。
        -   说明 按钮:  点击打开本使用说明窗口。
        -   切换文件 按钮:  手动选择其他的 JSON 配置文件。

    -   Prompt 内容查看 窗口:
        -   Prompt 列表:  以可滚动列表形式显示 *自定义* Prompt 的名称按钮 (UUID 标识符的 Prompt)。
        -   内容显示区域:  点击 Prompt 名称按钮后，右侧区域显示该 Prompt 的详细内容。
        -   排除的 Prompt:  为了避免界面过于复杂，以及默认核心 Prompt 通常不需要用户修改，所以以下 Prompt 类型不在此窗口显示:
            -   默认核心 Prompt (identifier 例如: `main`, `jailbreak`, `worldInfoBefore` 等)
            -   非 UUID 标识符的 Prompt

    -   Prompt 管理 窗口:
        -   Prompt 列表:  以可滚动列表形式显示 *自定义* Prompt 的名称和复选框 (UUID 标识符的Prompt)。
        -   启用/禁用操作:  勾选复选框表示启用该 Prompt，取消勾选表示禁用。 *点击 Prompt 所在行也可以切换启用/禁用状态。*
        -   保存配置 按钮:  点击后保存当前的启用/禁用配置到 JSON 文件。
        -   排除的 Prompt: 与 "Prompt 内容查看 窗口" 相同，默认核心 Prompt 和非 UUID 标识符的 Prompt 不在此窗口显示和管理。

    排除的 Prompt 类型 (详细列表):

    -   默认核心 Prompt (Identifier 列表):
        -   main
        -   jailbreak
        -   worldInfoBefore
        -   charDescription
        -   charPersonality
        -   scenario
        -   enhanceDefinitions
        -   nsfw
        -   worldInfoAfter
        -   dialogueExamples
        -   chatHistory

        这些 Prompt 是 SillyTavern 预设的核心组成部分，通常不需要用户自定义修改或调整启用/禁用状态。

    -   非 UUID 标识符的 Prompt:
        工具主要针对 *自定义* 的 Prompt 进行管理，这些 Prompt 通常具有 UUID 格式的 `identifier`。非 UUID 标识符的 Prompt 可能属于系统或默认配置的一部分，因此被排除。

    操作流程:

    1.  启动: 运行程序后，它会自动查找 SillyTavern 的 "OpenAI Settings" 目录。
        -   如果找到该目录，会自动加载该目录下 *最后修改* 的 JSON 配置文件。
        -   如果未找到目录，会提示用户手动选择 "OpenAI Settings" 目录。
    2.  查看: 在主界面查看当前配置的 Prompt Order 状态概览，以及当前加载的文件名。
    3.  (可选) 查看 Prompt 内容: 点击 "查看 Prompt 内容" 按钮，选择 Prompt 查看具体内容。
    4.  (可选) 管理 Prompt: 点击 "管理 Prompt 启用/禁用" 按钮，勾选/取消勾选自定义 Prompt，点击 "保存配置" 保存。
    5.  (可选) 切换文件: 点击 "切换文件" 按钮，手动选择并加载另一个 JSON 配置文件。
    6.  (可选) 查看说明: 点击 "说明" 按钮查看本使用说明。

    希望以上说明能够帮助您更好地使用本工具。如有任何疑问或建议，请随时反馈。
        """

        instruction_text.config(state=tk.NORMAL)
        instruction_text.insert(tk.END, instructions)
        instruction_text.config(state=tk.DISABLED)
        instruction_text.mark_set(" DocStart", "1.0")  # 确保文档从顶部开始显示

    def update_prompt_enabled_status_from_checkbox(self, identifier, checkbox_var):
        prompt_name = self.config_manager.get_prompt_name_by_identifier(
            identifier)  # 获取 Prompt 名称
        self.config_manager.update_prompt_enabled_status(
            identifier, checkbox_var.get())
        print(f"Checkbox 点击: Prompt '{prompt_name}' 触发状态更新")
        self.update_main_window_status()  # 更新主窗口

    def update_prompt_enabled_status_from_frame_click(self, identifier, checkbox_var):
        prompt_name = self.config_manager.get_prompt_name_by_identifier(
            identifier)  # 获取 Prompt 名称
        checkbox_var.set(not checkbox_var.get())
        self.config_manager.update_prompt_enabled_status(
            identifier, checkbox_var.get())
        print(
            f"Frame 点击: Prompt '{prompt_name}' 触发状态更新，切换到: {checkbox_var.get()}")
        self.update_main_window_status()  # 更新主窗口

    def run(self):
        """启动 GUI"""
        self.root.mainloop()


def find_sillytavern_openai_settings_path(initial_dir=None):
    # 查找 SillyTavern OpenAI Settings 目录路径 (允许手动选择/切换)
    if initial_dir and os.path.exists(initial_dir):
        return initial_dir

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
        settings_path = os.path.join(
            sillytavern_dir_path, "data", "default-user", "OpenAI Settings")
        if os.path.exists(settings_path):
            print(f"找到 OpenAI Settings 目录: {settings_path}")
            return settings_path

    # 未找到或用户希望手动选择
    messagebox.showinfo(
        "提示", "未自动找到 OpenAI Settings 目录，请手动选择 SillyTavern 的 OpenAI Settings 目录。")
    settings_path = filedialog.askdirectory(
        title="请选择 SillyTavern 的 OpenAI Settings 目录")
    return settings_path


def main():
    # 文件选择主逻辑, 并处理可能的 None 返回值
    settings_path = find_sillytavern_openai_settings_path()
    if not settings_path:
        messagebox.showerror("错误", "未找到 OpenAI Settings 目录，程序将退出。")
        return  # 退出程序

    json_files = [f for f in os.listdir(settings_path) if f.endswith('.json')]

    if not json_files:
        messagebox.showinfo("提示", "在 OpenAI Settings 目录下没有找到 JSON 文件。")
        return

    def open_selected_file(filepath):
        config_manager = ConfigManager()
        config_manager.load_config(filepath)
        prompt_manager = PromptManager(config_manager)
        ui_builder = UIBuilder(config_manager, prompt_manager)
        ui_builder.run()

    # 如果有 JSON 文件，加载修改时间最近的文件
    if json_files:
        # 获取每个文件的最后修改时间，并与文件名一起存储在元组中
        files_with_mtime = [
            (os.path.join(settings_path, f), os.path.getmtime(os.path.join(settings_path, f)))
            for f in json_files
        ]

        # 根据最后修改时间对元组进行排序 (最新的排在前面)
        files_with_mtime.sort(key=lambda x: x[1], reverse=True)

        # 获取最新修改的文件的路径
        latest_file_path = files_with_mtime[0][0]
        open_selected_file(latest_file_path)

    else:  # 理论上不会执行到这里，因为前面已经检查过 json_files
        messagebox.showinfo("提示", "没有找到 JSON 文件")

if __name__ == "__main__":
    main()