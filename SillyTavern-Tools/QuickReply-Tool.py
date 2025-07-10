import json
import os
import re
import sys
import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

class InvalidQuickReplyError(ValueError):
    """当QuickReply文件或其内容无效时抛出此异常"""
    pass

@dataclass
class Config:
    # 默认文件编码
    DEFAULT_ENCODING: str = 'utf-8'
    # 隐藏文件的前缀
    HIDDEN_FILE_PREFIX: str = "!"
    # 提取/合并的文件扩展名
    FILE_EXTENSION: str = ".txt"
    # 文件名中的非法字符正则表达式
    INVALID_FILENAME_CHARS: str = r'[\\/*?:"<>|]'
    # 合并时默认的QR版本号
    QR_VERSION: int = 2
    # 根JSON对象必须包含的键
    QR_REQUIRED_KEYS: List[str] = field(default_factory=lambda: ["version", "name", "qrList"])
    # qrList中每个条目必须包含的键
    QR_ITEM_REQUIRED_KEYS: List[str] = field(default_factory=lambda: ["id", "label", "message", "isHidden"])

class QuickReplyItem:
    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @property
    def label(self) -> str:
        return self._data.get("label", "")

    @property
    def message(self) -> str:
        return self._data.get("message", "")

    @message.setter
    def message(self, value: str):
        self._data["message"] = value

    @property
    def is_hidden(self) -> bool:
        return self._data.get("isHidden", False)

    def to_dict(self) -> Dict[str, Any]:
        return self._data

class QuickReplyData:
    def __init__(self, data: Dict[str, Any], source_path: Path):
        self._data = data
        self.source_path = source_path
        self.items = [QuickReplyItem(item_data) for item_data in self._data.get("qrList", [])]

    @property
    def name(self) -> str:
        return self._data.get("name", "")

    @classmethod
    def from_file(cls, file_path: Path, config: Config) -> 'QuickReplyData':
        try:
            with file_path.open('r', encoding=config.DEFAULT_ENCODING) as f:
                data = json.load(f)
        except FileNotFoundError:
            raise InvalidQuickReplyError(f"文件未找到: {file_path}")
        except json.JSONDecodeError as e:
            raise InvalidQuickReplyError(f"JSON解析错误在文件 {file_path}: {e}")
        except OSError as e:
            raise InvalidQuickReplyError(f"无法读取文件 {file_path}: {e}")

        if not isinstance(data, dict) or not all(key in data for key in config.QR_REQUIRED_KEYS):
            raise InvalidQuickReplyError(f"文件 {file_path.name} 缺少必须的根键。")

        for item_data in data.get("qrList", []):
            if not isinstance(item_data, dict) or not all(key in item_data for key in config.QR_ITEM_REQUIRED_KEYS):
                raise InvalidQuickReplyError(f"文件 {file_path.name} 中包含缺少必须键的条目。")

        return cls(data=data, source_path=file_path)

    def to_dict(self) -> Dict[str, Any]:
        return self._data

@dataclass
class ProcessResult:
    successes: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __str__(self):
        lines = []
        if self.successes:
            lines.append(f"成功 ({len(self.successes)}):")
            lines.extend([f"  - {s}" for s in self.successes])
        if self.failures:
            lines.append(f"失败 ({len(self.failures)}):")
            lines.extend([f"  - {f}" for f in self.failures])
        if self.warnings:
            lines.append(f"警告 ({len(self.warnings)}):")
            lines.extend([f"  - {w}" for w in self.warnings])
        if not lines:
            return "未执行任何操作。"
        return "\n".join(lines)

