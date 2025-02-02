import base64
import zlib
from PIL import Image
import sys
import png
import json
import os
import re
import collections

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

def sanitize_filename(filename):
    """将文件名中的非法字符替换为下划线，保留空格。"""
    return re.sub(r'[\\/:*?"<>|\r\n]', '_', filename)

def rename_png_files_recursive(directory, reset_counter=False):
    """递归地重命名指定目录及其子目录中符合角色卡结构的 PNG 文件。"""

    renamed_files = collections.defaultdict(dict)
    duplicate_charas = collections.defaultdict(lambda: collections.defaultdict(list))
    name_value_counts = collections.defaultdict(int)

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
                        new_filename_parts.append(f"[{tags_value}]")
                    if name_value:
                        new_filename_parts.append(name_value)
                        if suffix:
                            new_filename_parts.append(suffix)
                    if creator_value:
                        new_filename_parts.append(f"({creator_value})") # 创建者用 () 包裹

                    file_size_kb = os.path.getsize(png_file_path) // 1024
                    new_filename_parts.append(f"{file_size_kb}KB")
                    new_filename_parts.append(str(i))  # 保持原有结构

                    new_filename = "-".join(new_filename_parts) + ".png" # 使用单个 - 连接
                    new_filepath = os.path.join(root, new_filename)

                    old_filename = os.path.basename(png_file_path)
                    new_filename_base = os.path.basename(new_filepath)

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
    print("请选择操作路径:")
    print("1. 下载 (Downloads)")
    print("2. 文档 (Documents) - SillyTavern Characters")

    while True:
        choice = input("请选择 (1 或 2): ")
        if choice in ('1', '2'):
            break
        else:
            print("无效的选择，请重新输入。")

    if choice == '1':
        download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        print(f"\n处理路径: {download_path}")
        rename_png_files_recursive(download_path)

    elif choice == '2':
        documents_path = os.path.join(os.path.expanduser("~"), "Documents")
        print(f"\n在文档 (Documents) 目录下查找 SillyTavern 文件夹...")

        for root, dirs, _ in os.walk(documents_path):
            for dir_name in dirs:
                if dir_name == "SillyTavern":
                    sillytavern_dir_path = os.path.join(root, dir_name)
                    characters_path = os.path.join(sillytavern_dir_path, "data", "default-user", "characters")
                    if os.path.isdir(characters_path):
                        print(f"\n处理 SillyTavern Characters 路径: {characters_path}")
                        rename_png_files_recursive(characters_path, reset_counter=True)
                    else:
                        print(f"警告: 路径 {characters_path} 不存在。跳过。")

if __name__ == "__main__":
    main()