import json
import os
from typing import Optional, List, Tuple

def select_json_file() -> Optional[str]:
    """
    列出当前目录下所有 JSON 文件，并让用户通过数字 ID 选择。
    返回选择的文件路径，如果用户选择退出则返回 None。
    优化：直接回车默认选择 'y' (确认拆分)。
    """
    current_dir = os.getcwd()
    print(f"当前工作目录: {current_dir}")

    all_files = os.listdir('.')
    json_files = [f for f in all_files if f.endswith('.json')]

    if not json_files:
        print("当前目录下没有找到任何 JSON 文件。")
        return None

    print("\n请选择要处理的 JSON 文件 (输入数字 ID):")
    for i, filename in enumerate(json_files):
        print(f"{i+1}. {filename}")
    print("0. 退出")

    while True:
        try:
            choice = int(input("请输入数字 ID (0 - {}): ".format(len(json_files))))
            if choice == 0:
                return None
            elif 1 <= choice <= len(json_files):
                selected_file = json_files[choice - 1]
                confirmation_input = input(f"您选择了: {selected_file}, 确认执行拆分吗? (y/n, 默认: y): ").lower()
                if confirmation_input == '' or confirmation_input == 'y':
                    return selected_file
                elif confirmation_input == 'n':
                    print("已取消选择，请重新选择。")
                else:
                    print("无效的输入，请输入 'y' 或 'n' 或直接回车确认。")
            else:
                print("无效的数字 ID，请输入有效范围内的数字。")
        except ValueError:
            print("无效的输入，请输入数字。")


def is_metadata_entry(entry_data: dict) -> bool:
    """
    判断给定的条目数据是否为 "【说明】" 元数据条目。

    Args:
        entry_data (dict): 单个世界书条目的字典数据。

    Returns:
        bool: 如果是元数据条目则返回 True，否则返回 False。
    """
    return entry_data.get('comment') == "【说明】" or entry_data.get('uid') == 0

def is_divider_entry(entry_data: dict) -> bool:
    """
    判断给定的条目数据是否为分隔符条目（始/终 条目）。

    Args:
        entry_data (dict): 单个世界书条目的字典数据。

    Returns:
        bool: 如果是分隔符条目则返回 True，否则返回 False。
    """
    comment = entry_data.get('comment', '')
    return comment.startswith("--") and comment.endswith("--")

def extract_folder_name(entry_data: dict) -> Optional[str]:
    """
    从条目数据中提取文件夹名称。

    Args:
        entry_data (dict): 单个世界书条目的字典数据。

    Returns:
        Optional[str]: 文件夹名称字符串，如果无法提取则返回 None。
    """
    folder_name_list = entry_data.get('key')
    if isinstance(folder_name_list, list) and folder_name_list:
        return folder_name_list[0]
    elif isinstance(folder_name_list, str) and folder_name_list:
        return folder_name_list
    return None

def extract_file_name(entry_data: dict, output_file_ext: str, entry_id: str) -> str:
    """
    从条目数据中提取文件名，如果 comment 为空，则尝试 keysecondary，否则使用默认文件名。

    Args:
        entry_data (dict): 单个世界书条目的字典数据。
        output_file_ext (str): 输出文件的扩展名。
        entry_id (str): 条目的 ID，用于生成默认文件名。

    Returns:
        str: 文件名字符串，包含扩展名。
    """
    file_name = entry_data.get('comment', '').strip()
    if not file_name:
        keysecondary_list = entry_data.get('keysecondary')
        if isinstance(keysecondary_list, list) and keysecondary_list:
            file_name = keysecondary_list[0] + f".{output_file_ext}"
        elif isinstance(keysecondary_list, str) and keysecondary_list:
            file_name = keysecondary_list + f".{output_file_ext}"
        else:
            file_name = f"untitled_{entry_id}.{output_file_ext}"
    else:
        file_name = file_name + f".{output_file_ext}"
    return file_name


