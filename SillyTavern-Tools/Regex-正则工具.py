import os
import json
import re
import time
import collections
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

@dataclass
class OperationLog:
    type: str
    original_path: str
    new_path: str
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProcessResult:
    logs: List[OperationLog] = field(default_factory=list)
    processed: int = 0
    skipped: int = 0
    marked: int = 0
    failed: int = 0

class ConsoleReporter:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    def start_phase(self, title: str):
        print(f"\n>> {title}\n")

    def report_duplicates(self, paths: List[str]):
        print("[分析] 发现内容完全重复的脚本:")
        for path in paths:
            print(f"  - {os.path.relpath(path, self.root_dir)}")
        print()

    def start_folder(self, folder_name: str):
        print(f"处理文件夹: '{folder_name}'")

    def report_folder_skipped(self):
        print("  此文件夹所有有效文件均已正确标记，无需操作。\n")

    def report_error(self, message: str):
        print(f"  [错误] {message}")

    def report_undo_success(self, old: str, new: str):
        print(f"  [撤销] '{new}' -> '{old}'")

    def report_undo_skip(self, reason: str):
        print(f"  [跳过] {reason}")

def load_and_validate_regex_json(filepath: str) -> Optional[Dict]:
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        if all(key in data for key in [
            "scriptName", "findRegex", "replaceString", "disabled",
            "markdownOnly", "promptOnly", "runOnEdit"
        ]):
            return data
        return None
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None

def sanitize_filename(name: str) -> str:
    if not name: return "未命名"
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()

def find_unique_filepath(filepath: str) -> str:
    if not os.path.exists(filepath): return filepath
    base, ext = os.path.splitext(filepath)
    i = 1
    while True:
        new_filepath = f"{base}_{i}{ext}"
        if not os.path.exists(new_filepath): return new_filepath
        i += 1

class RegexFileProcessor:
    def __init__(self, folders: List[str], reporter: ConsoleReporter):
        self.folders = folders
        self.reporter = reporter

    def detect_duplicates(self) -> ProcessResult:
        self.reporter.start_phase("阶段一：检测重复")
        result = ProcessResult()
        regex_map = collections.defaultdict(list)
        for folder in self.folders:
            for filename in os.listdir(folder):
                if not filename.endswith('.json'): continue
                filepath = os.path.join(folder, filename)
                data = load_and_validate_regex_json(filepath)
                if not data: continue
                flags = (data.get('disabled', False), data.get('markdownOnly', False), data.get('promptOnly', True), data.get('runOnEdit', True))
                key = (data['findRegex'], data['replaceString'], flags)
                regex_map[key].append(filepath)
        
        for _, paths in regex_map.items():
            if len(paths) > 1:
                sorted_paths = sorted(paths)
                self.reporter.report_duplicates(sorted_paths)
                for path_to_mark in sorted_paths[1:]:
                    if "_DUPLICATE" in os.path.basename(path_to_mark): continue
                    base, ext = os.path.splitext(path_to_mark)
                    new_path = find_unique_filepath(f"{base}_DUPLICATE{ext}")
                    try:
                        os.rename(path_to_mark, new_path)
                        log = OperationLog("rename_only", path_to_mark, new_path)
                        result.logs.append(log)
                        result.marked += 1
                    except OSError as e:
                        result.failed += 1
                        self.reporter.report_error(f"标记文件 '{os.path.basename(path_to_mark)}' 失败: {e}")
        return result

    def apply_tags(self) -> ProcessResult:
        self.reporter.start_phase("阶段二：添加标签")
        def _add_tag_transform(data: Dict, tag: str) -> Optional[Dict]:
            original_name = data.get("scriptName", "")
            expected_prefix = f"【{tag}】"
            if original_name.startswith(expected_prefix): return None
            sanitized_name = re.sub(r'^【.*?】[-_\s]*', '', original_name).strip()
            data['scriptName'] = f"{expected_prefix}-{sanitized_name}"
            return data
        return self._process_folders(_add_tag_transform)

    def remove_tags(self) -> ProcessResult:
        self.reporter.start_phase("阶段二：移除标签")
        def _remove_tag_transform(data: Dict, _: str) -> Optional[Dict]:
            original_name = data.get("scriptName", "")
            modified_name = re.sub(r'^【.*?】[-_\s]*', '', original_name).strip()
            modified_name = re.sub(r'[-_\s]+', '-', modified_name).strip('-')
            if modified_name == original_name: return None
            data['scriptName'] = modified_name
            return data
        return self._process_folders(_remove_tag_transform)

    def _process_folders(self, transform_func: Callable) -> ProcessResult:
        result = ProcessResult()
        for folder in self.folders:
            self.reporter.start_folder(os.path.basename(folder))
            tag = os.path.basename(folder)
            files_in_folder = [f for f in os.listdir(folder) if f.endswith('.json') and "_DUPLICATE" not in f]
            processed_in_folder = 0

            for filename in files_in_folder:
                filepath = os.path.join(folder, filename)
                data = load_and_validate_regex_json(filepath)
                if not data:
                    result.skipped += 1
                    continue

                original_script_name = data.get("scriptName", os.path.splitext(filename)[0])
                modified_data = transform_func(data.copy(), tag)
                if not modified_data:
                    result.skipped += 1
                    continue

                new_script_name = modified_data['scriptName']
                new_filename_base = sanitize_filename(f"正则-{new_script_name}") + ".json"
                new_path = find_unique_filepath(os.path.join(folder, new_filename_base))
                
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(modified_data, f, indent=2, ensure_ascii=False)
                    if filepath.lower() != new_path.lower():
                        os.rename(filepath, new_path)
                    
                    log = OperationLog("rename_and_modify", filepath, new_path, {"original_script_name": original_script_name})
                    result.logs.append(log)
                    result.processed += 1
                    processed_in_folder += 1
                except OSError as e:
                    result.failed += 1
                    self.reporter.report_error(f"处理文件 '{filename}' 失败: {e}")
            
            if processed_in_folder == 0 and files_in_folder:
                self.reporter.report_folder_skipped()
        return result

