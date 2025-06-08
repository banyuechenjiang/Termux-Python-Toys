import os
import json
import shutil
import re
import collections
import time

try:
    import tkinter as tk
    from tkinter import filedialog
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

# --- 全局配置 ---
# 用户可在此处根据个人需求修改脚本的行为。


# 控制是否启用“移动文件”功能。
# - True:  处理完成后，文件将被移动到其对应的分类子文件夹中 (例如: "JSON角色卡/", "正则/")。
# - False: 文件只会被重命名(如果适用)，并保留在原始位置，不会被移动。
MOVE_FILES = False



# 控制是否启用“预览模式”(Dry Run)。
# - True:  脚本将只分析和显示它“将会”执行的所有操作(重命名、移动)，但不会对硬盘上的任何文件进行实际修改。
#          这是一种安全检查模式，用于在实际操作前预估结果。
# - False: 脚本将实际执行所有文件操作。
DRY_RUN = False


# 当一个文件夹内包含等于或超过此数量的“同一种类型”的JSON文件时
# 即便 MOVE_FILES = True
# 脚本会认为这个文件夹是用户手动整理过的“整合包”，并不会对其进行移动，以保护用户的分类结构。
# 若 MOVE_FILES = False，同时 MANUAL_SORT_THRESHOLD 有设置很大的话，理论上会单纯进行 重命名
MANUAL_SORT_THRESHOLD = 100

# (字符串列表)
# 受保护的文件夹名称列表 (不区分英文字母大小写)。
# 如果一个文件位于名称在此列表中的文件夹内 (例如 "MyGO/" 文件夹)，
# 脚本将永远不会移动它，但仍然会进行重命名等其他操作。
PRESET_NAMES = [
    "kemini", "mygo", "nova", "戏剧", "贝露", 
    "boxbear", "karu", "virgo", "处女座", "逍遥"
]

# (字符串列表)
# 文件类型的处理优先级顺序。
# 脚本会按照这个列表的顺序来尝试识别每个JSON文件。
# 通常情况下，用户无需修改此项。
PROCESSING_ORDER = ["主题", "酒馆脚本", "角色卡", "QuickReply", "正则", "世界书", "预设"]

# (字典)
# 定义了每种文件类型与其最终输出的子文件夹名称之间的映射关系。
# 如果您想更改某个分类的目标文件夹名称 (例如，将 "JSON角色卡" 改为 "My Cards")，
# 只需修改这里的 "folder" 值即可。
TYPE_CONFIG = {
    "主题": {"folder": "主题"},
    "酒馆脚本": {"folder": "酒馆脚本"},
    "角色卡": {"folder": "JSON角色卡"},
    "QuickReply": {"folder": "QuickReply"},
    "正则": {"folder": "正则"},
    "世界书": {"folder": "世界书"},
    "预设": {"folder": "预设"},
}


# (字符串列表)
# 为Termux) 预设的常用路径。
# 脚本会按此列表提供快捷选项，方便用户快速选择。
# 注意: '~/` 会被自动展开为当前用户的主目录。
COMMON_PATHS = [
    "~/storage/shared/Download",
    "~/storage/shared/Documents",
    "~/storage/shared/Download/Json文件",
    "~/Downloads",
    "~/Documents"
]

NAMING_PATTERNS = {
    "主题": re.compile(r"^主题-.*\.json$", re.IGNORECASE),
    "酒馆脚本": re.compile(r"^脚本_.*\.json$", re.IGNORECASE),
    "角色卡": re.compile(r"^角色卡-.*_\d+KB\.json$", re.IGNORECASE),
    "QuickReply": re.compile(r"^QR-.*\.json$", re.IGNORECASE),
    "正则": re.compile(r"^正则-.*\.json$", re.IGNORECASE),
}

def is_filename_standardized(filename, file_type):
    if file_type not in NAMING_PATTERNS:
        return True
    return bool(NAMING_PATTERNS[file_type].match(filename))

