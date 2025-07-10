import os
import sys
import json
import shutil
import re
import collections
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable

try:
    import tkinter as tk
    from tkinter import filedialog
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

# --- 全局配置 ---
# 用户可在此处根据个人需求修改脚本的行为。

# 控制是否启用“移动文件”功能。
MOVE_FILES = False

# 控制是否默认启用“预览模式”。
DRY_RUN = False

# 当一个文件夹内包含等于或超过此数量的“同一种类型”的JSON文件时，不会从中移出文件。
MANUAL_SORT_THRESHOLD = 100

# 受保护的文件夹名称列表 (不区分大小写)。位于这些文件夹内的文件不会被移动。
PRESET_NAMES = [
    "kemini", "mygo", "nova", "戏剧", "贝露", "dreammini", "gemini", 
    "boxbear", "karu", "virgo", "处女座", "逍遥", "janus", "lsr"
]

# (为Termux等环境) 预设的常用路径。
COMMON_PATHS = [
    "~/storage/shared/Download",
    "~/storage/shared/Documents",
    "~/storage/shared/Download/Json文件",
    "~/Downloads",
    "~/Documents"
]

# --- 核心架构：数据驱动设计 ---
# 将所有与文件类型相关的配置统一到一个结构中，便于维护和扩展。

def sanitize_filename(name: str) -> str:
    """移除文件名中的非法字符。"""
    if not name: return "未命名"
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def _get_theme_name(data: Dict, filepath: str) -> str:
    """生成主题文件的标准名称。"""
    return f"主题-{sanitize_filename(data.get('name'))}.json"

def _get_script_name(data: Dict, filepath: str) -> str:
    """生成酒馆脚本的标准名称。"""
    return f"脚本_{sanitize_filename(data.get('name'))}.json"

def _get_character_card_name(data: Dict, filepath: str) -> str:
    """生成角色卡的标准名称，包含名字和文件大小。"""
    name_val = sanitize_filename(data.get("data", {}).get("name") or data.get("name"))[:20]
    size_kb = os.path.getsize(filepath) // 1024
    return f"角色卡-{name_val}_{size_kb}KB.json"

def _get_quick_reply_name(data: Dict, filepath: str) -> str:
    """生成QuickReply的标准名称。"""
    return f"QR-{sanitize_filename(data.get('name'))}.json"

def _get_regex_name(data: Dict, filepath: str) -> str:
    """生成正则文件的标准名称。"""
    script_name = sanitize_filename(data.get("scriptName"))
    if script_name and script_name != "未命名":
        return f"正则-{script_name}.json"
    return f"正则-{os.path.splitext(os.path.basename(filepath))[0].replace('正则-', '')}.json"

def _get_no_rename(data: Dict, filepath: str) -> Optional[str]:
    """对于不需要重命名的类型（如世界书、预设），返回None。"""
    return None

FILE_TYPE_DEFINITIONS = {
    "主题": {
        "validator": lambda data: isinstance(data, dict) and all(k in data for k in ["name", "main_text_color", "font_scale"]),
        "naming_func": _get_theme_name,
        "folder": "主题",
        "standard_pattern": re.compile(r"^主题-.*\.json$", re.IGNORECASE)
    },
    "酒馆脚本": {
        "validator": lambda data: isinstance(data, dict) and set(data.keys()) == {"id", "name", "content", "info", "buttons"},
        "naming_func": _get_script_name,
        "folder": "酒馆脚本",
        "standard_pattern": re.compile(r"^脚本_.*\.json$", re.IGNORECASE)
    },
    "角色卡": {
        "validator": lambda data: isinstance(data, dict) and (("spec" in data and data.get("spec") == "chara_card_v2") or ("name" in data and "first_mes" in data)),
        "naming_func": _get_character_card_name,
        "folder": "JSON角色卡",
        "standard_pattern": re.compile(r"^角色卡-.*_\d+KB\.json$", re.IGNORECASE)
    },
    "QuickReply": {
        "validator": lambda data: isinstance(data, dict) and all(k in data for k in ["version", "name", "qrList"]),
        "naming_func": _get_quick_reply_name,
        "folder": "QuickReply",
        "standard_pattern": re.compile(r"^QR-.*\.json$", re.IGNORECASE)
    },
    "正则": {
        "validator": lambda data: isinstance(data, dict) and all(k in data for k in ["scriptName", "findRegex", "replaceString"]),
        "naming_func": _get_regex_name,
        "folder": "正则",
        "standard_pattern": re.compile(r"^正则-.*\.json$", re.IGNORECASE)
    },
    "世界书": {
        "validator": lambda data: isinstance(data, dict) and "entries" in data and isinstance(data.get("entries", {}), dict),
        "naming_func": _get_no_rename,
        "folder": "世界书",
        "standard_pattern": None
    },
    "预设": {
        "validator": lambda data: isinstance(data, dict) and sum(1 for k in ["custom_url", "openai_model", "assistant_prefill"] if k in data) >= 2,
        "naming_func": _get_no_rename,
        "folder": "预设",
        "standard_pattern": None
    }
}
PROCESSING_ORDER = ["主题", "酒馆脚本", "角色卡", "QuickReply", "正则", "世界书", "预设"]

