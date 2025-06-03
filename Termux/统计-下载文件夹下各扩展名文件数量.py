import os
import collections

def categorize_files_recursive(directory, ignore_folder="Termux-玩具-备份"):
    """
    递归地根据文件后缀对指定目录及其子目录下的文件进行分类，并将结果打印到终端。
    忽略指定的文件夹、以点 (.) 开头的文件夹及其内容。

    Args:
        directory: 要分类的目录的路径。
        ignore_folder: 要忽略的文件夹的名称。
    """

    file_categories = collections.defaultdict(list)

    try:
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d != ignore_folder and not d.startswith(".")]  # 忽略指定文件夹和隐藏文件夹

            for filename in files:
                filepath = os.path.relpath(os.path.join(root, filename), directory)
                base, ext = os.path.splitext(filename)
                file_categories[ext.lower()].append(filepath)

        # 打印分类结果，统计每个扩展名的文件数量
        for ext, filepaths in file_categories.items():
            print(f"\n文件类型: {ext} ({len(filepaths)})")
            for filepath in filepaths:
                print(f"  - {filepath}")


    except FileNotFoundError:
        print(f"错误：目录 '{directory}' 不存在。")
    except OSError as e:
        print(f"访问目录 '{directory}' 时出错：{e}")


if __name__ == "__main__":
    download_path = os.path.expanduser("~/storage/shared/Download")
    categorize_files_recursive(download_path)