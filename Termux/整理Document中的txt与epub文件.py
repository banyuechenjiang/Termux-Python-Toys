import os
import shutil
import sys

def is_html_file(file_path):
    """检查文件是否符合 HTML 结构。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read(1024)
            if "<html" in content.lower() and "</html>" in content.lower():
                return True
    except (OSError, UnicodeDecodeError):
        pass
    return False

def watch_and_move(watch_path, extensions, hidden_folder):
    """将指定扩展名的新文件移动到隐藏文件夹。"""
    os.makedirs(os.path.join(watch_path, hidden_folder), exist_ok=True)

    for filename in os.listdir(watch_path):
        if any(filename.endswith(ext) for ext in extensions):
            source_path = os.path.join(watch_path, filename)
            target_path = os.path.join(watch_path, hidden_folder, filename)

            try:
                shutil.move(source_path, target_path)
                print(f"已将 '{filename}' 移动到 '{hidden_folder}'")
            except (shutil.Error, OSError) as e:
                print(f"移动 '{filename}' 时出错: {e}")

        elif '.' not in filename:
            file_path = os.path.join(watch_path, filename)
            if is_html_file(file_path):
                add_extension = input(f"检测到疑似 HTML 文件 '{filename}'。是否添加 .html 扩展名？(y/n): ")
                if add_extension.lower() == 'y':
                    new_file_path = file_path + ".html"
                    try:
                        os.rename(file_path, new_file_path)
                        print(f"已将 '{filename}' 重命名为 '{filename}.html'")
                    except OSError as e:
                        print(f"重命名 '{filename}' 时出错: {e}")


def list_files(watch_path, hidden_folder):
    """列出隐藏文件夹中的文件。"""
    hidden_path = os.path.join(watch_path, hidden_folder)
    if not os.path.exists(hidden_path):
        print(f"隐藏文件夹 '{hidden_folder}' 不存在。")
        return [] # 返回空列表，避免后续处理出错

    files = []
    for filename in os.listdir(hidden_path):
        files.append(filename)
    return files


def read_txt_file(file_path):
    """读取 .txt 文件内容，并进行分页输出。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            print(f"\n--- {os.path.basename(file_path)} 的内容 ---")

            lines = content.splitlines()
            for i in range(0, len(lines), 10):  # 每页显示 10 行
                chunk = lines[i:i + 10]
                print("\n".join(chunk))
                input("按 Enter 键继续...")

    except (OSError, UnicodeDecodeError) as e:
        print(f"读取 '{os.path.basename(file_path)}' 时出错: {e}")



if __name__ == "__main__":
    watch_path = os.path.expanduser("~/storage/shared/Documents/")

    while True:
        print("\n选择一个选项:")
        print("1. 将 .txt 文件移动到 .txt 文件夹")
        print("2. 将 .epub 文件移动到 .epub 文件夹")
        print("3. 将 .txt 和 .epub 文件移动到各自的文件夹")
        print("4. 检查无扩展名文件并重命名为 .html")
        print("5. 读取 .txt 文件夹中的 .txt 文件")
        print("6. 列出 .epub 文件夹中的文件")
        print("7. 退出")

        choice = input("输入你的选择: ")

        if choice == '1':
            watch_and_move(watch_path, ['.txt'], ".txt")
        elif choice == '2':
            watch_and_move(watch_path, ['.epub'], ".epub")
        elif choice == '3':
            watch_and_move(watch_path, ['.txt'], ".txt")
            watch_and_move(watch_path, ['.epub'], ".epub")
        elif choice == '4':
            watch_and_move(watch_path, [], "")
        elif choice == '5':
            txt_files = list_files(watch_path, ".txt")
            if txt_files:
                print("\n.txt 文件列表：")
                for i, filename in enumerate(txt_files):
                    print(f"{i+1}. {filename}")

                while True:
                    try:
                        file_index = int(input("输入要读取的文件编号："))
                        if 1 <= file_index <= len(txt_files):
                            selected_file = os.path.join(watch_path, ".txt", txt_files[file_index-1])
                            read_txt_file(selected_file)
                            break  # 成功读取后跳出循环
                        else:
                            print("无效的编号，请重新输入。")
                    except ValueError:
                        print("请输入数字编号。")
            
        elif choice == '6':
            epub_files = list_files(watch_path, ".epub")
            if epub_files:
                print("\n.epub 文件列表：")
                for filename in epub_files:
                    print(filename)
        elif choice == '7':
            sys.exit(0)
        else:
            print("无效的选择，请重新输入。")