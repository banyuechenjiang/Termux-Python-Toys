import json
import os
import re
import sys

def is_valid_quickreply_json(file_path):
    """
    # 检查给定的 JSON 文件是否符合 QuickReply 类型的 JSON 文件的基本结构。
    # Args:
        file_path (str): JSON 文件的路径。
    # Returns:
        bool: 如果文件符合基本结构，则返回 True，否则返回 False。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

            # 更严格的结构检查
            if not isinstance(data, dict):
                print(f"# 错误：JSON 根不是字典: {file_path}")
                return False
            if not all(key in data for key in ["version", "name", "qrList"]):
                print(f"# 错误：缺少必要的键 (version, name, qrList): {file_path}")
                return False
            if not isinstance(data["version"], int):
                print(f"# 错误：'version' 不是整数: {file_path}")
                return False
            if not isinstance(data["name"], str):
                 print(f"# 错误：'name' 不是字符串: {file_path}")
                 return False
            if not isinstance(data["qrList"], list):
                print(f"# 错误：'qrList' 不是列表: {file_path}")
                return False
            for item in data["qrList"]:
                if not isinstance(item, dict):
                    print(f"# 错误：'qrList' 中的条目不是字典: {file_path}")
                    return False
                if not all(key in item for key in ["id", "label", "message", "isHidden"]):
                    print(f"# 错误：'qrList' 条目缺少必要的键 (id, label, message, isHidden): {file_path}")
                    return False
                # 可以根据需要添加更多类型检查

            return True
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"# 错误：读取或解析 JSON 失败: {file_path} - {e}")
        return False

def extract_from_json(file_path):
    """
    # 从 QuickReply JSON 文件中提取信息，并创建文件夹和 TXT 文件。

    # Args:
        file_path (str): QuickReply JSON 文件的路径。
    """
    print(f"# 正在处理: {file_path}")  # 调试信息

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"# 错误：文件未找到: {file_path}")
        return
    except json.JSONDecodeError:
        print(f"# 错误：JSON 格式错误: {file_path}")
        return

    name = data.get('name')
    if not name:
        print("# 警告：未找到 'name' 字段，无法创建文件夹。")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    folder_path = os.path.join(script_dir, name)

    if not os.path.exists(folder_path):
        try:
            os.makedirs(folder_path)
        except OSError as e:
            print(f"# 错误：创建文件夹失败 '{folder_path}': {e}")
            return

    qr_list = data.get('qrList', [])
    for qr_item in qr_list:
        label = qr_item.get('label')
        message = qr_item.get('message', '')
        is_hidden = qr_item.get('isHidden', False)

        if not label:
            print("# 警告：跳过没有 'label' 的 qr_item。")
            continue

        safe_label = re.sub(r'[\\/*?:"<>|]', '', label)
        file_name = f"!{safe_label}.txt" if is_hidden else f"{safe_label}.txt"
        file_path = os.path.join(folder_path, file_name)
        print(f"  # 正在创建文件: {file_path}") # 调试信息

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # 写入文件前，将 '\\n' 替换为 '\n'  (如果原始 JSON 中是 \\n)
                f.write(message.replace('\\n', '\n'))
            print(f"  # 成功创建文件: {file_path}")
        except OSError as e:
            print(f"# 错误：创建文件失败 '{file_path}': {e}")

def select_json_file_and_extract():
    """
    # 选择一个 QuickReply JSON 文件并执行提取操作。
    """
    json_files = [f for f in os.listdir('.') if f.endswith('.json')]
    valid_json_files = [f for f in json_files if is_valid_quickreply_json(f)]

    if not valid_json_files:
        print("# 未找到 QuickReply 类型的 JSON 文件。")
        return

    for i, file in enumerate(valid_json_files):
        print(f"{i + 1}. {file}")

    while True:
        try:
            choice = int(input("# 请选择要处理的 QuickReply JSON 文件的编号 (输入0退出): "))
            if choice == 0:
                return
            if 1 <= choice <= len(valid_json_files):
                selected_file = valid_json_files[choice - 1]
                extract_from_json(selected_file)
                break
            else:
                print("# 无效的编号，请重新输入。")
        except ValueError:
            print("# 无效的输入，请输入数字。")

def merge_to_json(directory: str, output_json_path: str):
    """
    # 合并指定目录下所有 txt 文件内容到新的 QuickReply JSON 文件。

    # Args:
       directory (str): 包含 txt 文件的目录。
       output_json_path (str): 输出的 QuickReply JSON 文件的路径。
    """
    print(f"# 正在合并目录: {directory}")

    txt_files = [f for f in os.listdir(directory) if f.endswith(".txt")]
    if not txt_files:
        print(f"# 警告：目录 '{directory}' 中未找到任何 TXT 文件。")
        return

    qr_list = []
    id_counter = 1
    for txt_file in txt_files:
        file_path = os.path.join(directory, txt_file)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                 # 读取时，保留原始换行符 '\n'
                content = f.read()

                is_hidden = txt_file.startswith("!")
                label = txt_file[1:-4] if is_hidden else txt_file[:-4]
                # print(f"label:{label},content:{content}")  # 调试时可以取消注释
                qr_list.append({
                    "id": id_counter,
                    "showLabel": False,
                    "label": label,
                    "title": "",
                    "message": content,  # 直接使用读取的内容，不替换换行符
                    "contextList": [],
                    "preventAutoExecute": True,
                    "isHidden": is_hidden,
                    "executeOnStartup": False,
                    "executeOnUser": False,
                    "executeOnAi": False,
                    "executeOnChatChange": False,
                    "executeOnGroupMemberDraft": False,
                    "executeOnNewChat": False,
                    "automationId": ""
                })
                id_counter += 1
            print(f"# 已读取并添加: {txt_file}")
        except OSError as e:
            print(f"# 错误：读取文件 '{txt_file}' 失败：{e}")
            return

    output_data = {
        "version": 2,
        "name": os.path.basename(directory),
        "disableSend": False,
        "placeBeforeInput": False,
        "injectInput": False,
        "color": "rgba(0, 0, 0, 0)",
        "onlyBorderColor": False,
        "qrList": qr_list,
        "idIndex": id_counter
    }

    try:
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False)  # 移除 indent=2
        print(f"# 成功创建新的 QuickReply JSON 文件: {output_json_path}")
    except OSError as e:
        print(f"# 错误：创建 JSON 文件 '{output_json_path}' 失败: {e}")

def get_quickreply_json_files():
    """# 获取当前目录下所有符合 QuickReply 结构的 JSON 文件"""
    all_json_files = [f for f in os.listdir('.') if f.endswith('.json')]
    quickreply_json_files = [f for f in all_json_files if is_valid_quickreply_json(f)]
    return quickreply_json_files

