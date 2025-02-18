import os
import json
import re

def rename_qr_files(directory):
    """
    重命名目录中符合 Quick Reply 结构的 JSON 文件，
    使用 "QuickReply-{name}" 作为新文件名（不考虑原始文件名）。

    Args:
        directory: 要处理的目录。
    """

    qr_keys = ["version", "name", "qrList"]
    count = 0

    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith(".json"):
                filepath = os.path.join(root, filename)

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    if all(key in data for key in qr_keys):
                        base, ext = os.path.splitext(filename)
                        name_value = data.get("name", "")

                        new_filename = f"QuickReply-{name_value}{ext}"  # 直接使用 "QuickReply-{name}" 作为新文件名
                        new_filepath = os.path.join(root, new_filename)

                        i = 1
                        while os.path.exists(new_filepath):  # 处理文件名冲突
                            new_filename = f"QuickReply-{name_value}_{i}{ext}"  # 添加数字后缀
                            new_filepath = os.path.join(root, new_filename)
                            i += 1

                        os.rename(filepath, new_filepath)
                        count += 1
                        print(f"已重命名: {filename} -> {new_filename}")

                except json.JSONDecodeError as e:
                    print(f"错误：文件 '{filename}' 不是有效的 JSON: {e}")
                except OSError as e:
                    print(f"错误：访问文件 '{filename}' 时出错: {e}")


    print(f"\n共处理了 {count} 个 Quick Reply JSON 文件。")




if __name__ == "__main__":
    download_path = os.path.expanduser("~/storage/shared/Download/Json文件")
    rename_qr_files(download_path)