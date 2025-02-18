import os
import json
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Tuple

# 全局配置
CONFIG = {
    'tag_position': 'prefix',  # 初始位置：前缀
    'brackets': '【】',  # 默认括号类型
    'bracket_pairs': {
        '[]': ('[', ']'),
        '［］': ('［', '］'),
        '「」': ('「', '」'),
        '『』': ('『', '』'),
        '【】': ('【', '】'),
        '〖〗': ('〖', '〗'),

    }
}

def sanitize_filename(filename: str) -> str:
    """文件名净化"""
    return re.sub(r'[\\/*?:"<>|]', '_', filename)

def extract_tag(text: str) -> str:
    """
    从文本中提取标签（根据设置中的括号类型）。
    """
    left_bracket, right_bracket = CONFIG['bracket_pairs'][CONFIG['brackets']]
    if text.startswith(left_bracket) and text.endswith(right_bracket):
        return text[len(left_bracket):-len(right_bracket)]
    return text

def remove_existing_tags(directory: str) -> None:
    """移除标签"""
    files_modified = 0
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith(".json"):
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    if "scriptName" in data:
                        script_name = data["scriptName"]
                        modified_script_name = script_name

                        # 循环移除最外层的标签
                        while True:
                            original_script_name = modified_script_name
                            # 尝试移除各种括号类型的标签
                            for left, right in CONFIG['bracket_pairs'].values():
                                modified_script_name = re.sub(rf'^{re.escape(left)}.*?{re.escape(right)}[-_\s]*', '', modified_script_name)  # 开头
                                modified_script_name = re.sub(rf'[-_\s]*{re.escape(left)}.*?{re.escape(right)}$', '', modified_script_name)  # 结尾
                            modified_script_name = modified_script_name.strip()
                            if modified_script_name == original_script_name:  # 没有变化，退出循环
                                break

                        # 清理多余的连接符
                        modified_script_name = re.sub(r'[-_\s]+', '-', modified_script_name)

                        if modified_script_name != script_name:
                            data["scriptName"] = modified_script_name

                            # 更新文件名
                            new_filename = f"正则-{modified_script_name}.json"
                            new_filepath = os.path.join(root, filename)
                            # 处理文件名冲突
                            i = 1
                            while os.path.exists(new_filepath):
                                base, ext = os.path.splitext(new_filename)
                                new_filename = f"{base}_{i}{ext}"
                                new_filepath = os.path.join(os.path.dirname(filepath), new_filename)
                                i += 1

                            with open(new_filepath, 'w', encoding='utf-8') as f:
                                json.dump(data, f, indent=2, ensure_ascii=False)

                            os.remove(filepath)
                            print(f"  已移除标签并重命名: {filename} -> {new_filename}")
                            files_modified += 1

                except (json.JSONDecodeError, OSError) as e:
                    print(f"  处理文件 '{filename}' 时出错: {e}")

    if files_modified == 0:
        print("没有找到需要移除标签的文件。")