def push_to_json(qr_json_path: str, directory: str):
    """
    # 从指定目录下的 TXT 文件更新 QuickReply JSON 文件中的 message 字段。

    # Args:
        qr_json_path (str): 要更新的 QuickReply JSON 文件的路径。
        directory (str): 包含 TXT 文件的目录。
    """
    print(f"# 正在推送更新到: {qr_json_path}，使用目录: {directory}")

    try:
        with open(qr_json_path, 'r', encoding='utf-8') as f:
            qr_data = json.load(f)
    except FileNotFoundError:
        print(f"# 错误：QuickReply JSON 文件未找到: {qr_json_path}")
        return
    except json.JSONDecodeError:
        print(f"# 错误：QuickReply JSON 文件 JSON 格式错误: {qr_json_path}")
        return

    file_contents = {}
    for filename in os.listdir(directory):
        if filename.endswith(".txt"):
            filepath = os.path.join(directory, filename)
            label = filename[:-4]
            if label.startswith("!"):
                label = label[1:]
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    # 读取 TXT 文件时，保留原始换行符
                    file_contents[label] = f.read()

            except OSError as e:
                print(f"# 错误：读取文件 '{filepath}' 失败: {e}")
                return

    updated_count = 0
    for qr_item in qr_data.get("qrList", []):
        label = qr_item.get("label")
        if label in file_contents:
            qr_item["message"] = file_contents[label]  # 更新 message，保留原始换行符
            updated_count += 1
            print(f"# 更新了 '{label}' 的 message")

    try:
        with open(qr_json_path, "w", encoding="utf-8") as f:
            json.dump(qr_data, f, ensure_ascii=False)  # 移除 indent=2
        print(f"# 成功更新 QuickReply JSON 文件: {qr_json_path}，更新了 {updated_count} 个条目")
    except OSError as e:
        print(f"# 错误：写入 QuickReply JSON 文件 '{qr_json_path}' 失败: {e}")

