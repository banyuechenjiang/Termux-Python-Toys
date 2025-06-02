import base64
import zlib
from PIL import Image
import sys
sys.path.append('/data/data/com.termux/files/usr/lib/python3.12/site-packages')
import png
import json

def read_png_metadata(png_file_path):
    """
    读取 PNG 文件中的元数据信息，并返回关键字为 "chara" 的文本内容。

    Args:
        png_file_path: PNG 文件路径。

    Returns:
        如果找到关键字为 "chara" 的文本内容，则返回其解码后的字符串；否则返回 None。
    """

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
        print(f"读取 PNG 文件 {png_file_path} 失败：{e}")
        return None


def print_metadata_info(data, png_file):
    """
    打印提取到的元数据信息，如果某些字段为空，则打印相应的提示信息。

    Args:
        data: 解析后的 JSON 元数据对象。
        png_file: PNG 文件名。
    """
    print(f"文件 {png_file} 的信息：")

    name = data.get("name")
    print(f"  角色名称：{name or '未找到'}")

    creator_notes = data.get("creator_notes") or data.get("creatorcomment")  # 兼容 v1 和 v2 数据结构
    print(f"  创建者注释：{creator_notes or '未找到'}")

    tags = data.get("tags")
    print(f"  标签：{', '.join(tags) if tags else '未找到'}")

    creator = data.get("creator") or data.get("create_by")  # 兼容 v1 和 v2 数据结构
    print(f"  创建者：{creator or '未找到'}")

    script_names = [script.get("scriptName") for script in data.get("extensions", {}).get("regex_scripts", []) if script.get("scriptName")]
    print(f"  脚本名称：{', '.join(script_names) if script_names else '未找到'}")

    character_book = data.get("character_book") or data.get("data", {}).get("character_book")  # 兼容 v1 和 v2 数据结构
    if character_book:
        character_book_name = character_book.get("name")
        if character_book_name:
            print(f"  世界信息书名称：{character_book_name}")
        else:
            entries = character_book.get("entries")
            if entries:
                print(f"  世界信息书条目：")
                for entry in entries:
                    keys = entry.get("keys")
                    comment = entry.get("comment")
                    print(f"    关键字：{', '.join(keys) if keys else '未找到'}")
                    print(f"    注释：{comment or '未找到'}")


if __name__ == "__main__":
    import os

    # 获取当前目录下所有 PNG 文件
    png_files = [f for f in os.listdir('.') if f.endswith('.png')]

    # 遍历 PNG 文件并打印元数据信息
    for png_file in png_files:
        metadata = read_png_metadata(png_file)
        if metadata:
            try:
                # 将元数据解析为 JSON 对象
                data = json.loads(metadata)
                print_metadata_info(data, png_file)

            except json.JSONDecodeError:
                print(f"文件 {png_file} 的元数据不是有效的 JSON 格式。")

        else:
            print(f"文件 {png_file} 中未找到关键字为 'chara' 的元数据信息。")