def print_main_menu():
    title = "JSON 文件处理与校验工具"
    line_char = "━"
    title_len = sum(2 if '\u4e00' <= char <= '\u9fff' else 1 for char in title)
    total_width = title_len + 4
    padding = line_char * ((total_width - title_len) // 2)
    
    print(f"\n{padding}{title}{padding}\n")
    move_status = "开启" if MOVE_FILES else "关闭"
    dry_run_status = "开启)当前仅预览" if DRY_RUN else "关闭) 即正常执行"

    options = [
        "1. [全功能] 整合与校验", "2. [单功能] 选择特定类型处理", "3. [撤销] 从日志恢复操作",
        f"M. 切换移动模式 (当前: {move_status})", f"P. 切换预览模式 (当前: {dry_run_status})", "0. 退出"
    ]
    for opt in options: print(f"  {opt}")
    print()

def print_submenu(options_to_display):
    print("\n--- 请选择要处理的文件类型 ---")
    for opt in options_to_display:
        print(f"  {opt}")
    print()

def is_theme(data):
    keys_to_check = ["name", "main_text_color", "font_scale", "custom_css"]
    return isinstance(data, dict) and all(key in data for key in keys_to_check)

def is_script(data):
    return isinstance(data, dict) and set(data.keys()) == {"id", "name", "content", "info", "buttons"}

def is_character_card(data):
    if not isinstance(data, dict): return False
    v2_keys = ["spec", "spec_version", "data"]
    if all(key in data for key in v2_keys) and data.get("spec") == "chara_card_v2": return True
    if "name" in data and "first_mes" in data: return True
    return False

def is_quick_reply(data):
    return isinstance(data, dict) and all(key in data for key in ["version", "name", "qrList"])

def is_regex(data):
    return isinstance(data, dict) and all(key in data for key in ["scriptName", "findRegex", "replaceString"])

def is_world_book(data):
    try: return isinstance(data, dict) and "entries" in data and isinstance(data.get("entries", {}), dict) and "0" in data["entries"] and isinstance(data["entries"]["0"], dict)
    except Exception: return False

def is_preset(data):
    preset_keys = ["custom_url", "openai_model", "custom_model", "assistant_prefill", "human_sysprompt_message", "continue_postfix", "function_calling", "seed", "n"]
    return isinstance(data, dict) and sum(1 for key in preset_keys if key in data) >= 2

VALIDATION_MAP = {
    "主题": is_theme, "酒馆脚本": is_script, "角色卡": is_character_card, "QuickReply": is_quick_reply,
    "正则": is_regex, "世界书": is_world_book, "预设": is_preset
}

def load_json_safely(filepath):
    encodings_to_try = ['utf-8', 'utf-16', 'utf-8-sig']
    for encoding in encodings_to_try:
        try:
            with open(filepath, 'r', encoding=encoding) as f: return json.load(f)
        except UnicodeDecodeError: continue
        except (json.JSONDecodeError, OSError): return None
    return None

def sanitize_filename(name):
    if not name: return "未命名"
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def handle_file_collision(filepath):
    if DRY_RUN: return filepath 
    base, ext = os.path.splitext(filepath)
    i = 1
    new_filepath = filepath
    while os.path.exists(new_filepath):
        new_filepath = f"{base}_{i}{ext}"
        i += 1
    return new_filepath

def is_safe_path(path):
    pattern = r'SillyTavern[/\\]data[/\\][^/\\]+'
    normalized_path = os.path.normpath(path)
    if re.search(pattern, normalized_path, re.IGNORECASE): return False
    return True

def detect_manual_sorting(base_path):
    dir_counts = collections.defaultdict(lambda: collections.defaultdict(int))
    for root, _, files in os.walk(base_path):
        for filename in files:
            if not filename.endswith(".json"): continue
            data = load_json_safely(os.path.join(root, filename))
            if not data: continue
            for file_type in PROCESSING_ORDER:
                if VALIDATION_MAP[file_type](data):
                    dir_counts[root][file_type] += 1
                    break
    manual_sorted_dirs = set()
    for directory, counts in dir_counts.items():
        for count in counts.values():
            if count >= MANUAL_SORT_THRESHOLD:
                manual_sorted_dirs.add(directory)
                break
    return manual_sorted_dirs

def _perform_action(filepath, data, file_type, base_path, manually_sorted_dirs):
    original_path_abs = os.path.abspath(filepath)
    original_filename = os.path.basename(filepath)
    root = os.path.dirname(filepath)
    parent_folder_name = os.path.basename(root)
    new_filename = original_filename
    target_subfolder_name = TYPE_CONFIG[file_type]["folder"]
    
    if file_type == "主题": new_filename = f"主题-{sanitize_filename(data.get('name'))}.json"
    elif file_type == "酒馆脚本": new_filename = f"脚本_{sanitize_filename(data.get('name'))}.json"
    elif file_type == "角色卡":
        name_val = sanitize_filename(data.get("data", {}).get("name") or data.get("name"))[:20]
        size_kb = os.path.getsize(filepath) // 1024
        new_filename = f"角色卡-{name_val}_{size_kb}KB.json"
    elif file_type == "QuickReply": new_filename = f"QR-{sanitize_filename(data.get('name'))}.json"
    elif file_type == "正则":
        script_name = sanitize_filename(data.get("scriptName")) if data.get("scriptName") else None
        if script_name and script_name != "未命名": new_filename = f"正则-{script_name}.json"
        else: new_filename = f"正则-{os.path.splitext(original_filename)[0].replace('正则-', '')}.json"
    
    log_entries, current_path = [], original_path_abs
    if new_filename.lower() != original_filename.lower():
        new_filepath_abs = os.path.abspath(os.path.join(root, new_filename))
        if not DRY_RUN:
            new_filepath_abs = handle_file_collision(new_filepath_abs)
            os.rename(current_path, new_filepath_abs)
            log_entries.append({"type": "rename", "original_path": current_path, "new_path": new_filepath_abs})
        current_path = new_filepath_abs

    is_in_manual_dir = root in manually_sorted_dirs
    is_in_preset_dir = parent_folder_name.lower() in PRESET_NAMES
    is_already_sorted = parent_folder_name == target_subfolder_name
    should_move = MOVE_FILES and not is_in_manual_dir and not is_in_preset_dir and not is_already_sorted
    move_skipped = False

    if should_move:
        target_dir = os.path.join(base_path, target_subfolder_name)
        final_dest = os.path.join(target_dir, os.path.basename(current_path))
        if not DRY_RUN:
            os.makedirs(target_dir, exist_ok=True)
            final_dest = handle_file_collision(final_dest)
            shutil.move(current_path, final_dest)
            log_entries.append({"type": "move", "original_path": current_path, "new_path": final_dest})
    elif MOVE_FILES and (is_in_manual_dir or is_in_preset_dir): move_skipped = True
        
    return True, os.path.basename(current_path), move_skipped, log_entries

def process_directory(base_path, specific_type=None):
    mode_text = specific_type if specific_type else "全功能"
    print(f"\n开始 {mode_text} 扫描，正在检测手动分类文件夹...")
    
    manually_sorted_dirs = detect_manual_sorting(base_path)
    if manually_sorted_dirs: print(f"检测到 {len(manually_sorted_dirs)} 个可能已手动分类的文件夹，将不会从中移出文件。")

    print("开始规划处理任务...")
    action_plan, conforming_files, processed_files = [], collections.defaultdict(list), set()
    folder_to_type_map = {v["folder"]: k for k, v in TYPE_CONFIG.items()}
    
    for root, _, files in os.walk(base_path, topdown=True):
        if 'logs' in os.path.basename(root): continue
        parent_folder_name = os.path.basename(root)
        current_dir_type = folder_to_type_map.get(parent_folder_name)

        for filename in files:
            if not filename.endswith(".json"): continue
            filepath = os.path.join(root, filename)
            if filepath in processed_files: continue

            if specific_type and current_dir_type and current_dir_type != specific_type:
                continue

            if current_dir_type and is_filename_standardized(filename, current_dir_type):
                data = load_json_safely(filepath)
                if data and VALIDATION_MAP[current_dir_type](data):
                    conforming_files[current_dir_type].append(filename)
                    processed_files.add(filepath)
                    continue

            data = load_json_safely(filepath)
            if not data: continue
            
            types_to_check = [specific_type] if specific_type else PROCESSING_ORDER
            for file_type in types_to_check:
                if VALIDATION_MAP[file_type](data):
                    action_plan.append({'type': file_type, 'path': filepath, 'data': data})
                    break
            processed_files.add(filepath)

    run_mode_text = "[预览模式]" if DRY_RUN else "[执行模式]"
    print(f"\n{run_mode_text} " + "━" * 8 + " 开始处理 " + "━" * 8)
    
    all_log_entries = []
    report_stats = collections.defaultdict(lambda: collections.defaultdict(int))
    grouped_actions = collections.defaultdict(list)
    for action in action_plan: grouped_actions[action['type']].append(action)
    
    types_to_execute = [specific_type] if specific_type else PROCESSING_ORDER
    processed_something = False

    for file_type in types_to_execute:
        actions_for_type = grouped_actions.get(file_type, [])
        if not actions_for_type: continue
        
        type_header_printed = False
        changed_files_in_type = set()
        
        for action in actions_for_type:
            success, new_name, skipped, log_entries = _perform_action(action['path'], action['data'], file_type, base_path, manually_sorted_dirs)
            if success:
                all_log_entries.extend(log_entries)
                if skipped: report_stats[file_type]['skipped_move'] += 1
                
                if log_entries:
                    if not type_header_printed:
                        print(f"\n--- 处理 {file_type} ---")
                        type_header_printed = True
                    processed_something = True
                    changed_files_in_type.add(action['path'])
                    log_msg = f"处理: {os.path.basename(action['path'])}"
                    for entry in log_entries:
                        if entry['type'] == 'rename': log_msg += f" -> {os.path.basename(entry['new_path'])}"
                        if entry['type'] == 'move': log_msg += f" -> (移动至 {TYPE_CONFIG[file_type]['folder']}{os.sep})"
                    print(log_msg)
        
        num_changed = len(changed_files_in_type)
        num_untouched = len(actions_for_type) - num_changed
        report_stats[file_type]['changed'] = num_changed
        report_stats[file_type]['untouched'] = num_untouched
    
    if not processed_something and not DRY_RUN:
        print("\n所有文件均符合规范，无需处理。")
        
    if all_log_entries and not DRY_RUN: save_log_file(all_log_entries)

    print("\n" + "━" * 8 + f" {mode_text} 任务完成 " + "━" * 8)
    if DRY_RUN: print("\n注意: 当前为预览模式，未对文件进行任何实际修改。")
    
    print("\n[任务摘要]")
    action_verb = "计划" if DRY_RUN else "执行"
    print(f"  - 总计扫描: {len(processed_files)} 个 .json 文件")
    if len(all_log_entries) > 0:
        print(f"  - {action_verb}操作: {len(all_log_entries)} 次 (重命名/移动)")
    
    print("\n[分类详情]")
    total_found = 0
    
    for ftype in PROCESSING_ORDER:
        stats = report_stats[ftype]
        changed = stats.get('changed', 0)
        untouched = stats.get('untouched', 0)
        conforming_checked = len(conforming_files.get(ftype, []))
        skipped_move = stats.get('skipped_move', 0)
        
        conforming_total = untouched + conforming_checked
        total_type_files = changed + conforming_total
        total_found += total_type_files
        
        if total_type_files == 0: continue

        print(f"  - {ftype} (共识别 {total_type_files} 个):")
        if changed > 0:
            change_verb = "将会修改" if DRY_RUN else "已修改"
            print(f"    - {change_verb}: {changed} 个文件")
        if conforming_total > 0:
            print(f"    - 已符合规范: {conforming_total} 个文件")
        if skipped_move > 0:
            print(f"    - 跳过移动 (位于保护目录): {skipped_move} 个文件")

    if total_found == 0:
        print("  - 未找到任何符合条件的文件。")
        
    print("━" * (len(mode_text)*2 + 22))


def save_log_file(log_data):
    logs_dir = 'logs'
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(logs_dir, f"op_log_{timestamp}.json")
    with open(log_filename, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=4, ensure_ascii=False)
    print(f"\n操作已记录到日志文件: {log_filename}")

def undo_from_log():
    logs_dir = 'logs'
    if not os.path.isdir(logs_dir) or not os.listdir(logs_dir):
        print("错误: 未找到 'logs' 文件夹或其中没有任何日志文件。")
        return

    log_path = None
    if GUI_AVAILABLE:
        root = tk.Tk()
        root.withdraw()
        log_path = filedialog.askopenfilename(title="请选择要撤销的日志文件", initialdir=logs_dir, filetypes=[("JSON logs", "*.json")])
    else:
        log_files = sorted([f for f in os.listdir(logs_dir) if f.endswith(".json")], reverse=True)
        if not log_files:
            print("错误: 'logs' 文件夹中没有找到日志文件。")
            return
        print("\n请选择要恢复的日志文件:")
        for i, f in enumerate(log_files):
            print(f"  {i+1}. {f}")
        try:
            choice = int(input(f"请输入选项 (1-{len(log_files)}): ")) - 1
            if 0 <= choice < len(log_files):
                log_path = os.path.join(logs_dir, log_files[choice])
        except (ValueError, IndexError):
            log_path = None
    
    if not log_path:
        print("未选择日志文件，操作取消。")
        return
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            actions = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        print(f"错误: 无法读取或解析日志文件 '{log_path}'。")
        return

    print(f"\n准备从 '{os.path.basename(log_path)}' 撤销 {len(actions)} 个操作...")
    actions.reverse()
    success_count, fail_count = 0, 0
    for action in actions:
        try:
            op_type, original, new = action['type'], action['original_path'], action['new_path']
            if op_type == "rename":
                print(f"撤销重命名: {os.path.basename(new)} -> {os.path.basename(original)}")
                os.rename(new, original)
            elif op_type == "move":
                print(f"撤销移动: {new} -> {original}")
                os.makedirs(os.path.dirname(original), exist_ok=True)
                shutil.move(new, original)
            success_count += 1
        except FileNotFoundError:
            print(f"  - 失败: 文件 '{new}' 不存在，可能已被移动或删除。")
            fail_count += 1
        except Exception as e:
            print(f"  - 失败: 发生未知错误: {e}")
            fail_count += 1
            
    print(f"\n撤销完成: {success_count} 个操作成功, {fail_count} 个操作失败。")
    while True:
        delete_choice = input(f"\n是否删除此日志文件 '{os.path.basename(log_path)}'? (y/n): ").lower()
        if delete_choice == 'y':
            try:
                os.remove(log_path)
                print(f"日志文件 '{os.path.basename(log_path)}' 已删除。")
            except OSError as e:
                print(f"删除日志文件失败: {e}")
            break
        elif delete_choice == 'n':
            print("日志文件已保留。")
            break
        else:
            print("无效的输入，请输入 'y' 或 'n'。")

def get_path_from_user():
    if GUI_AVAILABLE:
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askdirectory(title="请选择要处理的文件夹")
        if not path:
            print("未选择文件夹，操作取消。")
            return None
        return path
    else:
        print("\n未检测到GUI环境，切换到命令行路径选择模式。")
        expanded_paths = [os.path.expanduser(p) for p in COMMON_PATHS]
        print("请选择一个常用路径或手动输入：")
        for i, p in enumerate(expanded_paths):
            print(f"  {i+1}. {p}")
        print(f"  {len(expanded_paths)+1}. 手动输入其他路径")
        while True:
            try:
                choice = int(input(f"请输入选项 (1-{len(expanded_paths)+1}): "))
                if 1 <= choice <= len(expanded_paths):
                    return expanded_paths[choice - 1]
                elif choice == len(expanded_paths) + 1:
                    return os.path.expanduser(input("请输入完整路径: "))
                else:
                    print("无效的选项。")
            except (ValueError, IndexError):
                print("输入无效，请输入数字。")

def main():
    global MOVE_FILES, DRY_RUN
    while True:
        print_main_menu()
        choice = input("选项 (0-3, M, P): ").lower()

        if choice == '0':
            print("程序已退出。")
            break
        elif choice == 'm':
            MOVE_FILES = not MOVE_FILES
        elif choice == 'p':
            DRY_RUN = not DRY_RUN
        elif choice == '3':
            undo_from_log()
        elif choice in ['1', '2']:
            specific_type = None
            if choice == '2':
                all_possible_types = PROCESSING_ORDER[:]
                
                if not MOVE_FILES:
                    types_to_process = [t for t in all_possible_types if t not in ["世界书", "预设"]]
                else:
                    types_to_process = all_possible_types
                
                submenu_options_display = []
                submenu_map = {}
                for i, type_name in enumerate(types_to_process, 1):
                    submenu_options_display.append(f"{i}. {type_name}")
                    submenu_map[str(i)] = type_name
                
                submenu_options_display.append("0. 返回主菜单")
                
                while True:
                    print_submenu(submenu_options_display)
                    prompt_range = f"0-{len(types_to_process)}"
                    sub_choice = input(f"请选择类型 ({prompt_range}): ")
                    
                    if sub_choice == '0':
                        break
                    if sub_choice in submenu_map:
                        specific_type = submenu_map[sub_choice]
                        break
                    else:
                        print("无效的选项。")
                
                if not specific_type:
                    continue
            
            path = get_path_from_user()
            if not path:
                continue
            if not os.path.isdir(path):
                print(f"错误：路径 '{path}' 不存在或不是一个文件夹。")
                continue
            if not is_safe_path(path):
                print("警告：检测到您选择的路径可能为 SillyTavern 用户数据目录，为避免破坏程序结构，已中止操作。")
                continue
            process_directory(path, specific_type=specific_type)
        else:
            print("无效的选项，请重新输入。")

if __name__ == "__main__":
    main()
