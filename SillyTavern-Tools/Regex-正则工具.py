import os
import json
import re
import time
import collections
from datetime import datetime


USE_GUI = True

LOG_SUBDIR = "log-Regex"
DUPLICATE_SUFFIX = "_DUPLICATE"
REGEX_KEYS_REQUIRED = [
    "scriptName", "findRegex", "replaceString", "disabled",
    "markdownOnly", "promptOnly", "runOnEdit"
]


def load_and_validate_regex_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        if all(key in data for key in REGEX_KEYS_REQUIRED):
            return data
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    return None


def sanitize_filename(name):
    if not name:
        return "未命名"
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()


def handle_file_collision(filepath):
    base, ext = os.path.splitext(filepath)
    i = 1
    new_filepath = filepath
    while os.path.exists(new_filepath):
        new_filepath = f"{base}_{i}{ext}"
        i += 1
    return new_filepath


def save_log(log_data, log_filename):
    os.makedirs(LOG_SUBDIR, exist_ok=True)
    log_path = os.path.join(LOG_SUBDIR, log_filename)
    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        return log_path
    except OSError as e:
        print(f"[错误] 无法写入日志文件: {e}")
        return None

def parse_selection(selection_str, max_val):
    """解析用户输入的选择字符串 (如 '1 3-5 7')"""
    indices = set()
    parts = selection_str.replace(',', ' ').split()
    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            if '-' in part:
                start, end = map(int, part.split('-', 1))
                if start > end:
                    start, end = end, start
                for i in range(start, end + 1):
                    if 1 <= i <= max_val:
                        indices.add(i - 1)
            else:
                i = int(part)
                if 1 <= i <= max_val:
                    indices.add(i - 1)
        except ValueError:
            # 忽略无效的部分
            print(f"[警告] 已忽略无效输入部分: '{part}'")
            continue
    return sorted(list(indices))

