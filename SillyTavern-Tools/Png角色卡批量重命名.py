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

def read_png_metadata(png_file_path):
    """读取 PNG 文件中的元数据信息，并返回关键字为 "chara" 的文本内容。"""
    try:
        with open(png_file_path, 'rb') as f:
            reader = png.Reader(file=f)
            chunks = list(reader.chunks())  # 读取所有数据块

            for chunk_type, chunk_data in chunks:
                if chunk_type == b'tEXt':
                    keyword, text = chunk_data.split(b'\x00', 1)
                    if keyword.lower() == b'chara':
                        # 使用 zlib 解压缩文本内容（如果已压缩）
                        try:
                            text = zlib.decompress(text)
                        except zlib.error:
                            pass  # 文本内容未压缩
                        return base64.b64decode(text).decode('utf-8')
    except Exception as e:
        # 忽略不是 PNG 文件的错误
        if not isinstance(e, png.FormatError):
            print(f"读取 PNG 文件 {png_file_path} 失败：{e}")
        return None

_illegal_chars_pattern = re.compile(r'[\\/:*?"<>|]')

def sanitize_filename(filename):
    """将文件名中的非法字符替换为下划线。"""
    return _illegal_chars_pattern.sub('_', filename)

def rename_png_files_recursive(directory):
    """递归地重命名指定目录及其子目录中符合角色卡结构的 PNG 文件。"""

    renamed_files = collections.defaultdict(dict)  # 用于存储按目录的重命名信息
    i = 0  # 用于生成唯一的文件名

    for root, _, files in os.walk(directory):
        count = 0  # 初始化每个路径的计数器
        renamed_in_path = {} # 存储当前路径下的重命名信息
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

                        new_filename_parts = ["卡"]
                        if tags_value:
                            new_filename_parts.append(tags_value)
                        if name_value:
                            new_filename_parts.append(name_value)
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

                        # 存储到按目录的字典
                        relative_root = os.path.relpath(root, directory)
                        renamed_in_path[old_filename] = new_filename_base

                        i += 1
                        count += 1

                    except json.JSONDecodeError:
                        print(f"文件 {os.path.relpath(png_file_path, directory)} 的元数据不是有效的 JSON 格式。")

        if renamed_in_path:
            renamed_files[os.path.relpath(root, directory)] = renamed_in_path
            renamed_files[os.path.relpath(root, directory)]["count"] = count

    # 打印按目录的重命名信息并准备剪贴板内容
    clipboard_string = ""
    for path, items in renamed_files.items():
        if items.get('count', 0) > 0:
            print(f"{path}: ({items.get('count', 0)})")
            clipboard_string += f"{path}: ({items.get('count', 0)})\n"
            for old_name, new_name in items.items():
                if old_name != "count":
                    print(f"  - {old_name} -> {new_name}")
                    clipboard_string += f"  - {old_name} -> {new_name}\n"

    # 写入剪贴板
    if clipboard_string:
        try:
            process = subprocess.Popen(['termux-clipboard-set'], stdin=subprocess.PIPE, text=True)
            process.communicate(clipboard_string)
            print("\n重命名信息已复制到剪贴板。")
        except FileNotFoundError:
            print("\ntermux-clipboard-set 命令未找到，请确保已安装 Termux API。")

if __name__ == "__main__":
    download_path = os.path.expanduser("~/storage/shared/Download")
    rename_png_files_recursive(download_path)