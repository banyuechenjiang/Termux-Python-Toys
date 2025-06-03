import os
import json
import zipfile
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

def backup_files(source_path, file_type, backup_dir):
    """
    备份指定文件夹下指定类型的文件到 zip 压缩包。

    Args:
        source_path (str): 源文件夹的绝对路径。
        file_type (str): 文件类型，例如 ".png" 或 ".json"。
        backup_dir (str): 备份文件（zip 压缩包）保存的目录。
    """
    try:
        files_to_backup = list_files(source_path, file_type)
        if not files_to_backup:
            return

        timestamp = time.strftime("%Y%m%d-%H%M%S")

        # 如果是世界书文件，尝试读取json内容获取name键值作为文件名的一部分
        if file_type == ".json" and "worlds" in source_path:
            first_file_path = os.path.join(source_path, files_to_backup[0])
            try:
                with open(first_file_path, "r", encoding="utf-8") as f:
                    world_data = json.load(f)
                    world_name = world_data.get("name", "")
                    if world_name:
                        world_name = sanitize_filename(world_name)
                    else:
                        # 如果name为空，使用对应的源文件名
                        world_name = sanitize_filename(os.path.splitext(files_to_backup[0])[0])
            except (json.JSONDecodeError, UnicodeDecodeError):
                print(f"Error decoding JSON in {first_file_path}. Using source file name.")
                world_name = sanitize_filename(os.path.splitext(files_to_backup[0])[0])

            zip_filename = f"backup_worlds_{world_name}_{timestamp}.zip"

        else:
            zip_filename = f"backup_{os.path.basename(source_path)}_{timestamp}.zip"

        zip_path = os.path.join(backup_dir, zip_filename)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file in files_to_backup:
                file_path = os.path.join(source_path, file)
                zipf.write(file_path, arcname=file)

        print(f"已将 {source_path} 中的 {file_type} 文件备份到 {zip_path}")
    except Exception as e:
        print(f"备份过程中发生错误: {e}")

def extract_files(backup_dir, data_path):
    """
    解压备份文件夹中的 zip 文件到对应的文件夹下。

    Args:
        backup_dir (str): 备份文件所在的目录。
        data_path (str): SillyTavern 数据目录的绝对路径。
    """
    try:
        zip_files = [f for f in os.listdir(backup_dir) if os.path.isfile(os.path.join(backup_dir, f)) and f.endswith(".zip")]

        if not zip_files:
            print("在备份文件夹中没有找到 zip 文件。")
            return

        print("\n请选择要解压的备份文件：")
        for index, zip_file in enumerate(zip_files):
            print(f"{index + 1}. {zip_file}")
        print("0. 返回")

        choice = int(input("请输入选项编号："))
        if choice == 0:
            return
        elif 0 < choice <= len(zip_files):
            selected_zip = zip_files[choice - 1]
            zip_path = os.path.join(backup_dir, selected_zip)

            with zipfile.ZipFile(zip_path, "r") as zipf:
                for file in zipf.namelist():
                    # 根据文件名判断解压到哪个文件夹
                    if file.endswith(".png"):
                        extract_path = os.path.join(data_path, "characters")
                    elif file.endswith(".json"):
                        if "backup_worlds_" in selected_zip:
                            extract_path = os.path.join(data_path, "worlds")
                        elif "OpenAI Settings" in selected_zip:
                            extract_path = os.path.join(data_path, "OpenAI Settings")
                        elif "QuickReplies" in selected_zip:
                            extract_path = os.path.join(data_path, "QuickReplies")
                        else:
                            extract_path = data_path  # Default extraction path
                    else:
                        extract_path = data_path  # Default extraction path

                    # 确保解压路径存在
                    os.makedirs(extract_path, exist_ok=True)
                    zipf.extract(file, extract_path)

            print(f"已将 {selected_zip} 解压到对应的文件夹")
        else:
            print("无效的选项编号。")
    except (ValueError, IndexError):
        print("无效的输入，请输入数字。")
    except Exception as e:
        print(f"解压过程中发生错误: {e}")
        
def main():
    """
    主函数，处理用户选择并执行相应的操作。
    """
    # 获取脚本所在目录的父目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.join(script_dir, "SillyTavern", "data", "default-user")
    backup_path = os.path.join(script_dir, "SillyTavern-Backup")

    # 确保备份文件夹存在
    os.makedirs(backup_path, exist_ok=True)

    if not os.path.exists(base_path):
        print("未找到SillyTavern文件夹，请手动指定路径！")
        base_path = input("请输入SillyTavern/data/default-user文件夹的绝对路径：")

    options = [
        {"path": os.path.join(base_path, "characters"), "type": ".png", "desc": "characters 文件夹下的 PNG 文件"},
        {"path": os.path.join(base_path, "OpenAI Settings"), "type": ".json", "desc": "OpenAI Settings 文件夹下的 JSON 文件"},
        {"path": os.path.join(base_path, "QuickReplies"), "type": ".json", "desc": "QuickReplies 文件夹下的 JSON 文件"},
        {"path": os.path.join(base_path, "worlds"), "type": ".json", "desc": "worlds 文件夹下的 JSON 文件"},
    ]

    while True:
        print("\n请选择要执行的操作：")
        print("1. 统计文件")
        print("2. 备份文件")
        print("3. 解压文件")
        print("0. 退出")

        try:
            choice = int(input("请输入选项编号："))

            if choice == 0:
                print("退出程序。")
                break
            elif choice == 1:
                # 统计文件
                print("\n请选择要统计的文件夹：")
                for index, option in enumerate(options):
                    print(f"{index + 1}. {option['desc']} ({option['path']})")
                print("0. 返回")
                folder_choice = int(input("请输入选项编号："))
                if folder_choice == 0:
                    continue
                elif 0 < folder_choice <= len(options):
                    selected_option = options[folder_choice - 1]
                    list_files(selected_option["path"], selected_option["type"])
                else:
                    print("无效的选项编号。")

            elif choice == 2:
                # 备份文件
                print("\n请选择要备份的文件夹：")
                for index, option in enumerate(options):
                    print(f"{index + 1}. {option['desc']} ({option['path']})")
                print("0. 返回")

                backup_choice = int(input("请输入选项编号："))
                if backup_choice == 0:
                    continue
                elif 0 < backup_choice <= len(options):
                    selected_option = options[backup_choice - 1]
                    backup_files(selected_option["path"], selected_option["type"], backup_path)
                else:
                    print("无效的选项编号。")
            elif choice == 3:
                #解压文件
                extract_files(backup_path, base_path)

            else:
                print("无效的选项编号。")
        except (ValueError, IndexError):
            print("无效的输入，请输入数字。")
        except Exception as e:
            print(f"发生错误: {e}")

if __name__ == "__main__":
    main()