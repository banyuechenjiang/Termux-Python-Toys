import os
import shutil
import time
import datetime

def find_sillytavern_chats_path():
    # 查找 SillyTavern chats 目录路径
    documents_path = os.path.expanduser("~/Documents") # 兼容 Windows, macOS, Linux
    if not os.path.exists(documents_path):
        documents_path = os.path.expanduser("~/文档") # 兼容中文 Windows
    if not os.path.exists(documents_path):
         documents_path = os.path.expanduser("~") # 实在找不到，用用户根目录兜底，让用户手动选择

    print(f"\n在目录: {documents_path} 下查找 SillyTavern 文件夹...")
    sillytavern_dir_path = None
    for root, dirs, _ in os.walk(documents_path):
        if "SillyTavern" in dirs:
            sillytavern_dir_path = os.path.join(root, "SillyTavern")
            break
    if not sillytavern_dir_path:
        print("未找到 SillyTavern 文件夹，请手动输入 chats 目录路径。")
        chats_path = input("请输入 chats 目录的完整路径 (或留空取消): ").strip()
        if chats_path:
            return chats_path
        else:
            print("用户取消输入目录。")
            return None

    chats_path = os.path.join(sillytavern_dir_path, "data", "default-user", "chats")
    if os.path.exists(chats_path):
        print(f"找到 chats 目录: {chats_path}")
        return chats_path
    else:
        print("chats 目录不存在，请检查 SillyTavern 目录结构或手动输入 chats 目录路径。")
        chats_path = input("请输入 chats 目录的完整路径 (或留空取消): ").strip()
        if chats_path:
            return chats_path
        else:
            print("用户取消输入目录。")
            return None

def manual_delete_folders(chats_path):
    # 手动选择文件夹删除
    if not chats_path:
        print("未找到 chats 目录，跳过手动删除文件夹操作。")
        return
    print("\n--- 手动选择文件夹删除 ---")

    folder_names = [d for d in os.listdir(chats_path) if os.path.isdir(os.path.join(chats_path, d))]
    if not folder_names:
        print(f"chats 目录下没有子文件夹。")
        return

    print("chats 目录下的文件夹:")
    for i, folder_name in enumerate(folder_names):
        print(f"{i+1}. {folder_name}")

    selected_indices_str = input("请选择要删除的文件夹序号 (多个序号用空格分隔，留空取消): ")
    if selected_indices_str:
        try:
            selected_indices = [int(i) - 1 for i in selected_indices_str.split()]
            folders_to_delete = [folder_names[i] for i in selected_indices if 0 <= i < len(folder_names)]
            if folders_to_delete:
                for folder_name in folders_to_delete:
                    folder_path = os.path.join(chats_path, folder_name)
                    if input(f"确定删除文件夹及其所有内容: {folder_name} (yes/no)? ").lower() == 'yes':
                        try:
                            shutil.rmtree(folder_path)
                            print(f"已删除文件夹: {folder_name}")
                        except Exception as e:
                            print(f"删除文件夹 {folder_name} 失败: {e}")
                    else:
                        print(f"取消删除文件夹: {folder_name}")
            else:
                print("无效的文件夹序号选择。")
        except ValueError:
            print("无效的输入，请输入数字序号。")
    else:
        print("取消文件夹选择。")

def manual_delete_files_in_folder(chats_path):
    # 手动选择文件夹中的文件删除
    if not chats_path:
        print("未找到 chats 目录，跳过手动删除文件操作。")
        return
    print("\n--- 手动选择文件夹中的文件删除 ---")

    folder_names = [d for d in os.listdir(chats_path) if os.path.isdir(os.path.join(chats_path, d))]
    if not folder_names:
        print(f"chats 目录下没有子文件夹。")
        return

    print("请选择要操作的文件夹:")
    for i, folder_name in enumerate(folder_names):
        print(f"{i+1}. {folder_name}")

    selected_folder_index_str = input("请输入文件夹序号 (留空取消): ")
    if selected_folder_index_str:
        try:
            selected_folder_index = int(selected_folder_index_str) - 1
            if 0 <= selected_folder_index < len(folder_names):
                target_folder_name = folder_names[selected_folder_index]
                target_folder_path = os.path.join(chats_path, target_folder_name)
                file_names = [f for f in os.listdir(target_folder_path) if os.path.isfile(os.path.join(target_folder_path, f))]

                if not file_names:
                    print(f"文件夹 {target_folder_name} 中没有文件。")
                    return

                print(f"\n文件夹 {target_folder_name} 中的文件:")
                for i, file_name in enumerate(file_names):
                    print(f"{i+1}. {file_name}")

                selected_file_indices_str = input("请选择要删除的文件序号 (多个序号用空格分隔，留空取消): ")
                if selected_file_indices_str:
                    try:
                        selected_file_indices = [int(i) - 1 for i in selected_file_indices_str.split()]
                        files_to_delete = [file_names[i] for i in selected_file_indices if 0 <= i < len(file_names)]
                        if files_to_delete:
                            for file_name in files_to_delete:
                                file_path = os.path.join(target_folder_path, file_name)
                                if input(f"确定删除文件: {file_name} (yes/no)? ").lower() == 'yes':
                                    try:
                                        os.remove(file_path)
                                        print(f"已删除文件: {file_name}")
                                    except Exception as e:
                                        print(f"删除文件 {file_name} 失败: {e}")
                                else:
                                    print(f"取消删除文件: {file_name}")
                        else:
                            print("无效的文件序号选择。")
                    except ValueError:
                        print("无效的输入，请输入数字序号。")
                else:
                    print("取消文件选择。")

            else:
                print("无效的文件夹序号选择。")
        except ValueError:
            print("无效的输入，请输入数字序号。")
    else:
        print("取消文件夹选择。")

