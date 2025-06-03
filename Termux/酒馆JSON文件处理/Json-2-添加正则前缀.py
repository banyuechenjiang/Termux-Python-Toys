import os
import json
import re

def rename_regex_files(directory):
    """
    新增非法字符处理
    
    重命名目录中符合正则表达式结构的 JSON 文件，
    使用 "正则-{scriptName}_{fileSizeKB}KB" 作为新文件名。

    Args:
        directory: 要处理的目录。
    """

    regex_keys = ["scriptName", "findRegex", "replaceString"]
    count = 0

    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith(".json"):
                filepath = os.path.join(root, filename)

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    if all(key in data for key in regex_keys):
                        script_name = data.get("scriptName", "")
                        file_size_kb = os.path.getsize(filepath) // 1024

                        # 去除 scriptName 中的非法字符
                        script_name = re.sub(r'[\\/*?:"<>|]', "", script_name)  

                        #  "正则-{scriptName}_{fileSizeKB}KB"  格式
                        new_filename = f"正则-{script_name}_{file_size_kb}KB.json"
                        new_filepath = os.path.join(root, new_filename)

                        i = 1
                        while os.path.exists(new_filepath):  # 处理文件名冲突
                            new_filename = f"正则-{script_name}_{file_size_kb}KB_{i}.json"
                            new_filepath = os.path.join(root, new_filename)
                            i += 1

                        os.rename(filepath, new_filepath)
                        count += 1
                        print(f"已重命名: {filename} -> {new_filename}")

                except json.JSONDecodeError as e:
                    print(f"错误：文件 '{filename}' 不是有效的 JSON: {e}")
                except OSError as e:
                    print(f"错误：访问文件 '{filename}' 时出错: {e}")

    print(f"\n共处理了 {count} 个正则 JSON 文件。")


if __name__ == "__main__":
    download_path = os.path.expanduser("~/storage/shared/Download/Json文件")
    rename_regex_files(download_path)