# --- 结构化数据对象 ---
@dataclass
class Action:
    """定义一个计划中的文件操作。"""
    file_type: str
    original_path: str
    data: Dict
    new_name: Optional[str] = None
    should_move: bool = False
    target_dir: Optional[str] = None
    move_skipped_reason: Optional[str] = None

@dataclass
class ActionResult:
    """定义一个已完成的文件操作结果。"""
    original_path: str
    final_path: str
    file_type: str
    log_entries: List[Dict] = field(default_factory=list)
    status: str = "untouched" # "changed", "untouched", "skipped_move"

# --- 辅助函数 ---
def load_json_safely(filepath: str) -> Optional[Dict]:
    """安全地加载JSON文件，尝试多种编码。"""
    encodings_to_try = ['utf-8', 'utf-16', 'utf-8-sig']
    for encoding in encodings_to_try:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return json.load(f)
        except UnicodeDecodeError:
            continue
        except (json.JSONDecodeError, OSError):
            return None
    return None

def handle_file_collision(filepath: str) -> str:
    """处理文件名冲突，通过在末尾添加数字来生成唯一路径。"""
    if DRY_RUN: return filepath 
    base, ext = os.path.splitext(filepath)
    i = 1
    new_filepath = filepath
    while os.path.exists(new_filepath):
        new_filepath = f"{base}_{i}{ext}"
        i += 1
    return new_filepath

def is_safe_path(path: str) -> bool:
    """检查路径是否为受保护的SillyTavern系统目录。"""
    pattern = r'SillyTavern[/\\]data[/\\][^/\\]+'
    normalized_path = os.path.normpath(path)
    return not re.search(pattern, normalized_path, re.IGNORECASE)

def detect_manual_sorting(base_path: str) -> set:
    """检测用户可能已手动分类的文件夹。"""
    dir_counts = collections.defaultdict(lambda: collections.defaultdict(int))
    for root, _, files in os.walk(base_path):
        for filename in files:
            if not filename.endswith(".json"): continue
            filepath = os.path.join(root, filename)
            data = load_json_safely(filepath)
            if not data: continue
            for file_type in PROCESSING_ORDER:
                if FILE_TYPE_DEFINITIONS[file_type]["validator"](data):
                    dir_counts[root][file_type] += 1
                    break
    manual_sorted_dirs = set()
    for directory, counts in dir_counts.items():
        for count in counts.values():
            if count >= MANUAL_SORT_THRESHOLD:
                manual_sorted_dirs.add(directory)
                break
    return manual_sorted_dirs

# --- 核心流程：阶段化执行 ---

def _phase_1_plan_actions(base_path: str, manually_sorted_dirs: set, specific_type: Optional[str]) -> List[Action]:
    """阶段一：扫描文件，识别类型，并制定行动计划。"""
    print("开始规划处理任务...")
    action_plan = []
    processed_files = set()
    types_to_check = [specific_type] if specific_type else PROCESSING_ORDER

    for root, _, files in os.walk(base_path, topdown=True):
        if 'logs' in os.path.basename(root).lower(): continue
        
        for filename in files:
            if not filename.endswith(".json"): continue
            filepath = os.path.join(root, filename)
            if filepath in processed_files: continue
            processed_files.add(filepath)

            data = load_json_safely(filepath)
            if not data: continue

            identified_type = None
            for file_type in types_to_check:
                if FILE_TYPE_DEFINITIONS[file_type]["validator"](data):
                    identified_type = file_type
                    break
            if not identified_type: continue

            config = FILE_TYPE_DEFINITIONS[identified_type]
            new_name = config["naming_func"](data, filepath)
            
            parent_folder_name = os.path.basename(root)
            target_subfolder_name = config["folder"]
            is_in_manual_dir = root in manually_sorted_dirs
            is_in_preset_dir = parent_folder_name.lower() in PRESET_NAMES
            is_already_sorted = parent_folder_name == target_subfolder_name
            
            should_move = MOVE_FILES and not is_in_manual_dir and not is_in_preset_dir and not is_already_sorted
            move_skipped_reason = None
            if MOVE_FILES and not should_move:
                if is_in_manual_dir: move_skipped_reason = "manual"
                elif is_in_preset_dir: move_skipped_reason = "preset"

            target_dir = os.path.join(base_path, target_subfolder_name) if should_move else None

            action_plan.append(Action(
                file_type=identified_type, original_path=filepath, data=data,
                new_name=new_name, should_move=should_move, target_dir=target_dir,
                move_skipped_reason=move_skipped_reason
            ))
            
    return action_plan, processed_files