def auto_delete_empty_folders(chats_path):
    # 自动检查空文件夹删除
    if not chats_path:
        print("未找到 chats 目录，跳过自动删除空文件夹操作。")
        return
    print("\n--- 自动检查空文件夹删除 ---")
    deleted_folders = []
    for root, dirs, files in os.walk(chats_path, topdown=False): # topdown=False 保证先删除子文件夹
        for dir_name in dirs:
            folder_path = os.path.join(root, dir_name)
            if not os.listdir(folder_path): # 检查文件夹是否为空
                try:
                    os.rmdir(folder_path)
                    deleted_folders.append(folder_path)
                except Exception as e:
                    print(f"删除空文件夹 {folder_path} 失败: {e}")

    if deleted_folders:
        print("已删除以下空文件夹:")
        for folder_path in deleted_folders:
            print(folder_path)
    else:
        print("没有找到空文件夹。")

def delete_old_files_in_folder(chats_path):
    # 删除文件夹内 3 个月前的文件
    if not chats_path:
        print("未找到 chats 目录，跳过删除旧文件操作。")
        return
    print("\n--- 删除文件夹内 3 个月前的文件 ---")

    folder_names = [d for d in os.listdir(chats_path) if os.path.isdir(os.path.join(chats_path, d))]
    if not folder_names:
        print(f"chats 目录下没有子文件夹。")
        return

    print("请选择要操作的文件夹:")
    for i, folder_name in enumerate(folder_names):
        print(f"{i+1}. {folder_name}")

    selected_folder_index_str = input("请输入文件夹序号 (留空取消): ")
    if selected_folder_index_str:
        try:
            selected_folder_index = int(selected_folder_index_str) - 1
            if 0 <= selected_folder_index < len(folder_names):
                target_folder_name = folder_names[selected_folder_index]
                target_folder_path = os.path.join(chats_path, target_folder_name)
                file_names = [f for f in os.listdir(target_folder_path) if os.path.isfile(os.path.join(target_folder_path, f))]

                if not file_names:
                    print(f"文件夹 {target_folder_name} 中没有文件。")
                    return

                three_months_ago = datetime.datetime.now() - datetime.timedelta(days=90) # 近似 3 个月前
                files_to_delete = []
                print(f"\n文件夹 {target_folder_name} 中超过 3 个月的文件 (修改时间):")
                for file_name in file_names:
                    file_path = os.path.join(target_folder_path, file_name)
                    modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                    if modified_time < three_months_ago:
                        file_size_kb = os.path.getsize(file_path) / 1024
                        files_to_delete.append({'name': file_name, 'path': file_path, 'modified_time': modified_time, 'size_kb': file_size_kb})
                        print(f"- {file_name}, 修改时间: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}, 大小: {file_size_kb:.2f} KB")

                if not files_to_delete:
                    print(f"没有找到超过 3 个月的文件。")
                    return

                while True: # 循环等待用户确认或退出
                    confirm = input(f"\n确定删除以上 {len(files_to_delete)} 个文件吗? (yes/no, 输入 0 退出): ").lower()
                    if confirm == 'yes':
                        deleted_count = 0
                        for file_info in files_to_delete:
                            try:
                                os.remove(file_info['path'])
                                deleted_count += 1
                            except Exception as e:
                                print(f"删除文件 {file_info['name']} 失败: {e}")
                        print(f"已删除 {deleted_count} 个文件。")
                        break # 退出循环
                    elif confirm == 'no':
                        print("取消删除旧文件操作。")
                        break # 退出循环
                    elif confirm == '0':
                        print("退出删除旧文件操作。")
                        return # 退出函数
                    else:
                        print("无效的输入，请输入 yes, no 或 0。")

            else:
                print("无效的文件夹序号选择。")
        except ValueError:
            print("无效的输入，请输入数字序号。")
    else:
        print("取消文件夹选择。")


def main():
    # 主函数 - 优化菜单呈现，输入0为退出
    chats_path = find_sillytavern_chats_path()
    if not chats_path:
        print("无法执行清理操作，请检查 chats 目录路径。")
        return

    while True:
        print("\n请选择要执行的操作:")
        print("1. 手动选择文件夹删除")
        print("2. 手动选择文件夹中的文件删除")
        print("3. 自动检查空文件夹删除")
        print("4. 删除文件夹内 3 个月前的文件")
        print("0. 退出") # 修改为 0 退出

        choice = input("请输入数字选项: ")

        if choice == '1':
            manual_delete_folders(chats_path)
        elif choice == '2':
            manual_delete_files_in_folder(chats_path)
        elif choice == '3':
            auto_delete_empty_folders(chats_path)
        elif choice == '4':
            delete_old_files_in_folder(chats_path)
        elif choice == '0': 
            print("退出程序。")
            break
        else:
            print("无效的选项，请重新输入。")

if __name__ == "__main__":
    main()