class OperationManager:
    def __init__(self, log_path: Optional[str] = None):
        self.log_path = log_path
        self.log_data = self._load_log() if log_path else []

    def _load_log(self) -> List[Dict]:
        try:
            with open(self.log_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return []

    def save_log(self, logs: List[OperationLog]) -> Optional[str]:
        if not logs: return None
        os.makedirs("log-Regex", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"log_{timestamp}.json"
        log_path = os.path.join("log-Regex", log_filename)
        try:
            log_data_to_save = [log.__dict__ for log in logs]
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data_to_save, f, indent=2, ensure_ascii=False)
            return log_path
        except OSError:
            return None

    def execute_undo(self, reporter: ConsoleReporter) -> ProcessResult:
        result = ProcessResult()
        if not self.log_data: return result
        
        for entry_data in reversed(self.log_data):
            log = OperationLog(**entry_data)
            new_basename = os.path.basename(log.new_path)
            original_basename = os.path.basename(log.original_path)

            if not os.path.exists(log.new_path):
                reporter.report_undo_skip(f"目标文件不存在: {new_basename}")
                result.skipped += 1
                continue
            if os.path.exists(log.original_path) and log.original_path.lower() != log.new_path.lower():
                reporter.report_undo_skip(f"原始路径已存在文件: {original_basename}")
                result.skipped += 1
                continue
            
            undo_handler = getattr(self, f"_undo_{log.type}", None)
            if undo_handler and undo_handler(log):
                reporter.report_undo_success(original_basename, new_basename)
                result.processed += 1
            else:
                reporter.report_error(f"撤销 '{new_basename}' 失败")
                result.failed += 1
        return result

    def _undo_rename_and_modify(self, log: OperationLog) -> bool:
        try:
            with open(log.new_path, 'r+', encoding='utf-8') as f:
                file_data = json.load(f)
                file_data['scriptName'] = log.details['original_script_name']
                f.seek(0)
                f.truncate()
                json.dump(file_data, f, indent=2, ensure_ascii=False)
            if log.original_path.lower() != log.new_path.lower():
                os.rename(log.new_path, log.original_path)
            return True
        except (OSError, json.JSONDecodeError, KeyError):
            return False

    def _undo_rename_only(self, log: OperationLog) -> bool:
        try:
            os.rename(log.new_path, log.original_path)
            return True
        except OSError:
            return False

    def delete_log(self):
        if not self.log_path: return
        try:
            os.remove(self.log_path)
            print("日志文件已删除。")
        except OSError as e:
            print(f"删除日志文件失败: {e}")

class AppUI:
    def __init__(self):
        self.use_gui = True

    def toggle_mode(self):
        self.use_gui = not self.use_gui
        mode_text = "图形模式 (Tkinter)" if self.use_gui else "命令行模式 (Termux/CLI适用)"
        print(f"\n模式已切换为: {mode_text}")
        time.sleep(1)

    def display_main_menu(self) -> str:
        print("\n" + "=" * 35)
        print("    正则脚本文件批量处理器 v4.0")
        print("=" * 35)
        mode_text = "图形模式" if self.use_gui else "命令行模式"
        print(f"当前UI模式: {mode_text}\n")
        print("1. [添加标签] 处理单个文件夹")
        print("2. [添加标签] 批量处理所有子文件夹")
        print("3. [移除标签] 批量处理所有子文件夹")
        print("4. [撤销操作] 从日志文件恢复")
        print("0. 退出")
        return input("\n请选择 (0-4), 或输入 't' 切换UI模式: ").strip().lower()

    def get_folder_selection(self, single_mode: bool) -> Optional[List[str]]:
        if self.use_gui:
            return self._get_folders_gui(single_mode)
        return self._get_folders_cli(single_mode)

    def _get_folders_gui(self, single_mode: bool) -> Optional[List[str]]:
        try:
            import tkinter as tk
            from tkinter import filedialog
        except ImportError:
            print("\n[错误] Tkinter 图形库未安装或无法加载。将使用命令行模式。")
            return self._get_folders_cli(single_mode)
        
        root = tk.Tk()
        root.withdraw()
        if single_mode:
            target_dir = filedialog.askdirectory(title="请选择一个包含正则文件的子文件夹")
            return [target_dir] if target_dir else None
        else:
            root_dir = filedialog.askdirectory(title="请选择包含多个正则子文件夹的根目录")
            if not root_dir: return None
            return [
                os.path.join(root_dir, d) for d in os.listdir(root_dir)
                if os.path.isdir(os.path.join(root_dir, d)) and d != "log-Regex" and not d.startswith('.')
            ]

    def _get_folders_cli(self, single_mode: bool) -> Optional[List[str]]:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"\n将在以下目录中查找文件夹: {script_dir}")
        try:
            all_dirs = sorted([
                d for d in os.listdir(script_dir)
                if os.path.isdir(os.path.join(script_dir, d)) and d != "log-Regex" and not d.startswith('.')
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
        
        prompt = f"\n请输入单个数字 (1-{len(all_dirs)}): " if single_mode else f"\n请选择 (可输入范围如 1-3, 多个用空格隔开如 1 3, 或输入 'a' 全选): "
        user_input = input(prompt).strip().lower()
        if not user_input: return None
        
        if user_input in ['a', 'all']:
            selected_indices = list(range(len(all_dirs)))
        else:
            indices = set()
            parts = user_input.replace(',', ' ').split()
            for part in parts:
                part = part.strip()
                if not part: continue
                try:
                    if '-' in part:
                        start, end = map(int, part.split('-', 1))
                        if start > end: start, end = end, start
                        indices.update(range(start - 1, end))
                    else:
                        indices.add(int(part) - 1)
                except ValueError:
                    print(f"[警告] 已忽略无效输入部分: '{part}'")
            selected_indices = sorted([i for i in indices if 0 <= i < len(all_dirs)])
        
        if not selected_indices: return None
        if single_mode and len(selected_indices) > 1:
            selected_indices = [selected_indices[0]]
        return [os.path.join(script_dir, all_dirs[i]) for i in selected_indices]

    def select_log_file(self) -> Optional[str]:
        if not os.path.isdir("log-Regex") or not os.listdir("log-Regex"):
            print("未找到日志文件夹或其中没有任何日志文件。")
            return None
        log_files = sorted([f for f in os.listdir("log-Regex") if f.startswith('log_') and f.endswith('.json')], reverse=True)
        if not log_files:
            print("未找到可用的日志文件。")
            return None
        print("\n请选择要用于撤销操作的日志文件:")
        for i, filename in enumerate(log_files): print(f"  {i + 1}. {filename}")
        print("  0. 返回主菜单")
        try:
            choice = int(input(f"请选择 (0-{len(log_files)}): "))
            if choice == 0: return None
            return os.path.join("log-Regex", log_files[choice - 1])
        except (ValueError, IndexError):
            print("无效输入或选择。")
            return None

    def confirm_action(self, prompt: str) -> bool:
        return input(prompt).lower() == 'y'

    def report_results(self, title: str, result: ProcessResult, dup_result: Optional[ProcessResult] = None):
        print(f"\n--- {title} ---")
        marked = dup_result.marked if dup_result else 0
        processed = result.processed
        skipped = result.skipped
        failed = result.failed + (dup_result.failed if dup_result else 0)
        print(f"总计: 标记 {marked} 个重复文件, 处理 {processed} 个文件, 跳过 {skipped} 个, 失败 {failed} 个。")

    def report_undo_result(self, result: ProcessResult):
        print(f"\n--- 撤销总结 ---")
        print(f"总计: {result.processed} 个成功, {result.skipped} 个跳过, {result.failed} 个失败。")

def main():
    ui = AppUI()
    op_manager = OperationManager()

    while True:
        choice = ui.display_main_menu()
        folders = None
        if choice in ['1', '2', '3']:
            folders = ui.get_folder_selection(single_mode=(choice == '1'))
            if not folders:
                print("未选择任何文件夹，操作取消。")
                continue
            print("\n已选择以下文件夹进行处理:")
            for path in folders: print(f"  - {os.path.basename(path)}")
        
        if choice in ['1', '2']:
            root_dir = os.path.dirname(folders[0]) if folders else '.'
            reporter = ConsoleReporter(root_dir)
            processor = RegexFileProcessor(folders, reporter=reporter)
            
            dup_result = processor.detect_duplicates()
            tag_result = processor.apply_tags()
            ui.report_results("任务总结", tag_result, dup_result)
            
            all_logs = dup_result.logs + tag_result.logs
            log_path = op_manager.save_log(all_logs)
            if log_path: print(f"\n[日志] 操作记录已保存至: {os.path.relpath(log_path)}")

        elif choice == '3':
            root_dir = os.path.dirname(folders[0]) if folders else '.'
            reporter = ConsoleReporter(root_dir)
            processor = RegexFileProcessor(folders, reporter=reporter)
            result = processor.remove_tags()
            ui.report_results("任务总结", result)
            log_path = op_manager.save_log(result.logs)
            if log_path: print(f"\n[日志] 操作记录已保存至: {os.path.relpath(log_path)}")

        elif choice == '4':
            log_file = ui.select_log_file()
            if log_file:
                undo_manager = OperationManager(log_file)
                if not undo_manager.log_data:
                    print("日志文件为空或无法读取，操作取消。")
                    continue
                if ui.confirm_action(f"\n将从 '{os.path.basename(log_file)}' 撤销 {len(undo_manager.log_data)} 个操作。您确定吗? (y/n): "):
                    root_dir = os.path.dirname(os.path.dirname(log_file))
                    reporter = ConsoleReporter(root_dir)
                    result = undo_manager.execute_undo(reporter)
                    ui.report_undo_result(result)
                    if ui.confirm_action(f"是否删除已使用的日志文件 '{os.path.basename(log_file)}'? (y/n): "):
                        undo_manager.delete_log()
        
        elif choice == 't':
            ui.toggle_mode()
        elif choice == '0':
            print("程序已退出。")
            break
        else:
            print("无效的选项，请重新输入。")

if __name__ == "__main__":
    main()
