import os

def find_empty_folders(root_path, include_hidden=True):
  """
  穷举 Termux 根目录中的空文件夹（可选包含隐藏文件）。

  Args:
    root_path: Termux 根目录的路径。
    include_hidden: 是否包含隐藏文件夹，默认为 True。

  Returns:
    一个包含所有空文件夹路径的列表。
    如果发生错误，则返回 None，并在控制台打印错误消息。
  """
  empty_folders = []
  try:
    for dirpath, dirnames, filenames in os.walk(root_path):
      if not include_hidden:
        # 忽略隐藏文件和文件夹
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        filenames = [f for f in filenames if not f.startswith(".")]
      if not dirnames and not filenames:
        empty_folders.append(dirpath)
    return empty_folders
  except OSError as e:
    print(f"发生错误：无法访问 '{root_path}' - {e}")
    return None
  except Exception as e:
    print(f"发生未知错误：{e}")
    return None

if __name__ == "__main__":
  termux_root = os.path.expanduser("~")
  empty_folders = find_empty_folders(termux_root)  # 默认包含隐藏文件夹

  if empty_folders is not None:
    if empty_folders:
      print("空文件夹：")
      for folder in empty_folders:
        print(folder)
    else:
      print(f"'{termux_root}' 中没有空文件夹。")