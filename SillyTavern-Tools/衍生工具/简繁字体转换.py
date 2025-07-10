import json
import sys
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path
from collections import Counter
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import filedialog
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

try:
    import opencc
    import yaml
except ImportError:
    print("错误：缺少必要的库。\n请先通过 pip 安装 'opencc-python-rebuilt' 和 'PyYAML'。\n命令: pip install opencc-python-rebuilt PyYAML")
    sys.exit(1)

CHINESE_CHARS_RE = re.compile(r"[\u4e00-\u9fff]")
OUTPUT_BASE_DIR_NAME = "字体转化"

YAML_HANDLER = {'load': yaml.safe_load, 'dump': lambda data: yaml.dump(data, allow_unicode=True, sort_keys=False)}
FILE_HANDLERS = {
    '.json': {'load': json.loads, 'dump': lambda data: json.dumps(data, ensure_ascii=False, indent=4)},
    '.yaml': YAML_HANDLER,
    '.yml': YAML_HANDLER,
    '.txt': {'load': lambda text: text, 'dump': lambda text: text},
    '.md': {'load': lambda text: text, 'dump': lambda text: text},
}
SUPPORTED_EXTENSIONS = tuple(FILE_HANDLERS.keys())
SUPPORTED_EXTENSIONS_DESC = " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS)

MODES_CONFIG = {
    '1': {'type': 'conversion', 'desc': "繁体 -> 简体 转换", 'config': 't2s', 'suffix': '_简体'},
    '2': {'type': 'conversion', 'desc': "简体 -> 繁体 转换", 'config': 's2t', 'suffix': '_繁体'},
    '3': {'type': 'counting', 'desc': "统计汉字个数"},
}

@dataclass
class ProcessResult:
    status: str
    input_path: Path
    changes: int = 0
    diff_data: Optional[Dict[str, str]] = None
    char_count: Optional[int] = None

