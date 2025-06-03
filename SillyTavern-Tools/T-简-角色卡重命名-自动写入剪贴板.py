import base64
import zlib
from PIL import Image
import sys
sys.path.append('/data/data/com.termux/files/usr/lib/python3.12/site-packages')
import png
import json
import os
import re
import collections
import subprocess
import time

def read_png_metadata(png_file_path):
    """读取 PNG 文件中的元数据信息，并返回关键字为 "chara" 的文本内容。"""
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

_illegal_chars_pattern = re.compile(r'[\\/:*?"<>|]')

def sanitize_filename(filename):
    """将文件名中的非法字符替换为下划线。"""
    return _illegal_chars_pattern.sub('_', filename)

def rename_png_files_recursive(directory):
    """递归地重命名指定目录及其子目录中符合角色卡结构的 PNG 文件。"""
    renamed_files = collections.defaultdict(dict)
    i = 0
    clipboard_string = ""
    duplicate_charas = collections.defaultdict(lambda: collections.defaultdict(list)) # 用于存储重复角色卡，按角色名和路径分组
    name_value_counts = collections.defaultdict(int)
    clipboard_duplicate_string = "" # 用于存储重复卡信息的剪贴板字符串

    for root, _, files in os.walk(directory):
        count = 0
        renamed_in_path = {}
        for file in files:
            if file.endswith(".png"):
                png_file_path = os.path.join(root, file)
                metadata = read_png_metadata(png_file_path)

                if metadata:
                    try:
                        data = json.loads(metadata)
                        name_value = sanitize_filename(data.get("name") or data.get("displayName", ""))
                        tags_value = sanitize_filename(data.get("tags", [""])[0]) if data.get("tags") else ""
                        creator_value = sanitize_filename(data.get("creator") or data.get("createBy", ""))

                        name_value_counts[name_value] += 1
                        suffix = ""
                        if name_value_counts[name_value] > 1:
                            suffix = f"-{name_value_counts[name_value] - 1}"

                        new_filename_parts = ["卡"]
                        if tags_value:
                            new_filename_parts.append(tags_value)
                        if name_value:
                            new_filename_parts.append(name_value)
                            if suffix:
                                new_filename_parts.append(suffix)
                        if creator_value:
                            new_filename_parts.append(creator_value)

                        file_size_kb = os.path.getsize(png_file_path) // 1024
                        new_filename_parts.append(f"{file_size_kb}KB")
                        new_filename_parts.append(str(i))

                        new_filename = "-".join(new_filename_parts) + ".png"
                        new_filepath = os.path.join(root, new_filename)

                        old_filename = os.path.basename(png_file_path)
                        new_filename_base = os.path.basename(new_filepath)

                        os.rename(png_file_path, new_filepath)

                        relative_root = os.path.relpath(root, directory)
                        renamed_in_path[old_filename] = new_filename_base

                        if name_value:
                            duplicate_charas[name_value][root].append(new_filename_base) #  按角色名和路径存储重复文件名，重复判断基于 name_value

                        i += 1
                        count += 1

                    except json.JSONDecodeError:
                        print(f"文件 {os.path.relpath(png_file_path, directory)} 的元数据不是有效的 JSON 格式。")
        if count > 0:
            print(f"{os.path.relpath(root, directory)}: ({count})")
            clipboard_string += f"{os.path.relpath(root, directory)}: ({count})\n"
            for old_filename, new_filename_base in renamed_in_path.items():
                print(f"  - {old_filename} -> {new_filename_base}")
                clipboard_string += f"  - {old_filename} -> {new_filename_base}\n"


            renamed_files[os.path.relpath(root, directory)] = renamed_in_path
            renamed_files[os.path.relpath(root, directory)]["count"] = count
            renamed_files[os.path.relpath(root, directory)]["clipboard_string_path"] = f"{os.path.relpath(root, directory)}: ({count})\n"

    has_duplicates = False
    print("\n" + "-" * 30 + "\n" + "-" * 30 + "\n" + "-" * 30)
    time.sleep(2)
    print("重复的角色卡:")
    if duplicate_charas:
        for name, path_dict in duplicate_charas.items(): # 遍历角色名和路径字典
            if len(path_dict) > 1 or sum(len(files) for files in path_dict.values()) > 1: # 检查是否有重复文件
                has_duplicates = True
                print(f"{name}：")
                clipboard_duplicate_string += f"{name}：\n"
                for root, filenames in path_dict.items(): # 遍历路径和文件名列表
                    relative_path = os.path.relpath(root, os.path.expanduser("~/storage/shared/Download"))
                    print(f"　路径：{relative_path}")
                    clipboard_duplicate_string += f"　路径：{relative_path}\n"
                    for filename in filenames: # 遍历文件名列表
                        print(f"　　－　{filename}")
                        clipboard_duplicate_string += f"　　－　{filename}\n"

    if not has_duplicates:
        print("  无")
        clipboard_duplicate_string += "  无\n"

    if clipboard_duplicate_string:
        try:
            process = subprocess.Popen(['termux-clipboard-set'], stdin=subprocess.PIPE, text=True)
            process.communicate(clipboard_duplicate_string)
            print("\n重复角色卡信息已复制到剪贴板。")
        except FileNotFoundError:
            print("\ntermux-clipboard-set 命令未找到，请确保已安装 Termux API。")

    if clipboard_string:
        try:
            process = subprocess.Popen(['termux-clipboard-set'], stdin=subprocess.PIPE, text=True)
            process.communicate(clipboard_string)
            print("\n完整的重命名信息已复制到剪贴板。")
        except FileNotFoundError:
            print("\ntermux-clipboard-set 命令未找到，请确保已安装 Termux API。")


if __name__ == "__main__":
    download_path = os.path.expanduser("~/storage/shared/Download")
    rename_png_files_recursive(download_path)