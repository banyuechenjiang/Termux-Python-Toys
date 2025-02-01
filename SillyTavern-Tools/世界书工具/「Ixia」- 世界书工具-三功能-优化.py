import json
import os
from datetime import datetime
from typing import Optional, List, Tuple
import shutil  # 导入 shutil 模块，用于删除文件夹

def select_directory() -> Optional[str]:
    """
    让用户选择一个目录。
    该函数会列出当前工作目录下的所有文件夹，并允许用户通过输入数字 ID 选择一个文件夹。
    如果用户选择 '0' 或取消选择，则返回 None。
    """
    current_dir = os.getcwd()
    print("-" * 30)
    print(f"当前工作目录: {current_dir}")
    print("-" * 30)

    all_items = [item for item in os.listdir('.') if os.path.isdir(item)]
    if not all_items:
        print("  当前目录下没有找到任何文件夹。")
        return None

    print("\n请选择要处理的文件夹 (输入数字 ID):")
    for i, item in enumerate(all_items):
        print(f"  {i+1}. {item}")
    print("  0. 退出")

    while True:
        try:
            choice = int(input("请输入数字 ID (0 - {}): ".format(len(all_items))))
            if choice == 0:
                print("  您选择了退出操作。")
                return None
            elif 1 <= choice <= len(all_items):
                selected_dir = all_items[choice - 1]
                confirmation_input = input(f"您选择了: {selected_dir}, 确认选择此文件夹吗? (y/n, 默认: y): ").lower()
                if confirmation_input == '' or confirmation_input == 'y':
                    print(f"  已确认选择文件夹: {selected_dir}")
                    return selected_dir
                elif confirmation_input == 'n':
                    print("  已取消选择，请重新选择。")
                else:
                    print("  无效的输入，请输入 'y' 或 'n' 或直接回车确认。")
            else:
                print("  无效的数字 ID，请输入有效范围内的数字。")
        except ValueError:
            print("  无效的输入，请输入数字。")

def create_entry(info: dict, order: int, depth: int) -> dict:
    """
    创建世界书条目字典。
    根据传入的信息字典 `info`，创建符合世界书 JSON 格式的条目数据结构。
    此函数用于生成 JSON 文件时构建条目。
    """
    return {
        "uid": info.get("uid"),
        "key": info.get("key"),
        "keysecondary": info.get("keysecondary"),
        "comment": info.get("comment"),
        "content": info.get("content"),
        "constant": False,
        "vectorized": False,
        "selective": True,
        "selectiveLogic": 0,
        "addMemo": True,
        "order": order,
        "position": 1,
        "disable": False,
        "excludeRecursion": False,
        "preventRecursion": True,
        "delayUntilRecursion": False,
        "probability": 100,
        "matchWholeWords": None,
        "useProbability": True,
        "depth": depth,
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": None,
        "caseSensitive": None,
        "useGroupScoring": None,
        "automationId": "",
        "role": None,
        "sticky": 0,
        "cooldown": 0,
        "delay": 0,
        "displayIndex": info.get("displayIndex")
    }

def create_divider_entry(uid: int, display_index: int, text: str, fileList: Optional[List[str]] = None, isStart: bool = False, startOrder: int = 0) -> dict:
    """
    创建分隔符条目字典，用于在世界书 JSON 中标记文件夹的开始和结束。
    分隔符条目用于在反向提取时重建文件夹结构。
    `isStart` 参数用于区分是起始分隔符还是结束分隔符。
    """
    folderName = text.split('/').pop()
    content = ""
    position = 0
    order = 0
    random_directive_start = "{{random: "
    random_directive_end = "}}"
    list_start_tag = f"<{folderName}-列表>\n "
    list_end_tag = f"\n</{folderName}-列表>"

    if isStart:
        if fileList:
            fileListStr = ",".join(fileList)
            content = list_start_tag + random_directive_start + fileListStr + random_directive_end + list_end_tag
        else:
            content = list_start_tag + random_directive_start + random_directive_end + list_end_tag

        position = 0
        order = startOrder
    else:
        position = 1,
        order = startOrder + 2

    comment = f"--始 {folderName}--" if isStart else f"--{folderName} 终--"

    return {
        "uid": uid,
        "key": [folderName],
        "keysecondary": [],
        "comment": comment,
        "content": content,
        "constant": True,
        "vectorized": False,
        "selective": True,
        "selectiveLogic": 0,
        "addMemo": True,
        "order": order,
        "position": position[0] if isinstance(position, tuple) else position,
        "disable": False,
        "excludeRecursion": False,
        "preventRecursion": False,
        "delayUntilRecursion": False,
        "probability": 100,
        "matchWholeWords": None,
        "useProbability": True,
        "depth": 4,
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": None,
        "caseSensitive": None,
        "useGroupScoring": None,
        "automationId": "",
        "role": 1,
        "sticky": 0,
        "cooldown": 0,
        "delay": 0,
        "displayIndex": display_index
    }