def get_target_folders_cli(single_mode=False):
    """新的命令行文件夹选择逻辑"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"\n将在以下目录中查找文件夹: {script_dir}")

    try:
        all_dirs = sorted([
            d for d in os.listdir(script_dir)
            if os.path.isdir(os.path.join(script_dir, d)) and d != LOG_SUBDIR and not d.startswith('.')
        ])
    except OSError as e:
        print(f"[错误] 无法读取目录: {e}")
        return None

    if not all_dirs:
        print("未找到任何可处理的子文件夹。")
        return None

    print("\n请选择要处理的文件夹:")
    for i, dirname in enumerate(all_dirs):
        print(f"  {i + 1}. {dirname}")

    if single_mode:
        prompt = f"\n请输入单个数字 (1-{len(all_dirs)}): "
    else:
        prompt = f"\n请选择 (可输入范围如 1-3, 多个用空格隔开如 1 3, 或输入 'a' 全选): "
    
    user_input = input(prompt).strip().lower()

    if not user_input:
        print("未做任何选择。")
        return None

    selected_indices = []
    if user_input in ['a', 'all']:
        selected_indices = list(range(len(all_dirs)))
    else:
        selected_indices = parse_selection(user_input, len(all_dirs))

    if not selected_indices:
        print("根据您的输入，没有选中任何有效文件夹。")
        return None
    
    if single_mode and len(selected_indices) > 1:
        print("单选模式下仅处理第一个有效选择。")
        selected_indices = [selected_indices[0]]

    selected_paths = [os.path.join(script_dir, all_dirs[i]) for i in selected_indices]
    
    print("\n已选择以下文件夹进行处理:")
    for path in selected_paths:
        print(f"  - {os.path.basename(path)}")
        
    return selected_paths


def get_target_folders(single_mode=False):
    if not USE_GUI:
        return get_target_folders_cli(single_mode)

    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("\n[错误] Tkinter 图形库未安装或无法加载。")
        print("将使用命令行模式进行选择。")
        return get_target_folders_cli(single_mode)

    root = tk.Tk()
    root.withdraw()

    if single_mode:
        target_dir = filedialog.askdirectory(title="请选择一个包含正则文件的子文件夹")
        return [target_dir] if target_dir else None
    else:
        root_dir = filedialog.askdirectory(title="请选择包含多个子文件夹的根目录")
        if not root_dir:
            return None
        return [
            os.path.join(root_dir, d) for d in os.listdir(root_dir)
            if os.path.isdir(os.path.join(root_dir, d)) and d != LOG_SUBDIR
        ]


def phase_one_detect_duplicates(folders_to_scan):
    print("\n>> 阶段一：检测重复")
    regex_map = collections.defaultdict(list)
    local_log_entries = []
    files_marked = 0

    for folder in folders_to_scan:
        for filename in os.listdir(folder):
            if not filename.endswith('.json'):
                continue
            filepath = os.path.join(folder, filename)
            data = load_and_validate_regex_json(filepath)
            if not data:
                continue

            flags = (
                data.get('disabled', False), data.get('markdownOnly', False),
                data.get('promptOnly', True), data.get('runOnEdit', True)
            )
            key = (data['findRegex'], data['replaceString'], flags)
            regex_map[key].append(filepath)

    for key, paths in regex_map.items():
        if len(paths) > 1:
            print("\n[分析] 发现内容完全重复的脚本:")
            sorted_paths = sorted(paths)
            for p in sorted_paths:
                print(f"  - {os.path.relpath(p)}")

            for path_to_mark in sorted_paths:
                original_path_abs = os.path.abspath(path_to_mark)
                base_filename, ext = os.path.splitext(os.path.basename(original_path_abs))
                if base_filename.endswith(DUPLICATE_SUFFIX):
                    continue

                base, ext = os.path.splitext(original_path_abs)
                new_path_abs = handle_file_collision(f"{base}{DUPLICATE_SUFFIX}{ext}")

                try:
                    os.rename(original_path_abs, new_path_abs)
                    print(f"  [标记] 已重命名: '{os.path.basename(original_path_abs)}' -> '{os.path.basename(new_path_abs)}'")
                    local_log_entries.append({"original_path": original_path_abs, "new_path": new_path_abs})
                    files_marked += 1
                except OSError as e:
                    print(f"  [错误] 标记文件 '{os.path.basename(original_path_abs)}' 失败: {e}")

    if not files_marked and not any(len(p) > 1 for p in regex_map.values()):
        print("未发现需要标记的重复文件。")

    return local_log_entries, files_marked


def phase_two_apply_tags(folders_to_process):
    print("\n>> 阶段二：添加标签")
    local_log_entries = []
    files_processed, files_skipped = 0, 0

    for folder in folders_to_process:
        tag = os.path.basename(folder)
        print(f"\n处理文件夹: '{tag}'")
        folder_processed_count, folder_skipped_count = 0, 0
        all_filenames = os.listdir(folder)

        for filename in all_filenames:
            if not filename.endswith('.json') or DUPLICATE_SUFFIX in filename:
                continue

            expected_prefix = f"正则-【{tag}】-"
            if filename.startswith(expected_prefix):
                files_skipped += 1
                folder_skipped_count += 1
                continue

            filepath = os.path.join(folder, filename)
            data = load_and_validate_regex_json(filepath)
            if not data:
                print(f"  [跳过] '{filename}' 不是有效的正则文件或内容不完整。")
                files_skipped += 1
                folder_skipped_count += 1
                continue

            original_script_name = data.get("scriptName", os.path.splitext(filename)[0])
            sanitized_name = sanitize_filename(original_script_name)
            new_script_name = f"【{tag}】-{sanitized_name}"
            data['scriptName'] = new_script_name
            new_filename_base = f"正则-{new_script_name}.json"
            original_path_abs = os.path.abspath(filepath)
            new_path_abs = os.path.join(os.path.dirname(original_path_abs), new_filename_base)
            new_path_abs = handle_file_collision(new_path_abs)

            try:
                with open(original_path_abs, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                if original_path_abs.lower() != new_path_abs.lower():
                    os.rename(original_path_abs, new_path_abs)
                print(f"  [处理] '{os.path.basename(original_path_abs)}' -> '{os.path.basename(new_path_abs)}'")
                local_log_entries.append({"original_path": original_path_abs, "new_path": new_path_abs})
                files_processed += 1
                folder_processed_count += 1
            except OSError as e:
                print(f"  [错误] 处理文件 '{filename}' 失败: {e}")

        if folder_processed_count == 0 and folder_skipped_count > 0:
            print("  所有有效文件均已正确标记。")

    return local_log_entries, files_processed, files_skipped


def run_batch_processing(folders_to_process):
    if not folders_to_process:
        print("未选择任何文件夹，操作取消。")
        return

    print("\n===== 开始处理以下文件夹 =====")
    for folder in folders_to_process:
        print(f"- {os.path.relpath(folder)}")
    print("==============================")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"log_{timestamp}.json"
    total_log = []

    phase_one_logs, files_marked = phase_one_detect_duplicates(folders_to_process)
    total_log.extend(phase_one_logs)
    if phase_one_logs:
        log_path = save_log(total_log, log_filename)
        if log_path:
            print(f"\n[日志] 阶段一操作记录已保存至: {os.path.relpath(log_path)}")

    phase_two_logs, files_processed, files_skipped = phase_two_apply_tags(folders_to_process)
    total_log.extend(phase_two_logs)

    print("\n--- 任务总结 ---")
    print(f"总计: 标记 {files_marked} 个重复文件, 新增/更新 {files_processed} 个文件, 跳过 {files_skipped} 个文件。")

    if total_log:
        log_path = save_log(total_log, log_filename)
        if log_path:
            print(f"\n[日志] 完整操作记录已更新至: {os.path.relpath(log_path)}")
    else:
        print("\n未执行任何文件操作，无需生成日志。")


def undo_from_log():
    if not os.path.isdir(LOG_SUBDIR) or not os.listdir(LOG_SUBDIR):
        print("未找到日志文件夹或其中没有任何日志文件。")
        return

    log_files = sorted(
        [f for f in os.listdir(LOG_SUBDIR) if f.startswith('log_') and f.endswith('.json')],
        reverse=True
    )

    if not log_files:
        print("未找到可用的日志文件。")
        return

    print("\n请选择要用于撤销操作的日志文件:")
    for i, filename in enumerate(log_files):
        print(f"  {i + 1}. {filename}")
    print("  0. 返回主菜单")

    try:
        choice_str = input(f"请选择 (0-{len(log_files)}): ")
        choice = int(choice_str)
        if choice == 0: return
        if not 1 <= choice <= len(log_files):
            print("无效选择。")
            return
        log_to_use = os.path.join(LOG_SUBDIR, log_files[choice - 1])
    except (ValueError, IndexError):
        print("无效输入或选择。")
        return

    try:
        with open(log_to_use, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"读取日志文件 '{os.path.basename(log_to_use)}' 失败: {e}")
        return

    if not log_data:
        print("日志文件为空，无需操作。")
        return

    print(f"\n将从 '{os.path.basename(log_to_use)}' 撤销 {len(log_data)} 个操作。")
    if input("您确定要继续吗? (y/n): ").lower() != 'y':
        print("操作已取消。")
        return

    success, skipped, failed = 0, 0, 0
    for entry in reversed(log_data):
        original_path, new_path = entry['original_path'], entry['new_path']
        if not os.path.exists(new_path):
            skipped += 1
            continue
        if os.path.exists(original_path):
            skipped += 1
            continue
        try:
            os.rename(new_path, original_path)
            success += 1
        except OSError:
            failed += 1

    print(f"\n撤销完成: {success} 个成功, {skipped} 个跳过, {failed} 个失败。")

    if input(f"是否删除已使用的日志文件 '{os.path.basename(log_to_use)}'? (y/n): ").lower() == 'y':
        try:
            os.remove(log_to_use)
            print("日志文件已删除。")
        except OSError as e:
            print(f"删除日志文件失败: {e}")


def main():
    global USE_GUI
    while True:
        print("\n" + "=" * 30)
        print("  正则脚本文件批量处理器")
        print("=" * 30)
        mode_text = "图形选择 (Tkinter)" if USE_GUI else "命令行模式 "
        print(f"当前UI模式: {mode_text}\n")
        print("1. 处理单个文件夹")
        print("2. 批量处理子文件夹")
        print("3. 撤销操作")
        print("0. 退出")

        choice = input("\n请选择 (0-3), 或输入 't' 切换UI模式: ").strip().lower()

        if choice == 't':
            USE_GUI = not USE_GUI
            print(f"\n模式已切换为: {'图形模式' if USE_GUI else '命令行模式'}")
            continue

        if choice == '1':
            folders = get_target_folders(single_mode=True)
            if folders: run_batch_processing(folders)
        elif choice == '2':
            folders = get_target_folders(single_mode=False)
            if folders: run_batch_processing(folders)
        elif choice == '3':
            undo_from_log()
        elif choice == '0':
            print("程序已退出。")
            break
        else:
            print("无效的选项，请重新输入。")


if __name__ == "__main__":
    main()
