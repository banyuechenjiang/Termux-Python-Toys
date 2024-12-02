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


def sanitize_filename(filename):
    """将文件名中的非法字符替换为下划线。"""
    return re.sub(r'[\\/:*?"<>|]', '_', filename)


def rename_png_files_recursive(directory):
    """递归地重命名指定目录及其子目录中符合角色卡结构的 PNG 文件。"""

    renamed_files = collections.defaultdict(dict)  # 使用字典存储重命名信息
    i = 0  # 用于生成唯一的文件名

    for root, _, files in os.walk(directory):
        count = 0  # 初始化每个路径的计数器
        for file in files:
            if file.endswith(".png"):
                png_file_path = os.path.join(root, file)
                metadata = read_png_metadata(png_file_path)

                # 检查 metadata 是否存在且是有效的 JSON 格式
                if metadata:
                    try:
                        data = json.loads(metadata)

                        # 提取角色卡名称，优先使用 name 字段，如果不存在则使用 displayName 字段
                        name_value = sanitize_filename(data.get("name") or data.get("displayName", ""))

                        # 提取第一个标签作为标签值, 处理 tags 列表为空的情况
                        tags_value = sanitize_filename(data.get("tags", [""])[0]) if data.get("tags") else ""

                        # 提取创建者信息，优先使用 creator 字段，如果不存在则使用 createBy 字段
                        creator_value = sanitize_filename(data.get("creator") or data.get("createBy", ""))

                        # 使用 if-else 语句构建文件名
                        new_filename_parts = ["卡"]
                        if tags_value:
                            new_filename_parts.append(tags_value)
                        if name_value:
                            new_filename_parts.append(name_value)
                        if creator_value:
                            new_filename_parts.append(creator_value)

                        file_size_kb = os.path.getsize(png_file_path) // 1024
                        new_filename_parts.append(str(file_size_kb) + "KB")
                        new_filename_parts.append(str(i))

                        new_filename = "-".join(new_filename_parts) + ".png"
                        new_filepath = os.path.join(root, new_filename)

                        os.rename(png_file_path, new_filepath)
                        # 获取相对路径
                        relative_old_path = os.path.relpath(png_file_path, directory)
                        relative_new_path = os.path.relpath(new_filepath, directory)

                        # 将重命名信息存储到字典中, 只存储文件名
                        renamed_files[os.path.relpath(root, directory)][os.path.basename(relative_old_path)] = os.path.basename(relative_new_path)

                        i += 1
                        count += 1  # 增加计数器

                    except json.JSONDecodeError:
                        print(f"文件 {os.path.relpath(png_file_path, directory)} 的元数据不是有效的 JSON 格式。")

        # 更新路径后的计数
        if count > 0:
            renamed_files[os.path.relpath(root, directory)]["count"] = count

    # 打印类似 YAML 的输出
    for path, items in renamed_files.items():
        if items.get('count', 0) > 0:  # 忽略没有重命名文件的路径
            print(f"{path}: ({items.get('count', 0)})")  # 打印路径和计数
            for old_name, new_name in items.items():
                if old_name != "count":
                    print(f"  - {old_name} -> {new_name}")  # 打印重命名信息


if __name__ == "__main__":
    download_path = os.path.expanduser("~/storage/shared/Download") 
    rename_png_files_recursive(download_path)