class QuickReplyService:
    def __init__(self, config: Config):
        self.config = config

    def _sanitize_filename(self, name: str) -> str:
        return re.sub(self.config.INVALID_FILENAME_CHARS, '', name)

    def _write_json(self, data: Dict, path: Path) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding=self.config.DEFAULT_ENCODING) as f:
                json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
            return True
        except OSError:
            return False
        
    def extract(self, qr_data: QuickReplyData, base_dir: Path) -> ProcessResult:
        result = ProcessResult()
        folder_path = base_dir / self._sanitize_filename(qr_data.name)
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            result.failures.append(f"创建目录失败 '{folder_path}': {e}")
            return result

        for item in qr_data.items:
            if not item.label:
                result.warnings.append(f"跳过一个没有标签的条目。")
                continue
            safe_label = self._sanitize_filename(item.label)
            prefix = self.config.HIDDEN_FILE_PREFIX if item.is_hidden else ""
            file_path = folder_path / f"{prefix}{safe_label}{self.config.FILE_EXTENSION}"
            try:
                file_path.write_text(item.message.replace('\\n', '\n'), encoding=self.config.DEFAULT_ENCODING)
                result.successes.append(f"已提取: {file_path.relative_to(base_dir)}")
            except OSError as e:
                result.failures.append(f"创建文件失败 '{file_path}': {e}")
        return result

    def merge(self, directory: Path, output_path: Path) -> ProcessResult:
        result = ProcessResult()
        if not directory.is_dir():
            result.failures.append(f"目录不存在: {directory}")
            return result

        txt_files = sorted(list(directory.glob(f"*{self.config.FILE_EXTENSION}")))
        if not txt_files:
            result.warnings.append(f"目录 '{directory}' 中未找到TXT文件。")
            return result

        qr_list = []
        id_counter = 1
        for file_path in txt_files:
            try:
                content = file_path.read_text(encoding=self.config.DEFAULT_ENCODING)
                is_hidden = file_path.name.startswith(self.config.HIDDEN_FILE_PREFIX)
                label_start = len(self.config.HIDDEN_FILE_PREFIX) if is_hidden else 0
                label = file_path.stem[label_start:]

                item_data = {
                    "id": id_counter,
                    "showLabel": False,
                    "label": label,
                    "title": "",
                    "message": content,
                    "contextList": [],
                    "preventAutoExecute": True,
                    "isHidden": is_hidden,
                    "executeOnStartup": False,
                    "executeOnUser": False,
                    "executeOnAi": False,
                    "executeOnChatChange": False,
                    "executeOnGroupMemberDraft": False,
                    "executeOnNewChat": False,
                    "automationId": ""
                }
                qr_list.append(item_data)
                result.successes.append(f"已读取: {file_path.name}")
                id_counter += 1
            except OSError as e:
                result.failures.append(f"读取文件失败 '{file_path.name}': {e}")

        output_data = {
            "version": self.config.QR_VERSION,
            "name": directory.name,
            "disableSend": False,
            "placeBeforeInput": False,
            "injectInput": False,
            "color": "rgba(0, 0, 0, 0)",
            "onlyBorderColor": False,
            "qrList": qr_list,
            "idIndex": id_counter
        }

        if self._write_json(output_data, output_path):
            result.successes.append(f"成功创建JSON: {output_path.relative_to(directory.parent)}")
        else:
            result.failures.append(f"写入JSON失败: {output_path}")
        return result

    def push(self, qr_data: QuickReplyData, directory: Path) -> ProcessResult:
        result = ProcessResult()
        if not directory.is_dir():
            result.failures.append(f"目录不存在: {directory}")
            return result

        file_contents = {}
        for file_path in directory.glob(f"*{self.config.FILE_EXTENSION}"):
            try:
                label_start = len(self.config.HIDDEN_FILE_PREFIX) if file_path.name.startswith(self.config.HIDDEN_FILE_PREFIX) else 0
                label = file_path.stem[label_start:]
                file_contents[label] = file_path.read_text(encoding=self.config.DEFAULT_ENCODING)
            except OSError as e:
                result.failures.append(f"读取文件失败 '{file_path.name}': {e}")

        if not file_contents and not result.failures:
            result.warnings.append(f"目录 '{directory.name}' 中没有可用于推送的 .txt 文件。")
            return result

        updated_count = 0
        for item in qr_data.items:
            if item.label in file_contents:
                new_content = file_contents[item.label]
                if item.message != new_content:
                    item.message = new_content
                    updated_count += 1
                    result.successes.append(f"准备更新标签: '{item.label}'")

        if updated_count > 0:
            if self._write_json(qr_data.to_dict(), qr_data.source_path):
                result.successes.append(f"成功更新 {updated_count} 个条目到 {qr_data.source_path.name}")
            else:
                result.failures.append(f"写入更新失败: {qr_data.source_path.name}")
        else:
            result.warnings.append("没有找到内容发生变化的匹配标签进行更新。")
        return result

class AppUI:
    def display_main_menu(self) -> str:
        print("\n" + "="*20)
        print("  QuickReply 工具箱")
        print("="*20)
        print("\n请选择要执行的操作:")
        print("  1. 提取 (将 .json 文件解包成 .txt 文件)")
        print("  2. 合并 (将文件夹内的 .txt 文件打包成新 .json)")
        print("  3. 推送 (用 .txt 文件内容更新已有的 .json)")
        print("  0. 退出")
        return input("\n请输入选项 (0-3): ")

    def select_from_list(self, items: List[Path], prompt: str) -> Optional[Path]:
        if not items:
            self.display_message("列表为空，无法选择。", is_error=True)
            return None
        print(prompt)
        for i, item in enumerate(items):
            print(f"  {i + 1}. {item.name}")
        while True:
            try:
                choice_str = input(f"请输入编号 (1-{len(items)})，或输入 0 返回: ")
                if not choice_str: continue
                choice = int(choice_str)
                if choice == 0: return None
                if 1 <= choice <= len(items): return items[choice - 1]
                else: print("无效的编号，请重新输入。")
            except ValueError:
                print("无效的输入，请输入数字。")

    def report_results(self, title: str, result: ProcessResult):
        print(f"\n--- {title} 执行结果 ---")
        print(result)
        print("--------------------------")

    def display_message(self, message: str, is_error: bool = False):
        prefix = "错误: " if is_error else ""
        print(f"\n{prefix}{message}")

