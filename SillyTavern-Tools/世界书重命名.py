import os
import json
import re
import collections

def rename_shijieshu_files(directory):
    """
    重命名目录中符合世界书结构的 JSON 文件。

    Args:
        directory: 要处理的目录。
    """

    count = 0

    for root, _, files in os.walk(directory):
        for filename in files:
            # 使用正则表达式匹配 .json 或 .json(数字) 后缀
            if re.match(r'.+\.json(\(\d+\))?$', filename): 
                filepath = os.path.join(root, filename)

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        first_line = f.readline().strip()

                    # 使用正则表达式检查开头是否匹配世界书结构
                    if re.match(r'^\{"entries":\{"0":\{', first_line):
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        # 提取 key 值，限制长度并处理重复, 使用字符串类型的键, 优先使用 key
                        keys = []
                        if "0" in data["entries"]:
                            keys.extend(data["entries"]["0"].get("key", []))
                        
                        last_entry_key = str(len(data["entries"]) - 1)
                        if last_entry_key in data["entries"]:
                            keys.extend(data["entries"][last_entry_key].get("key", []))
                        
                        key_counts = collections.Counter(keys)
                        most_common_key = key_counts.most_common(1)[0][0] if key_counts else ""
                        
                        # 如果 key 为空，则使用 comment
                        if not most_common_key:
                            if "0" in data["entries"]:
                                most_common_key = data["entries"]["0"].get("comment", "")
                            
                            if not most_common_key and last_entry_key in data["entries"]:
                                most_common_key = data["entries"][last_entry_key].get("comment", "")

                        name_value = most_common_key[:20] if most_common_key else "无标题"
                        name_value = re.sub(r'[\\/*?:"<>|]', "", name_value)  # 去除非法字符

                        file_size_kb = os.path.getsize(filepath) // 1024
                        new_filename = f"世界书-{name_value}_{file_size_kb}KB.json"
                        new_filepath = os.path.join(root, new_filename)

                        i = 1
                        while os.path.exists(new_filepath):
                            new_filename = f"世界书-{name_value}_{file_size_kb}KB_{i}.json"
                            new_filepath = os.path.join(root, new_filename)
                            i += 1

                        os.rename(filepath, new_filepath)
                        count += 1
                        print(f"已重命名: {filename} -> {new_filename}")


                except (json.JSONDecodeError, OSError, KeyError, IndexError) as e:
                    print(f"错误：处理文件 '{filename}' 时出错: {e}")



    print(f"\n共处理了 {count} 个世界书 JSON 文件。")




if __name__ == "__main__":
    download_path = os.path.expanduser("~/storage/shared/Download/Json文件")
    rename_shijieshu_files(download_path)