def process_entry(entry_data: dict, output_root_dir: str, output_file_ext: str, entry_id: str, processed_entries_count: int, total_entries: int):
    """
    处理单个世界书条目，提取信息，创建文件夹和文件，并写入内容。

    Args:
        entry_data (dict): 单个世界书条目的字典数据。
        output_root_dir (str): 输出文件夹的根目录。
        output_file_ext (str): 输出文件的扩展名。
        entry_id (str): 条目的 ID。
        processed_entries_count (int): 当前已处理的条目计数。
        total_entries (int): 总条目数。
    """
    print(f"\n处理条目 {processed_entries_count}/{total_entries} (ID: {entry_id})...", end="")

    if is_metadata_entry(entry_data):
        print(f" 跳过 \"【说明】\" 条目, 该条目通常包含世界书元数据。", end="")
        return

    folder_name = extract_folder_name(entry_data)
    if not folder_name:
        warning_message = f" 警告: 条目 (ID: {entry_id}) 缺少有效的 'key' (关键字)，无法确定文件夹名称，跳过条目。"
        print(warning_message, end="")
        return

    if is_divider_entry(entry_data):
        comment = entry_data.get('comment', '')
        if comment.startswith("--始 "):
            divider_folder_name = comment[4:-2]
            print(f" 跳过 {divider_folder_name} 条目（始），仅用于构建文件夹结构。", end="")
        elif comment.startswith("--") and comment.endswith(" 终--"):
            divider_folder_name = comment[2:-4].strip()
            print(f" 跳过 {divider_folder_name} 条目（终），仅用于构建文件夹结构。", end="")
        return

    file_name = extract_file_name(entry_data, output_file_ext, entry_id)
    content = entry_data.get('content', '')

    folder_path = os.path.join(output_root_dir, folder_name)
    file_path = os.path.join(folder_path, file_name)

    os.makedirs(folder_path, exist_ok=True)

    try:
        with open(file_path, 'w', encoding='utf-8') as outfile:
            outfile.write(str(content))
        print(f" 文件 '{file_name}' 创建成功。", end="")
    except Exception as e:
        print(f" 写入文件 '{file_path}' 失败: {e}", end="")


def split_worldbook_flexible(json_filepath: str, output_root_dir: str, output_file_ext: str = "txt"):
    """
    读取 worldbook.json 文件并根据条目拆分成文件夹和文件，
    更灵活地处理可能经过手动修改的 JSON 文件, 并优化警告、进度信息。
    改进分隔符条目的 print 说明。
    代码结构优化，函数拆分，添加类型提示和注释。

    Args:
        json_filepath (str): worldbook.json 文件的路径。
        output_root_dir (str): 输出文件夹的根目录。
        output_file_ext (str): 输出文件的扩展名，默认为 "txt"，可选 "md"。
    """
    print(f"\n开始处理 JSON 文件: {json_filepath}")
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            worldbook_data = json.load(f)
    except FileNotFoundError:
        print(f"错误: JSON 文件未找到: {json_filepath}")
        return
    except json.JSONDecodeError:
        print(f"错误: JSON 文件解析失败，请检查文件 '{json_filepath}' 格式是否正确，可能不是有效的 JSON 文件。")
        return

    entries = worldbook_data.get('entries', {})
    total_entries = len(entries)
    processed_entries_count = 0

    for entry_id, entry_data in entries.items():
        processed_entries_count += 1
        process_entry(entry_data, output_root_dir, output_file_ext, entry_id, processed_entries_count, total_entries)

    print(f"\n\nWorldbook 拆分处理完成，文件已保存到: {output_root_dir}")


def extract_divider_info(entry_data: dict) -> Tuple[Optional[str], Optional[List[str]]]:
    """
    从 worldbook 条目中提取分隔符信息（如果它是分隔符条目）。
    返回文件夹名称 (str) 和 文件列表 (list of str)，如果不是分隔符条目则返回 None, None。
    """
    comment = entry_data.get('comment', '')
    content = entry_data.get('content', '')

    if comment.startswith("--始 ") and comment.endswith("--"):
        folder_name = comment[4:-2]
        file_list_str = content.strip()
        file_list = []
        if file_list_str.startswith(f"<{folder_name}-列表>") and file_list_str.endswith(f"</{folder_name}-列表>"):
            inner_content = file_list_str[len(f"<{folder_name}-列表>"): -len(f"</{folder_name}-列表>")].strip()
            if inner_content.startswith("{{random: ") and inner_content.endswith("}}"):
                random_content = inner_content[len("{{random: "):-2].strip()
                file_list = [f.strip() for f in random_content.split(',') if f.strip()]
        return folder_name, file_list
    elif comment.startswith("--") and comment.endswith(" 终--"):
        folder_name = comment[2:-4].strip()
        return folder_name, None
    else:
        return None, None


if __name__ == "__main__":
    selected_json = select_json_file()
    if selected_json:
        json_filename_without_ext = os.path.splitext(selected_json)[0]
        output_dir_base = json_filename_without_ext

        prefix_to_remove = "「Ixia」-世界书 - "
        if output_dir_base.startswith(prefix_to_remove):
            output_dir_base = output_dir_base[len(prefix_to_remove):]

        output_dir = f"{output_dir_base}-拆分"
        output_ext = input("请选择输出文件扩展名 (txt/md, 默认为 txt): ").strip().lower() or "txt"

        split_worldbook_flexible(selected_json, output_dir, output_ext)
        print(f"请检查目录: {output_dir}")
    else:
        print("用户取消操作。")