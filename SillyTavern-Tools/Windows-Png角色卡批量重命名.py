import base64
import zlib
import sys
import png
import json
import os
import re
import collections
import tkinter as tk
from tkinter import filedialog
import time


def read_png_metadata(png_file_path):
    """读取 PNG 文件中的元数据，返回 "chara" 关键字的文本内容。"""
    try:
        with open(png_file_path, 'rb') as f:
            reader = png.Reader(file=f)
            chunks = list(reader.chunks())

            for chunk_type, chunk_data in chunks:
                if chunk_type == b'tEXt':
                    keyword, text = chunk_data.split(b'\x00', 1)
                    if keyword.lower() == b'chara':
                        try:
                            text = zlib.decompress(text)
                        except zlib.error:
                            pass
                        return base64.b64decode(text).decode('utf-8')
    except Exception as e:
        if not isinstance(e, png.FormatError):
            print(f"读取 PNG 文件 {png_file_path} 失败：{e}")
        return None


def sanitize_filename(filename):
    """将文件名中的非法字符替换为下划线，保留空格。"""
    return re.sub(r'[\\/:*?"<>|\r\n]', '_', filename)


def rename_png_files_recursive(directory, reset_counter=False):
    """
    递归地重命名指定目录及其子目录中符合角色卡结构的 PNG 文件。
    结合了两个脚本的功能，用于比较重复，并简化命名。
    """

    renamed_files = collections.defaultdict(dict)
    duplicate_charas = collections.defaultdict(lambda: collections.defaultdict(list))
    name_value_counts = collections.defaultdict(int)
    processed_files = set()  # 用于跟踪已处理的文件，防止重复处理

    # 根据 reset_counter 参数决定是否重置计数器
    if reset_counter:
        i = 0
    else:
        i = 0  # 如果不重置，则保持 i 的值

    for root, _, files in os.walk(directory):
        count = 0
        renamed_in_path = {}
        for file in files:
            if file.endswith(".png"):
                png_file_path = os.path.join(root, file)

                # 检查文件是否已经被处理过
                if png_file_path in processed_files:
                    continue
                processed_files.add(png_file_path)

                metadata = read_png_metadata(png_file_path)

                if metadata is not None:  # 确保 metadata 被成功赋值
                    try:
                        data = json.loads(metadata)
                        name_value = sanitize_filename(data.get("name") or data.get("displayName", ""))
                        tags_value = sanitize_filename(data.get("tags", [""])[0]) if data.get("tags") else ""  # 仍然读取
                        creator_value = sanitize_filename(data.get("creator") or data.get("createBy", ""))  # 仍然读取

                        name_value_counts[name_value] += 1
                        suffix = ""
                        if name_value_counts[name_value] > 1:
                            suffix = f"-{name_value_counts[name_value] - 1}"

                        # 简化文件名：只包含 name, 计数器(如果有), 文件大小, 和 i
                        file_size_kb = os.path.getsize(png_file_path) // 1024
                        new_filename_parts = []
                        if name_value:
                            new_filename_parts.append(name_value)
                        if suffix:
                            new_filename_parts.append(suffix)

                        new_filename_parts.append(f"{file_size_kb}KB")
                        new_filename_parts.append(str(i))

                        new_filename = "-".join(new_filename_parts) + ".png"
                        new_filepath = os.path.join(root, new_filename)

                        old_filename = os.path.basename(png_file_path)
                        new_filename_base = os.path.basename(new_filepath)

                        # 重命名警告（只在处理 SillyTavern 目录时显示）
                        if "SillyTavern" in root and "characters" in root.lower():
                            print(f"警告：正在重命名 SillyTavern 角色卡文件：{old_filename} -> {new_filename_base}")
                            print("这可能会影响到基于角色卡名称命名的 SillyTavern 聊天记录文件夹，导致聊天记录文件夹与角色卡失去关联。")

                        os.rename(png_file_path, new_filepath)

                        relative_root = os.path.relpath(root, directory)
                        renamed_in_path[old_filename] = new_filename_base

                        if name_value:
                            duplicate_charas[name_value][root].append(new_filename_base)

                        i += 1
                        count += 1

                    except json.JSONDecodeError:
                        print(f"文件 {os.path.relpath(png_file_path, directory)} 的元数据不是有效的 JSON 格式。")
        if count > 0:
            print(f"{os.path.relpath(root, directory)}: ({count})")
            for old_filename, new_filename_base in renamed_in_path.items():
                print(f"  - {old_filename} -> {new_filename_base}")

            renamed_files[os.path.relpath(root, directory)] = renamed_in_path
            renamed_files[os.path.relpath(root, directory)]["count"] = count
            renamed_files[os.path.relpath(root, directory)]["clipboard_string_path"] = f"{os.path.relpath(root, directory)}: ({count})\n"

    has_duplicates = False
    print("\n" + "-" * 30 + "\n" + "-" * 30 + "\n" + "-" * 30)
    print("重复的角色卡:")
    if duplicate_charas:
        for name, path_dict in duplicate_charas.items():
            if len(path_dict) > 1 or sum(len(files) for files in path_dict.values()) > 1:
                has_duplicates = True
                print(f"{name}：")
                for root, filenames in path_dict.items():
                    relative_path = os.path.relpath(root, directory)
                    print(f"　路径：{relative_path}")
                    for filename in filenames:
                        print(f"　　－　{filename}")

    if not has_duplicates:
        print("  无")

    print("\n重命名完成，详细信息请查看终端输出。")

    return i  # 返回计数器的值