class FileProcessor:
    def __init__(self, mode: str, tasks: List[Dict], script_dir: Path, base_name: str):
        self.mode_config = MODES_CONFIG[mode]
        self.tasks = tasks
        self.script_dir = script_dir
        self.base_name = base_name
        self.stats = Counter()
        self.all_conversion_diffs = {}
        self.total_changed_chars = 0
        self.total_counted_chars = 0
        self.lock = threading.Lock()
        self.converter = self._setup_converter()
        self.final_output_dir = self._setup_output_dir()

    def _setup_converter(self) -> Optional[opencc.OpenCC]:
        if self.mode_config['type'] == 'conversion':
            return opencc.OpenCC(self.mode_config['config'])
        return None

    def _setup_output_dir(self) -> Optional[Path]:
        if self.mode_config['type'] == 'conversion':
            output_dir_name = f"{self.base_name}{self.mode_config['suffix']}"
            return self.script_dir / OUTPUT_BASE_DIR_NAME / output_dir_name
        return None

    def run(self):
        print(f"\n已选择: {self.mode_config['desc']}")
        if self.final_output_dir:
            print(f"结果将保存至: {self.final_output_dir}\n")
        
        workflow = self._run_conversion_workflow if self.mode_config['type'] == 'conversion' else self._run_counting_workflow
        workflow()
        
        if self.mode_config['type'] == 'conversion' and self.all_conversion_diffs:
            self._write_diff_log()
        
        self._print_summary_report()

    def _run_conversion_workflow(self):
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(self._process_file_for_conversion, task['input']): task for task in self.tasks}
            for future in as_completed(futures):
                result = future.result()
                with self.lock:
                    self.stats[result.status] += 1
                    if result.status == 'success':
                        self.total_changed_chars += result.changes
                        if result.diff_data:
                            relative_path = result.input_path.relative_to(self.script_dir) if result.input_path.is_relative_to(self.script_dir) else result.input_path
                            self.all_conversion_diffs[str(relative_path)] = result.diff_data

    def _run_counting_workflow(self):
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(self._count_chars_in_file, task['input']): task for task in self.tasks}
            for future in as_completed(futures):
                result = future.result()
                with self.lock:
                    if result.char_count is not None:
                        self.stats['success'] += 1
                        self.total_counted_chars += result.char_count
                    else:
                        self.stats['fail'] += 1

    def _process_file_for_conversion(self, input_path: Path) -> ProcessResult:
        print(f"- 正在处理: {input_path.name}")
        output_path = self.final_output_dir / input_path.name
        try:
            handler = FILE_HANDLERS.get(input_path.suffix.lower())
            if not handler: return ProcessResult(status='unsupported', input_path=input_path)

            original_content = input_path.read_text(encoding='utf-8')
            if not self._needs_conversion_check(original_content):
                print(f"  └─ {input_path.name}: 无需转换。")
                return ProcessResult(status='no_change', input_path=input_path)

            original_data = handler['load'](original_content)
            converted_data, change_count, diffs_list = self._convert_structured_data(original_data)

            if change_count == 0:
                print(f"  └─ {input_path.name}: 无实际变化。")
                return ProcessResult(status='no_change', input_path=input_path)

            converted_content_str = handler['dump'](converted_data)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(converted_content_str, encoding='utf-8')
            print(f"  └─ {input_path.name}: 转换成功 (共 {change_count} 个字符)。")

            aggregated_diff = {'original': "".join(d['original'] for d in diffs_list), 'converted': "".join(d['converted'] for d in diffs_list)} if diffs_list else None
            return ProcessResult(status='success', changes=change_count, diff_data=aggregated_diff, input_path=input_path)
        except Exception as e:
            print(f"  └─ 错误: 处理 {input_path.name} 时发生错误: {e}")
            return ProcessResult(status='fail', input_path=input_path)

    def _needs_conversion_check(self, content: str) -> bool:
        unique_chars = "".join(set(CHINESE_CHARS_RE.findall(content)))
        return unique_chars and self.converter.convert(unique_chars) != unique_chars

    def _convert_structured_data(self, data: Any) -> Tuple[Any, int, List[Dict[str, str]]]:
        if isinstance(data, dict):
            new_dict, total_changes, all_diffs = {}, 0, []
            for k, v in data.items():
                converted_v, changes, diffs = self._convert_structured_data(v)
                new_dict[k] = converted_v
                total_changes += changes
                all_diffs.extend(diffs)
            return new_dict, total_changes, all_diffs
        elif isinstance(data, list):
            new_list, total_changes, all_diffs = [], 0, []
            for item in data:
                converted_item, changes, diffs = self._convert_structured_data(item)
                new_list.append(converted_item)
                total_changes += changes
                all_diffs.extend(diffs)
            return new_list, total_changes, all_diffs
        elif isinstance(data, str):
            converted_text = self.converter.convert(data)
            diffs = [{'original': c1, 'converted': c2} for c1, c2 in zip(data, converted_text) if c1 != c2]
            return converted_text, len(diffs), diffs
        else:
            return data, 0, []

    def _count_chars_in_file(self, input_path: Path) -> ProcessResult:
        print(f"- 正在统计: {input_path.name}")
        try:
            count = len(CHINESE_CHARS_RE.findall(input_path.read_text(encoding='utf-8')))
            print(f"  └─ {input_path.name}: {count} 个汉字")
            return ProcessResult(status='success', input_path=input_path, char_count=count)
        except Exception as e:
            print(f"  └─ 错误: 无法读取 {input_path.name}: {e}")
            return ProcessResult(status='fail', input_path=input_path)

    def _write_diff_log(self):
        diff_filename = f"{self.final_output_dir.name}_diff.yaml"
        diff_file_path = self.final_output_dir.parent / diff_filename
        try:
            with diff_file_path.open('w', encoding='utf-8') as f:
                yaml.dump(self.all_conversion_diffs, f, allow_unicode=True, sort_keys=False, indent=2)
            print(f"\n* 转换对比日志已保存至: {diff_file_path}")
        except Exception as e:
            print(f"\n* 错误: 无法写入转换对比日志文件: {e}")

    def _print_summary_report(self):
        print("\n==============================================")
        print(f"          {self.mode_config['desc']} 完成！")
        print("----------------------------------------------")
        total_processed = len(self.tasks)
        print(f"总共扫描文件: {total_processed}个")
        if self.mode_config['type'] == 'conversion':
            print(f"  - 转换成功: {self.stats['success']}个")
            print(f"  - 无需转换: {self.stats['no_change']}个")
            print(f"  - 处理失败: {self.stats['fail']}个")
            if self.stats['unsupported'] > 0: print(f"  - 不支持的文件类型: {self.stats['unsupported']}个")
            print("----------------------------------------------")
            if self.total_changed_chars > 0: print(f"总共转换字符: {self.total_changed_chars}个")
            if self.stats['success'] > 0: print(f"转换结果已保存至 '{self.final_output_dir}'")
        elif self.mode_config['type'] == 'counting':
            print(f"  - 统计成功: {self.stats['success']}个")
            print(f"  - 读取失败: {self.stats['fail']}个")
            print("----------------------------------------------")
            print(f"总计汉字数量: {self.total_counted_chars} 个")
        print("==============================================")

