import os
import json
import shutil
import re
import collections

def classify_json_files(download_path):
    """
    根据用户选择的功能，分类并移动 JSON 文件到指定目录。

    Args:
        download_path: 要处理的根目录。
    """

    while True:
        print("\n请选择要执行的操作：")
        print("1. 移动预设 JSON 文件")
        print("2. 移动正则 JSON 文件")
        print("3. 移动 Quick Reply JSON 文件")
        print("4. 移动世界书 JSON 文件")
        print("0. 退出")

        choice = input("请输入选项编号: ")

        if choice == "1":
            move_preset_files(download_path)
        elif choice == "2":
            move_regex_files(download_path)
        elif choice == "3":
            move_quick_reply_files(download_path)
        elif choice == "4":
            move_world_book_files(download_path)
        elif choice == "0":
            print("程序已退出。")
            break
        else:
            print("无效的选项，请重新输入。")

def move_preset_files(download_path):
    """
    根据预设结构将 JSON 文件分类并移动到指定目录。
    只要有两个及以上的匹配键就进行移动。
    不进行重命名操作。
    """

    preset_dir = os.path.join(download_path, "Json文件", "预设")
    move_files(download_path, preset_dir, "预设", ["custom_url", "openai_model", "custom_model", "assistant_prefill",
                                                  "human_sysprompt_message", "continue_postfix", "function_calling", "seed", "n"], 2)

def move_regex_files(download_path):
    """
    根据正则表达式结构将 JSON 文件分类并移动到指定目录。
    如果所有key都存在就移动。
    不进行重命名操作。
    """

    regex_dir = os.path.join(download_path, "Json文件", "正则")
    move_files(download_path, regex_dir, "正则", ["scriptName", "findRegex", "replaceString"], 3)

def move_quick_reply_files(download_path):
    """
    根据 Quick Reply 结构将 JSON 文件分类并移动到指定目录。
    如果所有key都存在就移动。
    不进行重命名操作。
    """

    quick_reply_dir = os.path.join(download_path, "Json文件", "QuickReply")
    move_files(download_path, quick_reply_dir, "Quick Reply", ["version", "name", "qrList"], 3)

def move_world_book_files(download_path):
    """
    根据世界书结构将 JSON 文件分类并移动到指定目录。
    不进行重命名操作。
    """

    world_book_dir = os.path.join(download_path, "Json文件", "世界书")
    move_files(download_path, world_book_dir, "世界书", ["entries"], 1, is_world_book)

def is_world_book(data):
    """
    判断一个 JSON 数据是否符合世界书结构。

    Args:
        data: JSON 数据。

    Returns:
        如果符合世界书结构，返回 True；否则返回 False。
    """
    try:
        return "entries" in data and "0" in data["entries"] and isinstance(data["entries"]["0"], dict)
    except (KeyError, TypeError):
        return False

def move_files(download_path, target_dir, file_type, matching_keys, required_matches, custom_check=None):
    """
    根据匹配键将 JSON 文件分类并移动到指定目录。
    不进行重命名操作。

    Args:
        download_path: 要处理的根目录。
        target_dir: 目标目录的路径。
        file_type: 文件类型 ("预设", "正则", "Quick Reply" 或 "世界书")。
        matching_keys: 用于匹配的键列表。
        required_matches: 至少需要的匹配键数量。
        custom_check: 可选，用于进行自定义检查的函数。
    """

    os.makedirs(target_dir, exist_ok=True)  # 确保目标目录存在

    count = 0
    processed_files = set()  # 用于跟踪已处理的文件，避免重复处理

    target_dir_abs = os.path.abspath(target_dir)  # 获取目标目录的绝对路径

    for root, _, files in os.walk(download_path):
        root_abs = os.path.abspath(root)

        # 避免处理目标文件夹本身及其子文件夹
        if root_abs == target_dir_abs or root_abs.startswith(target_dir_abs + os.sep):
            continue

        for filename in files:
            if filename.endswith(".json"):
                filepath = os.path.join(root, filename)

                # 避免重复处理
                if filepath in processed_files:
                    continue

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    matched_count = sum(1 for key in matching_keys if key in data)

                    # 如果提供了自定义检查函数，则使用自定义检查函数
                    if custom_check:
                        is_valid = custom_check(data)
                    else:
                        is_valid = matched_count >= required_matches

                    if is_valid:
                        # 构建新文件路径(不重命名)
                        new_filepath = os.path.join(target_dir, filename)

                        if os.path.exists(new_filepath):
                            print(f"目标文件已存在，跳过: {filename}")
                            continue

                        shutil.move(filepath, new_filepath)
                        count += 1
                        processed_files.add(new_filepath)  # 将新路径添加到已处理集合中
                        print(f"已移动: {filename} -> {new_filepath}")

                except (json.JSONDecodeError, OSError, KeyError) as e:
                    print(f"错误：处理文件 '{filename}' 时出错: {e}")

    print(f"\n共处理了 {count} 个{file_type} JSON 文件。")

if __name__ == "__main__":
    download_path = os.path.expanduser("~/storage/shared/Download")
    classify_json_files(download_path)