def _phase_2_execute_plan(action_plan: List[Action]) -> List[ActionResult]:
    """阶段二：根据计划执行文件操作或进行预览。"""
    run_mode_text = "[预览模式]" if DRY_RUN else "[执行模式]"
    print(f"\n{run_mode_text} " + "━" * 8 + " 开始处理 " + "━" * 8)
    
    results = []
    grouped_actions = collections.defaultdict(list)
    for action in action_plan:
        # 只有需要重命名或移动的文件才需要分组显示
        if (action.new_name and os.path.basename(action.original_path).lower() != action.new_name.lower()) or action.should_move:
            grouped_actions[action.file_type].append(action)

    for file_type in PROCESSING_ORDER:
        if file_type not in grouped_actions: continue
        
        print(f"\n--- 处理 {file_type} ---")
        for action in grouped_actions[file_type]:
            current_path = action.original_path
            log_entries = []
            
            # 模拟/执行重命名
            if action.new_name and os.path.basename(current_path).lower() != action.new_name.lower():
                new_filepath = os.path.join(os.path.dirname(current_path), action.new_name)
                if not DRY_RUN:
                    new_filepath = handle_file_collision(new_filepath)
                    os.rename(current_path, new_filepath)
                log_entries.append({"type": "rename", "original_path": current_path, "new_path": new_filepath})
                current_path = new_filepath

            # 模拟/执行移动
            if action.should_move and action.target_dir:
                final_dest = os.path.join(action.target_dir, os.path.basename(current_path))
                if not DRY_RUN:
                    os.makedirs(action.target_dir, exist_ok=True)
                    final_dest = handle_file_collision(final_dest)
                    shutil.move(current_path, final_dest)
                log_entries.append({"type": "move", "original_path": current_path, "new_path": final_dest})
                current_path = final_dest

            log_msg = f"处理: {os.path.basename(action.original_path)}"
            rename_log = next((le for le in log_entries if le['type'] == 'rename'), None)
            move_log = next((le for le in log_entries if le['type'] == 'move'), None)
            if rename_log: log_msg += f" -> {os.path.basename(rename_log['new_path'])}"
            if move_log: log_msg += f" -> (移动至 {FILE_TYPE_DEFINITIONS[file_type]['folder']}{os.sep})"
            print(log_msg)

            results.append(ActionResult(
                original_path=action.original_path, final_path=current_path, file_type=action.file_type,
                log_entries=log_entries, status="changed"
            ))
            
    if not any(r.status == 'changed' for r in results):
        print("\n所有文件均符合规范，无需处理。")
        
    return results

def _phase_3_generate_report(action_plan: List[Action], results: List[ActionResult], scanned_files: set, mode_text: str):
    """阶段三：根据执行结果生成摘要报告。"""
    print("\n" + "━" * 8 + f" {mode_text} 任务完成 " + "━" * 8)
    if DRY_RUN: print("\n注意: 当前为预览模式，未对文件进行任何实际修改。")
    
    stats = collections.defaultdict(lambda: collections.defaultdict(int))
    actioned_paths = {res.original_path for res in results}
    
    for res in results:
        stats[res.file_type]['changed'] += 1
        
    for action in action_plan:
        if action.original_path not in actioned_paths:
            if action.move_skipped_reason:
                stats[action.file_type]['skipped_move'] += 1
            else:
                stats[action.file_type]['untouched'] += 1

    print("\n[任务摘要]")
    action_verb = "计划" if DRY_RUN else "执行"
    total_ops = sum(len(r.log_entries) for r in results)
    print(f"  - 总计扫描: {len(scanned_files)} 个 .json 文件")
    if total_ops > 0:
        print(f"  - {action_verb}操作: {total_ops} 次 (重命名/移动)")
    
    print("\n[分类详情]")
    total_found = sum(len(v) for v in stats.values())
    if total_found == 0:
        print("  - 未找到任何符合条件的文件。")
        return

    for ftype in PROCESSING_ORDER:
        type_stats = stats.get(ftype)
        if not type_stats: continue
        
        total_type_files = sum(type_stats.values())
        print(f"  - {ftype} (共识别 {total_type_files} 个):")
        
        if type_stats.get('changed', 0) > 0:
            change_verb = "将会修改" if DRY_RUN else "已修改"
            print(f"    - {change_verb}: {type_stats['changed']} 个文件")
        if type_stats.get('untouched', 0) > 0:
            print(f"    - 已符合规范: {type_stats['untouched']} 个文件")
        if type_stats.get('skipped_move', 0) > 0:
            print(f"    - 跳过移动 (位于保护目录): {type_stats['skipped_move']} 个文件")
        
    print("━" * (len(mode_text)*2 + 22))