class Application:
    def __init__(self, ui: AppUI, service: QuickReplyService, config: Config):
        self.ui = ui
        self.service = service
        self.config = config
        try:
            self.base_dir = Path(sys.argv[0]).parent.resolve() if getattr(sys, 'frozen', False) else Path(__file__).parent.resolve()
        except NameError:
            self.base_dir = Path.cwd()

    def _get_valid_qr_files(self) -> List[Path]:
        valid_files = []
        for f in self.base_dir.glob('*.json'):
            try:
                QuickReplyData.from_file(f, self.config)
                valid_files.append(f)
            except InvalidQuickReplyError:
                continue
        return valid_files

    def _get_valid_folders(self) -> List[Path]:
        return [d for d in self.base_dir.iterdir() if d.is_dir() and any(d.glob(f"*{self.config.FILE_EXTENSION}"))]

    def run_interactive(self):
        while True:
            choice = self.ui.display_main_menu()
            if choice == "1": self.handle_extract_interactive()
            elif choice == "2": self.handle_merge_interactive()
            elif choice == "3": self.handle_push_interactive()
            elif choice == "0": self.ui.display_message("退出程序。"); break
            else: self.ui.display_message("无效的选项，请重新输入。")

    def handle_extract_interactive(self):
        valid_files = self._get_valid_qr_files()
        if not valid_files: self.ui.display_message("未找到有效的 QuickReply JSON 文件。"); return
        selected_file = self.ui.select_from_list(valid_files, "\n请选择要提取的JSON文件：")
        if selected_file: self.run_extract(selected_file)

    def handle_merge_interactive(self):
        valid_folders = self._get_valid_folders()
        if not valid_folders: self.ui.display_message("当前目录下没有包含 .txt 文件的文件夹。"); return
        selected_folder = self.ui.select_from_list(valid_folders, "\n请选择要合并的文件夹：")
        if selected_folder: self.run_merge(selected_folder)

    def handle_push_interactive(self):
        valid_files = self._get_valid_qr_files()
        if not valid_files: self.ui.display_message("未找到有效的 QuickReply JSON 文件。"); return
        selected_file = self.ui.select_from_list(valid_files, "\n请选择要更新的目标JSON文件：")
        if not selected_file: return

        valid_folders = self._get_valid_folders()
        if not valid_folders: self.ui.display_message("当前目录下没有包含 .txt 文件的文件夹。"); return
        selected_folder = self.ui.select_from_list(valid_folders, "\n请选择包含更新内容的源文件夹：")
        if selected_folder: self.run_push(selected_file, selected_folder)

    def _load_qr_data(self, file_path: Path) -> Optional[QuickReplyData]:
        try:
            return QuickReplyData.from_file(file_path, self.config)
        except InvalidQuickReplyError as e:
            self.ui.display_message(f"无法加载文件 {file_path.name}: {e}", is_error=True)
            return None

    def run_extract(self, file_path: Path):
        qr_data = self._load_qr_data(file_path)
        if qr_data:
            result = self.service.extract(qr_data, self.base_dir)
            self.ui.report_results(f"提取 '{file_path.name}'", result)

    def run_merge(self, dir_path: Path):
        output_name = f"QuickReply-{dir_path.name}.json"
        output_path = self.base_dir / output_name
        result = self.service.merge(dir_path, output_path)
        self.ui.report_results(f"合并 '{dir_path.name}'", result)

    def run_push(self, file_path: Path, dir_path: Path):
        qr_data = self._load_qr_data(file_path)
        if qr_data:
            result = self.service.push(qr_data, dir_path)
            self.ui.report_results(f"推送 '{dir_path.name}' -> '{file_path.name}'", result)

def main():
    parser = argparse.ArgumentParser(
        description="一个用于提取、合并和更新 QuickReply JSON 的工具。",
        epilog="如果没有提供任何命令，程序将进入交互模式。"
    )
    subparsers = parser.add_subparsers(dest="command", help="可用的命令")

    parser_extract = subparsers.add_parser("extract", help="从 QuickReply JSON 提取到文件")
    parser_extract.add_argument("file", type=Path, help="要提取的 QuickReply JSON 文件路径")

    parser_merge = subparsers.add_parser("merge", help="从文件合并到新的 QuickReply JSON")
    parser_merge.add_argument("directory", type=Path, help="包含 .txt 文件的目录路径")

    parser_push = subparsers.add_parser("push", help="从文件更新 QuickReply JSON")
    parser_push.add_argument("json_file", type=Path, help="要更新的 QuickReply JSON 文件路径")
    parser_push.add_argument("directory", type=Path, help="包含更新内容的 .txt 文件目录路径")

    args = parser.parse_args()

    config = Config()
    service = QuickReplyService(config)
    ui = AppUI()
    app = Application(ui, service, config)

    try:
        if args.command == "extract":
            app.run_extract(args.file.resolve())
        elif args.command == "merge":
            app.run_merge(args.directory.resolve())
        elif args.command == "push":
            app.run_push(args.json_file.resolve(), args.directory.resolve())
        else:
            app.run_interactive()
    except Exception as e:
        ui.display_message(f"发生了一个意外错误: {e}", is_error=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