def process_json_file(filepath: str, tag: str = "") -> Tuple[bool, str, str]:
    """处理单个文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not all(key in data for key in ["scriptName", "findRegex", "replaceString"]):
            print(f"  跳过: 文件 '{os.path.basename(filepath)}' 缺少必要键。")
            return False, "", ""

        original_script_name = data.get("scriptName", "")
        script_name = sanitize_filename(original_script_name)
        modified_script_name = script_name  # 初始化
        left_bracket, right_bracket = CONFIG['bracket_pairs'][CONFIG['brackets']]

        if tag:
            # tag 已经在 process_subdirectories_with_tag 中被正确提取

            # 1. 更精确地匹配现有标签及其前后缀
            existing_tag_match = re.match(r'^(.*?)((?:[-_ ]*\.json)|(?:[-_ ]+.*\.json))$', script_name)
            if existing_tag_match:
                prefix = existing_tag_match.group(1)
                suffix = existing_tag_match.group(2)
                tag_search = re.search(r'[' + re.escape(''.join(CONFIG['bracket_pairs'].keys())) + r']', prefix)

                if tag_search: #找到了
                    existing_brackets = prefix[tag_search.start():tag_search.end()]
                    _, existing_right = CONFIG['bracket_pairs'][existing_brackets]
                    old_tag_full = prefix[tag_search.start():]
                    modified_script_name = script_name.replace(old_tag_full, f"{left_bracket}{tag}{right_bracket}") # 替换
                else:
                    answer = messagebox.askyesno( # 没找到
                        "添加标签",
                        f"scriptName '{script_name}' 不符合当前标签格式。\n\n是否要添加标签 '{tag}'？",
                    )
                    if answer:
                        if CONFIG['tag_position'] == 'prefix':
                            modified_script_name = f"{left_bracket}{tag}{right_bracket}-{script_name}"
                        else:
                            modified_script_name = f"{script_name}-{left_bracket}{tag}{right_bracket}"
                    else:
                        print(f"用户取消，跳过文件：{script_name} 的修改")
            else: # 匹配失败
                if CONFIG['tag_position'] == 'prefix':
                    modified_script_name = f"{left_bracket}{tag}{right_bracket}-{script_name}"
                else:
                    modified_script_name = f"{script_name}-{left_bracket}{tag}{right_bracket}"


            # 清理
            modified_script_name = re.sub(r'^[\[「『【](.*?)[\s_-]*[\]」』】]$', r'\1', modified_script_name)
            modified_script_name = re.sub(r'[\s_-]+', '-', modified_script_name)  # 多个空格、_、- 替换为单个-
            data["scriptName"] = modified_script_name  # 更新

        new_filename = f"正则-{modified_script_name}.json"
        new_filepath = os.path.join(os.path.dirname(filepath), new_filename)

        # 处理文件名冲突
        i = 1
        while os.path.exists(new_filepath):
            base, ext = os.path.splitext(new_filename)
            new_filename = f"{base}_{i}{ext}"
            new_filepath = os.path.join(os.path.dirname(filepath), new_filename)
            i += 1

        with open(new_filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        os.remove(filepath)
        return True, os.path.basename(filepath), new_filename

    except (json.JSONDecodeError, OSError) as e:
        print(f"  处理文件 '{os.path.basename(filepath)}' 时出错: {e}")
        return False, "", ""

def process_directory(directory: str, tag: str = "", batch_mode: bool = False) -> None:
    """处理目录"""
    file_count = 0
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith(".json"):
                filepath = os.path.join(root, filename)
                success, old_filename, new_filename = process_json_file(filepath, tag)
                if success:
                    file_count += 1
                    print(f"  已重命名: '{old_filename}' -> '{new_filename}'")
    if not batch_mode:
        print(f"\n共处理了 {file_count} 个 JSON 文件。")

def process_subdirectories_with_tag(directory: str) -> None:
    """处理子目录"""
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        if os.path.isdir(item_path):
            print(f"\n处理子文件夹: {item}")

            # 1. 提取 tag *文本*
            extracted_tag = None
            detected_brackets = None
            for bracket_type, (left, right) in CONFIG['bracket_pairs'].items():
                if item.startswith(left) and item.endswith(right):
                    detected_brackets = bracket_type
                    extracted_tag = item[len(left):-len(right)]  # 提取 *文本*
                    break

            # 2. 检查括号类型是否一致 (恢复选择功能)
            temp_brackets = CONFIG['brackets']  # 保存当前设置
            if detected_brackets and detected_brackets != CONFIG['brackets']:
                response = messagebox.askyesno(
                    "括号类型不一致",
                    f"子文件夹 '{item}' 的括号类型 ({detected_brackets}) 与设置 ({CONFIG['brackets']}) 不一致。\n\n"
                    f"是否要使用子文件夹名称的括号 ({detected_brackets})？\n\n"
                    "选择“是”将使用子文件夹的括号，选择“否”将使用设置中的括号。",
                )
                if response:
                    CONFIG['brackets'] = detected_brackets  # *临时* 更新

            # 3. 传递 *提取的* tag 文本
            if extracted_tag is not None:
                process_directory(item_path, extracted_tag, batch_mode=False)
            else:
                process_directory(item_path, item, batch_mode=False)

            CONFIG['brackets'] = temp_brackets  # 恢复设置

def settings_menu() -> None:
    """设置菜单"""
    while True:
        print("\n设置菜单：")
        print(f"1. 选择括号类型（当前：{CONFIG['brackets']}）")
        print(f"2. 切换标签位置 (当前: {'前缀' if CONFIG['tag_position'] == 'prefix' else '后缀'})")
        print("0. 返回主菜单")

        choice = input("请选择 (1, 2, 或 0): ").strip()

        if choice == '1':
            print("\n可选的括号类型：")
            for i, bracket_key in enumerate(CONFIG['bracket_pairs']):
                print(f"{i+1}. {bracket_key}")
            bracket_choice = input("请选择括号类型 (输入数字): ").strip()
            try:
                bracket_index = int(bracket_choice) - 1
                if 0 <= bracket_index < len(CONFIG['bracket_pairs']):
                    CONFIG['brackets'] = list(CONFIG['bracket_pairs'].keys())[bracket_index]
                    print(f"已选择括号类型: {CONFIG['brackets']}")
                else:
                    print("无效的括号类型选择。")
            except ValueError:
                print("无效的输入。请输入数字。")

        elif choice == '2':
            if CONFIG['tag_position'] == 'prefix':
                CONFIG['tag_position'] = 'suffix'
                print("标签位置已切换为：后缀")
            else:
                CONFIG['tag_position'] = 'prefix'
                print("标签位置已切换为：前缀")

        elif choice == '0':
            break
        else:
            print("无效的选项。")

def main() -> None:
    """主函数"""
    root = tk.Tk()
    root.withdraw()
    directory = os.path.dirname(os.path.abspath(__file__))  # 在循环外部初始化

    while True:
        print("\n请选择操作：")
        print("1. 处理脚本所在文件夹")
        print("2. 选择文件夹")
        print("3. 批量处理子文件夹 (以子文件夹名为 tag)")
        print("4. 移除现有标签")
        print("999. 设置")
        print("0. 退出")

        choice = input("请选择 (1, 2, 3, 4, 999, 或 0): ").strip()

        if choice == '999':
            settings_menu()
        elif choice == '4':  # 移除现有标签 (修复)
            # directory = os.path.dirname(os.path.abspath(__file__))  # 移到循环外部
            remove_existing_tags(directory)
            continue
        elif choice in ('1', '2', '3'):
            if choice == '1':
                # directory = os.path.dirname(os.path.abspath(__file__)) # 移到循环外部
                print(f"处理脚本所在文件夹: {directory}")
            elif choice == '2':
                directory = filedialog.askdirectory(title="选择包含 JSON 文件的文件夹")
                if not directory:
                    print("未选择文件夹。")
                    continue
                print(f"处理文件夹: {directory}")
            elif choice == '3':
                # directory = os.path.dirname(os.path.abspath(__file__)) # 移到循环外部
                print(f"处理脚本所在文件夹下的子文件夹: {directory}")
                process_subdirectories_with_tag(directory)
                continue

            tag = input("请输入要添加或修改的标签 (留空则不添加): ").strip()
            process_directory(directory, tag)

        elif choice == '0':
            print("退出程序。")
            break
        else:
            print("无效的选项。")
if __name__ == "__main__":
    main()