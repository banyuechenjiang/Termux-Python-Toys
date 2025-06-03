import os
import json
import collections

def analyze_json_structure(directory):
    """
    递归地遍历指定目录下的所有 JSON 文件，并穷举打印它们的键结构（。

    Args:
        directory: 要分析的目录的路径。
    """

    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith(".json"):
                filepath = os.path.join(root, filename)

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        print(f"\n文件: {filename}") # 只打印一次文件名
                        print_keys(data, "") # 打印键结构，不带路径


                except json.JSONDecodeError as e:
                    print(f"错误: 文件 '{filename}' 不是有效的 JSON 文件: {e}")
                except OSError as e:
                    print(f"错误: 访问文件 '{filename}' 时出错: {e}")




def print_keys(data, prefix=""):
    """
    递归打印字典的键结构（简洁版）.

    Args:
        data: 要打印的字典或列表.
        prefix: 当前的前缀（用于缩进）.
    """

    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{prefix}{key}")
            print_keys(value, prefix + "  ")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            print_keys(item, prefix + f"[{i}]")




if __name__ == "__main__":
    download_path = os.path.expanduser("~/storage/shared/Download/Json文件")
    analyze_json_structure(download_path)