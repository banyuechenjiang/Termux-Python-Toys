import os
import collections
import yaml

def categorize_files_recursive(directory, ignore_folder="Termux-玩具-备份", max_path_depth=2):
    """
    递归地根据文件后缀对指定目录及其子目录下的文件进行分类，
    并将结果以 YAML 格式打印到终端，以扩展名为最上级键，
    并统计每个扩展名的文件数量。
    忽略指定的文件夹、以点 (.) 开头的文件夹及其内容。
    限制输出路径的深度，避免路径过长。
    在最后进行额外的统计，输出文件总数和各个类型对应的数量。
    去除重复的路径，减少输出长度。

    Args:
        directory: 要分类的目录的路径。
        ignore_folder: 要忽略的文件夹的名称。
        max_path_depth: 输出路径的最大深度。
    """

    file_categories = collections.defaultdict(set)  # 使用 set 存储路径，避免重复
    total_files = 0

    try:
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d != ignore_folder and not d.startswith(".")]  # 忽略指定文件夹和隐藏文件夹

            for filename in files:
                filepath = os.path.relpath(os.path.join(root, filename), directory)
                base, ext = os.path.splitext(filename)
                file_categories[ext.lower()].add(filepath)  # 添加到 set 中，自动去重
                total_files += 1

        # 打印分类结果，统计每个扩展名的文件数量，并以 YAML 格式输出
        print("文件分类结果：")
        for ext, filepaths in file_categories.items():
            truncated_paths = {os.sep.join(p.split(os.sep)[:max_path_depth]) for p in filepaths}  # 截断路径并去重
            print(f"文件类型: {ext} ({len(filepaths)})")
            yaml_output = {ext: {
                "count": len(filepaths),
                "paths": [{"path": p} for p in truncated_paths]  # 使用截断后的路径
            }}
            print(yaml.dump(yaml_output, indent=2, allow_unicode=True))

        # 打印额外统计信息
        print("\n额外统计信息：")
        print(f"文件总数: {total_files}")
        for ext, filepaths in file_categories.items():
            print(f"{ext}: {len(filepaths)}")

    except FileNotFoundError:
        print(f"错误：目录 '{directory}' 不存在。")
    except OSError as e:
        print(f"访问目录 '{directory}' 时出错：{e}")


def choose_directory():
    """
    列出当前目录下的文件夹，并允许用户通过数字选择要处理的文件夹。
    """
    current_dir = os.getcwd()
    subfolders = [
        f for f in os.listdir(current_dir) if os.path.isdir(os.path.join(current_dir, f))
    ]

    if not subfolders:
        print("当前目录下没有文件夹。")
        return None

    print("请选择要处理的文件夹：")
    for i, folder in enumerate(subfolders):
        print(f"{i+1}. {folder}")

    while True:
        try:
            choice = int(input("请输入数字："))
            if 1 <= choice <= len(subfolders):
                return os.path.join(current_dir, subfolders[choice - 1])
            else:
                print("无效的数字，请重新输入。")
        except ValueError:
            print("无效的输入，请重新输入。")


if __name__ == "__main__":
    chosen_dir = choose_directory()
    if chosen_dir:
        categorize_files_recursive(chosen_dir)