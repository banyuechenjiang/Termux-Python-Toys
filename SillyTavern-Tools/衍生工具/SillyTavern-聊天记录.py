import os
import json
import time
import re

def list_files(path, file_type):
    """
    统计指定文件夹下指定类型的文件数量，并列出文件名。

    Args:
        path (str): 文件夹的绝对路径或相对路径。
        file_type (str): 文件类型，例如 ".png" 或 ".json"。

    Returns:
        list: 包含文件名的列表，如果没有找到文件则返回空列表。
    """
    try:
        if not os.path.exists(path):
            print(f"路径不存在: {path}")
            return []

        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and f.endswith(file_type)]

        if not files:
            print(f"在 {path} 中没有找到 {file_type} 文件。")
            return []

        print(f"在 {path} 中找到 {len(files)} 个 {file_type} 文件：")
        for index, file in enumerate(files):
            print(f"{index + 1}. {file}")
        return files
    except Exception as e:
        print(f"发生错误: {e}")
        return []
    
def sanitize_filename(filename):
    """
    清理文件名中的非法字符，使其可以作为文件名。
    同时也会清除首尾的空白字符以及一些特殊符号。

    Args:
        filename (str): 原始文件名。

    Returns:
        str: 清理后的文件名。
    """
    # 移除首尾空白字符
    filename = filename.strip()
    # 清理特殊符号和非法字符
    filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
    # 移除部分特殊字符，例如 ♥ 和 ✨
    filename = re.sub(r'[♥✨★☆]', '', filename)
    # 移除 Emoji
    filename = re.sub("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                           "]+", "", filename, flags=re.UNICODE)

    return filename

def format_chat_log(data, remove_tags=False):
    """
    将 JSONL 数据格式化为人类可读的聊天记录。

    Args:
        data (list): 包含 JSON 对象的列表。
        remove_tags (bool): 是否移除 <thinking>、<memory> 和 <think> 标签。

    Returns:
        str: 格式化后的聊天记录。
    """
    chat_log = ""
    for entry in data:
        if "name" in entry and "mes" in entry:
            name = entry["name"]
            message = entry["mes"]

            # 处理消息中的换行符
            message = message.replace("\\n", "\n")

            if remove_tags:
                # 移除 <thinking>...</thinking> 标签及其内容
                message = re.sub(r"<thinking>[\s\S]*?</thinking>", "", message, flags=re.DOTALL)
                 # 移除 <think>...</think> 标签及其内容
                message = re.sub(r"<think>[\s\S]*?</think>", "", message, flags=re.DOTALL)
                # 移除 <memory>...</memory> 标签及其内容
                message = re.sub(r"<memory>[\s\S]*?</memory>", "", message, flags=re.DOTALL)

            chat_log += f"{name}: {message}\n\n"
    
    # 移除开头可能的空行
    chat_log = chat_log.lstrip('\n')

    return chat_log