def process_directory(base_path: str, specific_type: Optional[str] = None):
    """主处理流程，协调各个阶段。"""
    mode_text = specific_type if specific_type else "全功能"
    print(f"\n开始 {mode_text} 扫描，正在检测手动分类文件夹...")
    
    manually_sorted_dirs = detect_manual_sorting(base_path)
    if manually_sorted_dirs: print(f"检测到 {len(manually_sorted_dirs)} 个可能已手动分类的文件夹，将不会从中移出文件。")

    action_plan, scanned_files = _phase_1_plan_actions(base_path, manually_sorted_dirs, specific_type)
    results = _phase_2_execute_plan(action_plan)
    
    all_log_entries = [entry for res in results for entry in res.log_entries]
    if all_log_entries and not DRY_RUN:
        save_log_file(all_log_entries)

    _phase_3_generate_report(action_plan, results, scanned_files, mode_text)

# --- UI 与交互函数 ---
def save_log_file(log_data: List[Dict]):
    """将操作记录保存到日志文件。"""
    logs_dir = 'logs'
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(logs_dir, f"op_log_{timestamp}.json")
    with open(log_filename, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=4, ensure_ascii=False)
    print(f"\n操作已记录到日志文件: {log_filename}")

def undo_from_log():
    """从日志文件撤销操作。"""
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
            pass
    
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

def get_path_from_user() -> Optional[str]:
    """通过GUI或命令行获取用户要处理的文件夹路径。"""
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

def print_main_menu():
    """打印主菜单。"""
    title = "JSON 文件处理与校验工具"
    line_char = "━"
    title_len = sum(2 if '\u4e00' <= char <= '\u9fff' else 1 for char in title)
    total_width = title_len + 4
    padding = line_char * ((total_width - title_len) // 2)
    
    print(f"\n{padding}{title}{padding}\n")
    move_status = "开启" if MOVE_FILES else "关闭"
    dry_run_status = "开启 (仅预览)" if DRY_RUN else "关闭 (正常执行)"

    options = [
        "1. [全功能] 整合与校验", "2. [单功能] 选择特定类型处理", "3. [撤销] 从日志恢复操作",
        f"M. 切换移动模式 (当前: {move_status})", f"P. 切换预览模式 (当前: {dry_run_status})", "0. 退出"
    ]
    for opt in options: print(f"  {opt}")
    print()

def print_submenu(options_to_display: List[str]):
    """打印子菜单。"""
    print("\n--- 请选择要处理的文件类型 ---")
    for opt in options_to_display:
        print(f"  {opt}")
    print()

def main():
    """程序主循环。"""
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
                # 只有可以被重命名或在移动模式下可以被移动的类型，才在单功能模式下有意义
                types_to_process = [t for t in PROCESSING_ORDER if FILE_TYPE_DEFINITIONS[t]['naming_func'] is not _get_no_rename or MOVE_FILES]
                
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
                    
                    if sub_choice == '0': break
                    if sub_choice in submenu_map:
                        specific_type = submenu_map[sub_choice]
                        break
                    else:
                        print("无效的选项。")
                if not specific_type: continue
            
            path = get_path_from_user()
            if not path: continue
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
    if len(sys.argv) > 1:
        print("检测到拖放操作，将以 [全功能] 模式处理...")
        
        MOVE_FILES = False
        DRY_RUN = False
        
        for path in sys.argv[1:]:
            path = path.strip('"')
            
            if not os.path.exists(path):
                print(f"\n错误：路径 '{path}' 不存在，已跳过。")
                continue

            if os.path.isdir(path):
                target_path = path
            elif os.path.isfile(path):
                target_path = os.path.dirname(path)
            else:
                print(f"\n警告：路径 '{path}' 既不是文件也不是文件夹，已跳过。")
                continue

            print(f"\n--- 正在处理目标: {target_path} ---")
            if not is_safe_path(target_path):
                print("警告：检测到您选择的路径可能为 SillyTavern 用户数据目录，为避免破坏程序结构，已中止操作。")
                continue
            
            process_directory(target_path, specific_type=None)
        
        print("\n所有拖放任务处理完毕。")
        input("按 Enter 键退出...")

    else:
        main()