def get_valid_folders():
    """
    # 获取当前目录下的有效文件夹列表。这些文件夹包含 TXT 文件。

    # Returns:
        list: 有效文件夹列表。
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    folders = [d for d in os.listdir(script_dir) if os.path.isdir(os.path.join(script_dir, d))]

    valid_folders = []
    for folder in folders:
        folder_path = os.path.join(script_dir, folder)
        if any(f.endswith(".txt") for f in os.listdir(folder_path)):
            valid_folders.append(folder)
    return valid_folders

def main():
    """# 主函数，提供交互式菜单"""
    while True:
        print("\n# 请选择操作:")
        print("# 1. 提取 (从 QuickReply JSON 提取到文件)")
        print("# 2. 合并 (从文件合并到新的 QuickReply JSON)")
        print("# 3. 推送 (从文件更新 QuickReply JSON)")
        print("# 0. 退出")

        choice = input("# 请输入选项 (0-3): ")

        if choice == "1":
            select_json_file_and_extract()
        elif choice == "2":
            valid_folders = get_valid_folders()
            if not valid_folders:
                print("# 当前目录下没有包含 TXT 文件的文件夹。")
                continue

            print("# 请选择一个文件夹进行合并：")
            for i, folder in enumerate(valid_folders):
                print(f"{i + 1}. {folder}")

            while True:
                try:
                    choice = int(input("# 请输入文件夹编号 (输入0返回): "))
                    if choice == 0:
                        break
                    if 1 <= choice <= len(valid_folders):
                        directory = valid_folders[choice - 1]
                        break
                    else:
                        print("# 无效的编号，请重新输入。")
                except ValueError:
                    print("# 无效的输入，请输入数字。")

            if choice == 0:
                continue

            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_json_name = f"QuickReply-{os.path.basename(directory)}.json"
            output_json_path = os.path.join(script_dir, output_json_name)
            merge_to_json(directory, output_json_path)

        elif choice == "3":
            qr_json_files = get_quickreply_json_files()
            if not qr_json_files:
                print("# 未找到 QuickReply JSON 文件，请先使用提取操作。")
                continue

            for i, file in enumerate(qr_json_files):
                print(f"{i + 1}. {file}")

            while True:
                try:
                    choice = int(input("# 请选择要更新的 QuickReply JSON 文件的编号 (输入0退出): "))
                    if choice == 0:
                        break
                    if 1 <= choice <= len(qr_json_files):
                        selected_qr_json = qr_json_files[choice - 1]
                        break
                    else:
                        print("# 无效的编号，请重新输入。")
                except ValueError:
                    print("# 无效的输入，请输入数字。")
            if choice == 0:
                continue

            valid_folders = get_valid_folders()
            if not valid_folders:
                print("# 当前目录下没有包含TXT文件的文件夹")
                continue

            print("# 请选择一个文件夹来更新 QuickReply JSON：")
            for i, folder in enumerate(valid_folders):
                print(f"{i + 1}. {folder}")
            while True:
                try:
                    choice_folder = int(input("# 请输入文件夹编号 (输入0返回): "))
                    if choice_folder == 0:
                        break
                    if 1 <= choice_folder <= len(valid_folders):
                        directory = valid_folders[choice_folder - 1]
                        break
                    else:
                        print("# 无效的编号，请重新输入")
                except ValueError:
                    print("# 无效的输入，请输入数字。")

            if choice_folder == 0:
                continue

            push_to_json(selected_qr_json, directory)

        elif choice == "0":
            print("# 退出程序。")
            break
        else:
            print("# 无效的选项，请重新输入。")

if __name__ == "__main__":
    main()