def process_jsonl_chat(file_path, output_dir):
    """
    读取 JSONL 聊天记录文件，清洗数据，并将其转换为人类可读的格式。
    提供选项：直接查看或保存为txt文件。

    Args:
        file_path (str): JSONL 文件的路径。
        output_dir (str): 输出文件的目录（查看或保存txt）。
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = []
            for line in f:
                try:
                    json_obj = json.loads(line)
                    data.append(json_obj)
                except json.JSONDecodeError:
                    print(f"Error decoding JSON line in {file_path}. Skipping line.")
                    continue

        if not data:
            print(f"No valid JSON data found in {file_path}.")
            return

        # 格式化聊天记录
        
        source_filename = os.path.splitext(os.path.basename(file_path))[0]

        while True:
            print("\n请选择操作：")
            print("1. 直接查看聊天记录")
            print("2. 保存为 TXT 文件")
            print("0. 返回上一级")

            choice = input("请输入选项编号：")

            if choice == '1':
                # 查看时移除标签
                formatted_chat = format_chat_log(data, remove_tags=True)
                lines = formatted_chat.split('\n\n')
                line_index = 0
                while line_index < len(lines):
                    print(lines[line_index])
                    user_input = input("按回车键继续 (输入 0 退出): ")
                    if user_input == '0':
                        break
                    line_index += 1
                break  # 查看完后退出循环
            elif choice == '2':
                # 保存时保留标签
                formatted_chat = format_chat_log(data, remove_tags=False)
                # 获取源文件名（不含扩展名）并进行清理
                cleaned_filename = sanitize_filename(source_filename) + "_formatted.txt"
                output_path = os.path.join(output_dir, cleaned_filename)

                with open(output_path, "w", encoding="utf-8") as outfile:
                    outfile.write(formatted_chat)

                print(f"Formatted chat log saved to: {output_path}")
                break  # 保存后退出循环
            elif choice == '0':
                return  # 返回上一级
            else:
                print("无效的选项编号。")

    except Exception as e:
        print(f"Error processing {file_path}: {e}")

def main():
    """
    主函数，处理用户选择并执行相应的操作。
    """
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.join(script_dir, "SillyTavern", "data", "default-user")
    chats_path = os.path.join(base_path, "chats")

    if not os.path.exists(chats_path):
        print("未找到SillyTavern chats文件夹，请手动指定路径！")
        base_path = input("请输入SillyTavern/data/default-user文件夹的绝对路径：")
        chats_path = os.path.join(base_path, "chats")

    while True:
        # 列出 chats 文件夹下的所有子文件夹
        char_dirs = [d for d in os.listdir(chats_path) if os.path.isdir(os.path.join(chats_path, d))]

        if not char_dirs:
            print("未找到任何角色文件夹。")
            print("按任意键退出")
            input()
            return  # 无角色文件夹时，直接退出

        print("\n请选择要处理的角色文件夹：")
        for index, char_dir in enumerate(char_dirs):
            print(f"{index + 1}. {char_dir}")
        print("0. 退出") # 更改为退出选项

        try:
            choice = int(input("请输入选项编号："))
            if choice == 0:
                print("退出程序。")
                break # 退出循环
            elif 0 < choice <= len(char_dirs):
                selected_char_dir = char_dirs[choice - 1]
                char_dir_path = os.path.join(chats_path, selected_char_dir)

                # 列出选择的文件夹下的所有 .jsonl 文件
                jsonl_files = [f for f in os.listdir(char_dir_path) if os.path.isfile(os.path.join(char_dir_path, f)) and f.endswith(".jsonl")]
                
                # 如果只有一个 .jsonl 文件，直接处理
                if len(jsonl_files) == 1:
                    file_path = os.path.join(char_dir_path, jsonl_files[0])
                    process_jsonl_chat(file_path, char_dir_path)
                elif len(jsonl_files) >1:
                    # 如果有多个 .jsonl 文件，让用户选择
                    print(f"\n请选择要处理的 JSONL 文件：")
                    for index, jsonl_file in enumerate(jsonl_files):
                        print(f"{index + 1}. {jsonl_file}")
                    print("0. 返回上一级")

                    file_choice = int(input("请输入选项编号："))
                    if file_choice == 0:
                        print("返回上一级")
                        continue
                    elif 0 < file_choice <= len(jsonl_files):
                        selected_file = jsonl_files[file_choice - 1]
                        file_path = os.path.join(char_dir_path, selected_file)

                        # 处理选定的 JSONL 文件
                        process_jsonl_chat(file_path, char_dir_path)
                    else:
                        print("无效的选项编号。")
                else:
                    print(f"在 {char_dir_path} 中没有找到 .jsonl 文件。")
                    continue
            else:
                print("无效的选项编号。")
        except (ValueError, IndexError):
            print("无效的输入，请输入数字。")
        except Exception as e:
            print(f"发生错误: {e}")

if __name__ == "__main__":
    main()