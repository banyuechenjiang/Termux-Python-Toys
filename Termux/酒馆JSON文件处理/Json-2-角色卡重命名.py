import os
import json
import re
import collections

def rename_character_card_files(directory):
    """
    重命名目录中符合角色卡结构的 JSON 文件。

    Args:
        directory: 要处理的目录。
    """

    count = 0

    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.endswith(".json"):
                filepath = os.path.join(root, filename)

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 使用多个键进行匹配
                    matching_keys = ["first_mes", "tags", "name", "spec", "spec_version", "data"]  
                    if all(key in data for key in matching_keys) and data.get("spec") == "chara_card_v2":
                        
                        name_value = data.get("data", {}).get("name", "")
                        name_value = re.sub(r'[\\/*?:"<>|]', "", name_value)[:20] if name_value else "未知角色" # 限制长度并处理非法字符

                        file_size_kb = os.path.getsize(filepath) // 1024
                        new_filename = f"角色卡-{name_value}_{file_size_kb}KB.json"
                        new_filepath = os.path.join(root, new_filename)

                        i = 1
                        while os.path.exists(new_filepath):
                            new_filename = f"角色卡-{name_value}_{file_size_kb}KB_{i}.json"
                            new_filepath = os.path.join(root, new_filename)
                            i += 1

                        os.rename(filepath, new_filepath)
                        count += 1
                        print(f"已重命名: {filename} -> {new_filename}")


                except (json.JSONDecodeError, OSError, KeyError, IndexError) as e:
                    print(f"错误：处理文件 '{filename}' 时出错: {e}")


    print(f"\n共处理了 {count} 个角色卡 JSON 文件。")



if __name__ == "__main__":
    download_path = os.path.expanduser("~/storage/shared/Download/Json文件")
    rename_character_card_files(download_path)