class UIManager:
    def __init__(self, script_dir: Path):
        self.script_dir = script_dir

    def display_intro(self, version_str="v4.5 - 并行优化版"):
        print("==============================================")
        print(f"  多功能文件处理工具 ({version_str})")
        print("==============================================")

    def get_mode_choice(self) -> str:
        print("请选择要执行的功能:")
        for key, config in MODES_CONFIG.items():
            print(f"  {key}. {config['desc']}")
        print("  0. 退出程序")
        
        mode_choice = ''
        valid_choices = list(MODES_CONFIG.keys()) + ['0']
        while mode_choice not in valid_choices:
            mode_choice = input(f"请输入功能编号 ({', '.join(valid_choices)}): ")
        if mode_choice == '0': sys.exit(0)
        return mode_choice

    def get_tasks_and_basename_interactive(self) -> Tuple[Optional[List[Dict]], Optional[str]]:
        items_in_dir = [item for item in self.script_dir.iterdir() if item.name not in (OUTPUT_BASE_DIR_NAME, Path(__file__).name)]
        process_options = []
        for item_path in sorted(items_in_dir, key=lambda p: (not p.is_dir(), p.name.lower())):
            if item_path.is_dir() or (item_path.is_file() and item_path.suffix.lower() in SUPPORTED_EXTENSIONS):
                process_options.append({'name': item_path.name, 'type': 'dir' if item_path.is_dir() else 'file', 'path': item_path})

        if not process_options and not TKINTER_AVAILABLE:
            print("\n错误：在脚本所在文件夹下未找到任何子文件夹或支持的文件，且Tkinter不可用。")
            return None, None

        print("\n请选择要进行处理的文件夹或文件:")
        for i, option in enumerate(process_options, 1):
            tag = "[文件夹]" if option['type'] == 'dir' else "[文  件]"
            print(f"  {i:2}. {tag} {option['name']}")
        
        if TKINTER_AVAILABLE: print(f"  {'t':>2}. [浏览..] 使用文件浏览器选择文件或文件夹")
        
        valid_choices = [str(i) for i in range(1, len(process_options) + 1)]
        if TKINTER_AVAILABLE: valid_choices.append('t')

        choice_str = ''
        while choice_str not in valid_choices:
            choice_str = input(f"请输入编号 (1-{len(process_options)}{', t' if TKINTER_AVAILABLE else ''}): ").lower()

        if choice_str == 't':
            return self._get_tasks_from_tkinter()
        else:
            selected_option = process_options[int(choice_str) - 1]
            tasks = self._collect_tasks_from_path(selected_option['path'])
            base_name = selected_option['name'] if selected_option['type'] == 'dir' else selected_option['path'].stem
            return tasks, base_name

    def _get_tasks_from_tkinter(self) -> Tuple[Optional[List[Dict]], Optional[str]]:
        root = tk.Tk()
        root.withdraw()
        
        print("\n请在弹出的对话框中选择文件或文件夹...")
        choice = input("要选择单个文件(f)还是整个文件夹(d)? [f/d]: ").lower()
        
        path_str = filedialog.askdirectory(title="请选择一个文件夹") if choice == 'd' else filedialog.askopenfilename(title="请选择一个文件", filetypes=[("支持的文件", SUPPORTED_EXTENSIONS_DESC), ("所有文件", "*.*")])
        
        if not path_str:
            print("未选择任何项目。")
            return None, None
            
        selected_path = Path(path_str)
        tasks = self._collect_tasks_from_path(selected_path)
        base_name = selected_path.name if selected_path.is_dir() else selected_path.stem
        return tasks, base_name

    @staticmethod
    def _collect_tasks_from_path(target_path: Path) -> List[Dict]:
        tasks = []
        if not target_path.exists():
            print(f"  - 警告: 路径不存在，已跳过 '{target_path}'")
            return tasks

        if target_path.is_dir():
            print(f"  - 正在递归搜索文件夹: {target_path.name}")
            for file_path in target_path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    tasks.append({'input': file_path})
            print(f"    └─ 在 '{target_path.name}' 中找到 {len(tasks)} 个支持的文件。")
        elif target_path.is_file():
            if target_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                tasks.append({'input': target_path})
                print(f"  - 已添加文件: {target_path.name}")
            else:
                print(f"  - 警告: 不支持的文件类型，已跳过 '{target_path.name}'")
        return tasks

def run_interactive_mode():
    script_dir = Path(__file__).resolve().parent
    ui = UIManager(script_dir)
    ui.display_intro()
    mode = ui.get_mode_choice()
    tasks, base_name = ui.get_tasks_and_basename_interactive()
    if not tasks: return
    processor = FileProcessor(mode, tasks, script_dir, base_name)
    processor.run()

def run_drag_drop_mode(dropped_paths: List[str]):
    script_dir = Path(__file__).resolve().parent
    ui = UIManager(script_dir)
    ui.display_intro("v4.5 - 拖放模式")
    
    tasks = []
    print("\n正在解析拖放的项目...")
    for path_str in dropped_paths:
        tasks.extend(UIManager._collect_tasks_from_path(Path(path_str)))

    if not tasks:
        print("\n未找到任何有效文件进行处理。")
        return

    mode = ui.get_mode_choice()
    base_name = Path(dropped_paths[0]).stem if len(dropped_paths) == 1 else f"DragDrop_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    processor = FileProcessor(mode, tasks, script_dir, base_name)
    processor.run()

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            run_drag_drop_mode(sys.argv[1:])
        else:
            run_interactive_mode()
    except (SystemExit, KeyboardInterrupt):
        print("\n程序已退出。")
    except Exception as e:
        print(f"\n发生未预料的严重错误: {e}")
    finally:
        input("\n按回车键退出。")