def extract_info(content: str, fileName: str, relative_folder_path: str, root_folder_name: str, uid: int, displayIndex: int) -> dict:
    """
    从文件内容中提取条目信息。
    从读取的文件内容、文件名和文件路径中提取关键信息，
    用于创建世界书条目。确定条目的 key，comment 和 content 等字段。
    """
    title = os.path.splitext(fileName)[0]
    if relative_folder_path:
        folderParts = relative_folder_path.replace("\\", "/").split('/')
        folderName = folderParts[-1]
        key_value = [folderName]
    else:
        key_value = [root_folder_name]

    return {
        "uid": uid,
        "key": key_value,
        "keysecondary": [title],
        "comment": title,
        "content": content,
        "displayIndex": displayIndex,
        "fileSize": len(content.encode('utf-8'))
    }


def generate_worldbook_json(root_dir: str, output_filename: str = 'worldbook.json'):
    """
    遍历指定根目录下的文件夹和文件，生成 worldbook.json 文件。
    此函数是生成世界书 JSON 文件的核心函数。
    它会递归遍历指定目录，读取 .txt 和 .md 文件内容，
    并将其转换为世界书 JSON 格式，最后保存到文件。
    """
    print("-" * 30)
    print("开始生成 世界书.json 文件...")
    print("-" * 30)

    entries = {}
    uid_counter = 0
    display_index = 0
    folder_order = 99
    current_folder = ""

    now = datetime.now()
    formatted_date = now.strftime("%Y/%m/%d %H:%M:%S")
    metadata_content = """{{//
---
生成时间: {}
---
世界书描述：
标签：
---
配置信息：
 - 区分大小写:  否
---
免责声明：
本世界书由半自动化工具生成，可能包含不准确或不完善的信息。
用户应自行判断信息的适用性，并承担使用本世界书的风险。
本世界书中的内容，不构成任何形式的建议或保证。
本工具不保证生成的文本完全符合预期，也不对由此产生的任何直接或间接损失负责。
---
内容来源：本世界书的内容由用户提供的文本文件生成，本工具不对这些文件的内容和来源的合法性负责。
---
版权声明：
本世界书采用知识共享署名-相同方式共享 4.0 国际许可协议进行许可。
(Creative Commons Attribution-ShareAlike 4.0 International License)
查看许可证副本请访问：https://creativecommons.org/licenses/by-sa/4.0/
---
作者：
---
}}""".format(formatted_date)

    entries[uid_counter] = {
        "uid": uid_counter,
        "key": [],
        "keysecondary": [],
        "comment": "【说明】",
        "content": metadata_content,
        "constant": True,
        "vectorized": False,
        "selective": False,
        "selectiveLogic": 0,
        "addMemo": True,
        "order": 98,
        "position": 0,
        "disable": False,
        "excludeRecursion": False,
        "preventRecursion": False,
        "delayUntilRecursion": False,
        "probability": 100,
        "matchWholeWords": None,
        "useProbability": True,
        "depth": 4,
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": None,
        "caseSensitive": None,
        "useGroupScoring": None,
        "automationId": "",
        "role": 1,
        "sticky": 0,
        "cooldown": 0,
        "delay": 0,
        "displayIndex": display_index
    }
    uid_counter += 1
    display_index += 1

    uploadFolderName = os.path.basename(root_dir)

    total_files_processed = 0
    for folder_path, dirnames, filenames in os.walk(root_dir):
        dirnames.sort()
        filenames.sort()

        folderName = os.path.basename(folder_path)
        if folderName == uploadFolderName:
            continue

        relative_folder_path = os.path.relpath(folder_path, root_dir)

        if current_folder != relative_folder_path:
            if current_folder != "":
                entries[uid_counter] = create_divider_entry(uid_counter, display_index, f"End of {current_folder}", None, False, folder_order)
                uid_counter += 1
                display_index += 1

            current_folder_files = sorted([os.path.splitext(f)[0] for f in filenames if f.endswith(('.txt', '.md'))])
            entries[uid_counter] = create_divider_entry(uid_counter, display_index, relative_folder_path, current_folder_files, True, folder_order)
            uid_counter += 1
            display_index += 1
            current_folder = relative_folder_path
            folder_order += 10
            print(f"\n  处理文件夹: {relative_folder_path}")

        for file_name in filenames:
            if file_name.endswith(('.txt', '.md')):
                file_path = os.path.join(folder_path, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    print(f"  读取文件 {file_path} 失败: {e}")
                    continue

                info = extract_info(content, file_name, relative_folder_path, uploadFolderName, uid_counter, display_index)
                if info:
                    depth = 4
                    file_size = info["fileSize"]
                    if file_size <= 512: depth = 4
                    elif file_size <= 1024: depth = 5
                    elif file_size <= 1536: depth = 6
                    elif file_size <= 2048: depth = 7
                    else: depth = 8

                    order = folder_order + 1
                    entries[uid_counter] = create_entry(info, order, depth)
                    uid_counter += 1
                    display_index += 1
                    total_files_processed += 1

    if current_folder != "":
        entries[uid_counter] = create_divider_entry(uid_counter, display_index, f"End of {current_folder}", None, False, folder_order)

    worldbook = {"entries": entries}
    output = json.dumps(worldbook, indent=2, ensure_ascii=False)

    try:
        output_filepath = f"「Ixia」-世界书 - {uploadFolderName}.json"
        with open(output_filepath, 'w', encoding='utf-8') as outfile:
            outfile.write(output)
        print(f"\n{'-' * 30}")
        print(f"世界书.json 文件生成成功: {output_filepath}")
        print(f"共处理了 {total_files_processed} 个文本文件。")
        print(f"{'-' * 30}")
    except Exception as e:
        print(f"生成 世界书.json 文件失败: {e}")

def select_json_file() -> Optional[str]:
    """
    列出当前目录下所有 JSON 文件，并让用户通过数字 ID 选择。
    该函数扫描当前目录下的所有 .json 文件，并列出供用户选择。
    如果用户选择 '0' 或取消选择，则返回 None。
    """
    current_dir = os.getcwd()
    print("-" * 30)
    print(f"当前工作目录: {current_dir}")
    print("-" * 30)

    all_files = os.listdir('.')
    json_files = [f for f in all_files if f.endswith('.json')]
    json_files.sort()

    if not json_files:
        print("  当前目录下没有找到任何 JSON 文件。")
        return None

    print("\n请选择要处理的 JSON 文件 (输入数字 ID):")
    for i, filename in enumerate(json_files):
        print(f"  {i+1}. {filename}")
    print("  0. 退出")

    while True:
        try:
            choice = int(input("请输入数字 ID (0 - {}): ".format(len(json_files))))
            if choice == 0:
                print("  您选择了退出操作。")
                return None
            elif 1 <= choice <= len(json_files):
                selected_file = json_files[choice - 1]
                confirmation_input = input(f"您选择了: {selected_file}, 确认执行拆分吗? (y/n, 默认: y): ").lower()
                if confirmation_input == '' or confirmation_input == 'y':
                    print(f"  已确认选择 JSON 文件: {selected_file}")
                    return selected_file
                elif confirmation_input == 'n':
                    print("  已取消选择，请重新选择。")
                else:
                    print("  无效的输入，请输入 'y' 或 'n' 或直接回车确认。")
            else:
                print("  无效的数字 ID，请输入有效范围内的数字。")
        except ValueError:
            print("  无效的输入，请输入数字。")


def is_metadata_entry(entry_data: dict) -> bool:
    """
    判断给定的条目数据是否为 "【说明】" 元数据条目。
    元数据条目通常用于存储世界书的描述、标签等信息。
    """
    return entry_data.get('comment') == "【说明】" and entry_data.get('uid') == 0 # 修改处：将 or 改为 and

def is_divider_entry(entry_data: dict) -> bool:
    """
    判断给定的条目数据是否为分隔符条目（始/终 条目）。
    分隔符条目用于标记文件夹的开始和结束，方便在反向提取时重建目录结构。
    """
    comment = entry_data.get('comment', '')
    return comment.startswith("--") and comment.endswith("--")

def extract_folder_name(entry_data: dict) -> Optional[str]:
    """
    从条目数据中提取文件夹名称。
    根据条目数据中的 'key' 字段，尝试提取文件夹名称。
    'key' 字段通常存储文件夹名称信息。
    """
    folder_name_list = entry_data.get('key')
    if isinstance(folder_name_list, list) and folder_name_list:
        return folder_name_list[0]
    elif isinstance(folder_name_list, str) and folder_name_list:
        return folder_name_list
    return None

def extract_file_name(entry_data: dict, output_file_ext: str, entry_id: str) -> str:
    """
    从条目数据中提取文件名。
    优先使用 'comment' 字段作为文件名，如果 'comment' 为空，则尝试使用 'keysecondary' 字段。
    如果都为空，则生成默认文件名。
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
    此函数负责根据条目数据，在指定的输出目录下创建相应的文件夹和文件，
    并将条目的 'content' 写入到文件中。
    """
    print(f" 处理条目 {processed_entries_count}/{total_entries} (ID: {entry_id})...", end="")

    if is_metadata_entry(entry_data):
        print(f" 跳过 \"【说明】\" 条目, 该条目通常包含世界书元数据。")
        return

    folder_name = extract_folder_name(entry_data)
    if not folder_name:
        warning_message = f" 警告: 条目 (ID: {entry_id}) 缺少有效的 'key' (关键字)，无法确定文件夹名称，跳过条目。"
        print(warning_message)
        return

    if is_divider_entry(entry_data):
        comment = entry_data.get('comment', '')
        if comment.startswith("--始 "):
            divider_folder_name = comment[4:-2]
            print(f" 跳过 {divider_folder_name} 条目（始），仅用于构建文件夹结构。")
        elif comment.startswith("--") and comment.endswith(" 终--"):
            divider_folder_name = comment[2:-4].strip()
            print(f" 跳过 {divider_folder_name} 条目（终），仅用于构建文件夹结构。")
        return

    file_name = extract_file_name(entry_data, output_file_ext, entry_id)
    content = entry_data.get('content', '')

    folder_path = os.path.join(output_root_dir, folder_name)
    file_path = os.path.join(folder_path, file_name)

    os.makedirs(folder_path, exist_ok=True)

    try:
        with open(file_path, 'w', encoding='utf-8') as outfile:
            outfile.write(str(content))
        print(f" 文件 '{file_name}' 创建成功。")
    except Exception as e:
        print(f" 写入文件 '{file_path}' 失败: {e}")


def split_worldbook_flexible(json_filepath: str, output_root_dir: str, output_file_ext: str = "txt"):
    """
    读取 worldbook.json 文件并根据条目拆分成文件夹和文件。
    此函数是反向提取世界书内容的核心函数。
    它读取世界书 JSON 文件，遍历每个条目，并根据条目信息重建文件夹和文件结构。
    """
    print("-" * 30)
    print(f"开始处理 JSON 文件: {json_filepath}")
    print(f"文件将拆分到目录: {output_root_dir}")
    print(f"文件扩展名: .{output_file_ext}")
    print("-" * 30)
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

    print(f"共计 {total_entries} 个条目待处理...")

    for entry_id, entry_data in entries.items():
        processed_entries_count += 1
        process_entry(entry_data, output_root_dir, output_file_ext, entry_id, processed_entries_count, total_entries)

    print(f"\n{'-' * 30}")
    print(f"\n世界书文件拆分处理完成，文件已保存到: {output_root_dir}")
    print(f"{'-' * 30}")


def extract_divider_info(entry_data: dict) -> Tuple[Optional[str], Optional[List[str]]]:
    """
    从 worldbook 条目中提取分隔符信息。
    如果给定的条目是分隔符条目，则解析其 'comment' 和 'content' 字段，
    提取文件夹名称和文件列表（如果存在）。
    如果不是分隔符条目，则返回 None, None。
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

def select_split_directory_for_deletion() -> Optional[str]:
    """
    让用户选择一个以 '-拆分' 结尾的目录进行删除。
    只列出当前工作目录下以 '-拆分' 结尾的文件夹，并允许用户选择删除。
    """
    current_dir = os.getcwd()
    print("-" * 30)
    print(f"当前工作目录: {current_dir}")
    print("-" * 30)

    split_directories = [item for item in os.listdir('.') if os.path.isdir(item) and item.endswith('-拆分')]
    if not split_directories:
        print("  当前目录下没有找到任何以 '-拆分' 结尾的文件夹。")
        return None

    print("\n请选择要删除的拆分文件夹 (输入数字 ID):")
    for i, item in enumerate(split_directories):
        print(f"  {i+1}. {item}")
    print("  0. 退出")

    while True:
        try:
            choice = int(input("请输入数字 ID (0 - {}): ".format(len(split_directories))))
            if choice == 0:
                print("  您选择了退出操作。")
                return None
            elif 1 <= choice <= len(split_directories):
                selected_dir = split_directories[choice - 1]
                print(f"  已选择删除文件夹: {selected_dir}") #  Removed confirmation here, moved to delete_directory
                return selected_dir
            else:
                print("  无效的数字 ID，请输入有效范围内的数字。")
        except ValueError:
            print("  无效的输入，请输入数字。")

def delete_directory(dir_name: str):
    """
    删除指定的文件夹及其所有内容。
    只需要一次确认，输入 "yes" 确认删除操作，防止误删。
    """
    dir_path = os.path.join(os.getcwd(), dir_name)
    if not os.path.exists(dir_path):
        print(f"  错误: 文件夹 '{dir_name}' 不存在。")
        return

    if not os.path.isdir(dir_path):
        print(f"  错误: '{dir_name}' 不是一个文件夹。")
        return

    confirmation_input = input(f"请确认您要**永久删除**文件夹 '{dir_name}' 及其所有内容 (输入 'yes' 确认): ").lower()
    if confirmation_input == 'yes':
        try:
            shutil.rmtree(dir_path)
            print(f"  文件夹 '{dir_name}' 及其内容已成功删除。")
        except Exception as e:
            print(f"  删除文件夹 '{dir_name}' 失败: {e}")
    else:
        print(f"  已取消删除文件夹 '{dir_name}' 操作。")


if __name__ == "__main__":
    while True: # 添加循环
        print("-" * 30)
        print("  欢迎使用 世界书 工具！")
        print("-" * 30)
        #  选择执行生成还是反提取
        # 检查是否存在 '-拆分' 文件夹，以决定是否显示删除选项
        has_split_folders = any(item.endswith('-拆分') and os.path.isdir(item) for item in os.listdir('.'))
        operation_options = "请选择操作类型 (输入数字 0-{}):\n".format(2 + (1 if has_split_folders else 0))
        operation_options += "1: 生成 世界书.json 文件\n"
        operation_options += "2: 从 世界书.json 文件反向提取为文件\n"
        if has_split_folders:
            operation_options += "3: 删除 '-拆分' 后缀的文件夹及其内容\n" # 新增选项
        operation_options += "0: 退出\n"

        operation_type = input(operation_options).strip() # 获取用户选择的操作类型

        if operation_type == '1':
            root_directory = select_directory()
            if root_directory:
                generate_worldbook_json(root_directory)
                print(f"\n操作完成，请检查生成的 世界书.json 文件。")
            else:
                print("\n用户取消操作。")
        elif operation_type == '2':
            selected_json = select_json_file() #  这里恢复了 select_json_file() 的正常调用
            if selected_json:
                json_filename_without_ext = os.path.splitext(selected_json)[0]
                output_dir_base = json_filename_without_ext

                prefix_to_remove = "「Ixia」-世界书 - "
                if output_dir_base.startswith(prefix_to_remove):
                    output_dir_base = output_dir_base[len(prefix_to_remove):]

                output_dir = f"{output_dir_base}-拆分"
                output_ext = input("请选择输出文件扩展名 (txt/md, 默认为 txt): ").strip().lower() or "txt"

                split_worldbook_flexible(selected_json, output_dir, output_ext)
                print(f"\n操作完成，请检查目录: {output_dir}")
            else:
                print("\n用户取消操作。")
        elif operation_type == '3' and has_split_folders: # 处理删除选项
            selected_split_dir = select_split_directory_for_deletion()
            if selected_split_dir:
                delete_directory(selected_split_dir) # Directly call delete_directory after selection
            else:
                print("\n用户取消删除文件夹操作。")
        elif operation_type == '0': # 处理 0 选项
            print("  您选择了退出程序。")
            break # 退出循环
        else:
            print("无效的操作类型，请输入 0, 1, 2{}。".format(", 3" if has_split_folders else ""))
        print("-" * 30) # 分隔线
        print("  操作完成. 您可以继续选择其他操作或退出。") # 提示信息
        print("-" * 30) # 分隔线

    print("-" * 30)
    print("  感谢使用！")
    print("-" * 30)