def main():
    """主函数，处理用户交互和目录选择。"""
    while True:
        print("请选择操作：")
        print("1. 处理脚本所在文件夹")
        print("2. 选择文件夹")
        print("0. 退出")

        choice = input("请选择 (1, 2, 或 0): ").strip()

        if choice == '1':
            directory = os.path.dirname(os.path.abspath(__file__))
            print(f"处理脚本所在文件夹: {directory}")
            # 增加 SillyTavern 路径的特殊处理 (在选择目录后)
            if "SillyTavern" in directory.lower() and "characters" in directory.lower():
                print("\n警告: 正在处理 SillyTavern 角色卡文件夹。")
                print("重命名角色卡文件可能会影响到基于角色卡名称命名的 SillyTavern 聊天记录文件夹。")
                confirmation = input("是否继续重命名 SillyTavern 角色卡? (yes/no): ").lower()
                if confirmation != 'yes':
                    print("操作已取消。")
                    continue  # 回到循环开始
                rename_png_files_recursive(directory, reset_counter=True)  # SillyTavern 目录重置计数器
            else:
                rename_png_files_recursive(directory)


        elif choice == '2':
            directory = filedialog.askdirectory(title="选择包含 PNG 文件的文件夹")
            if directory:  # 确保用户选择了文件夹
                print(f"处理文件夹: {directory}")
                # 增加 SillyTavern 路径的特殊处理 (在选择目录后)
                if "SillyTavern" in directory.lower() and "characters" in directory.lower():
                    print("\n警告: 正在处理 SillyTavern 角色卡文件夹。")
                    print("重命名角色卡文件可能会影响到基于角色卡名称命名的 SillyTavern 聊天记录文件夹。")
                    confirmation = input("是否继续重命名 SillyTavern 角色卡? (yes/no): ").lower()
                    if confirmation != 'yes':
                        print("操作已取消。")
                        continue #回到循环开始
                    rename_png_files_recursive(directory, reset_counter=True)  # SillyTavern 目录重置计数器

                else: # 非SillyTavern目录
                    rename_png_files_recursive(directory)
            else:
                print("未选择文件夹。")  # 用户取消了选择

        elif choice == '0':
            print("退出程序。")
            break  # 退出循环

        else:
            print("无效的选项。")


if __name__ == "__main__":
    main()