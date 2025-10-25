import json
import os
import re
import sys
from typing import Optional, Dict, Any, List
from datetime import datetime

# ==============================================================================
#  部分 1: 世界书生成器 (文件夹 -> .json)
# ==============================================================================
class WorldbookGenerator:
    """根据配置文件夹，生成世界书 (.json) 文件。"""

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.source_texts_dir = os.path.join(self.root_dir, "source_texts")
        
        print("\n[生成器] 正在加载配置文件...")
        self.config = self._load_json_file(os.path.join(self.root_dir, "worldbook_rules.json"), "rules配置文件")
        self.keyword_mapping = self._load_json_file(os.path.join(self.root_dir, "keyword_mapping.json"), "关键词映射文件")
        
        self.rules = self.config.get("rules", [])
        self.processing_order = self.config.get("processing_order", [])
        self.pinned_files = self.config.get("pinned_files", [])

    @staticmethod
    def _load_json_file(file_path: str, file_description: str) -> dict:
        """加载并返回指定的JSON文件。"""
        if not os.path.exists(file_path):
            print(f"  警告: {file_description} ({file_path}) 未找到。将使用空设置。")
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                print(f"  成功加载 {file_description}")
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"  警告: 加载 {file_description} ({file_path}) 失败 - {e}。将使用空设置。")
            return {}

    def _find_rule_for_file(self, file_name: str) -> dict:
        """根据文件名匹配并返回最合适的规则。"""
        for rule in self.rules:
            if file_name in rule.get("identifiers", []):
                return rule
        return self.config.get("default", {})

    def _create_entry(self, info: dict, file_name: str) -> dict:
        """根据信息和规则创建条目。"""
        rule = self._find_rule_for_file(file_name)
        settings = rule.get("settings", {})
        
        entry = {
            "uid": info.get("uid"), "key": info.get("key", []), "keysecondary": info.get("keysecondary", []),
            "comment": info.get("comment", ""), "content": info.get("content", ""),
            "displayIndex": info.get("displayIndex"),
        }
        entry.update(settings)
        return entry

    def _extract_info(self, content: str, fileName: str, uid: int, displayIndex: int) -> dict:
        """从文件名和映射中提取信息。"""
        base_name = os.path.splitext(fileName)[0]
        
        mapping = self.keyword_mapping.get(fileName, {})
        key_list = mapping.get("key", [])
        keysecondary_list = mapping.get("keysecondary", [])

        return {
            "uid": uid, "key": key_list, "keysecondary": keysecondary_list,
            "comment": base_name, "content": content, "displayIndex": displayIndex,
        }

    def generate_worldbook(self, identifier: str = "Touhou"):
        """执行生成过程。"""
        print(f"\n[生成器] 开始生成世界书 (从 '{self.root_dir}')...")
        
        ordered_file_list = [f for f in self.processing_order if os.path.exists(os.path.join(self.source_texts_dir, f))]
        
        entries = {}
        uid_counter, display_index, total_files_processed = 1, 1, 0

        for file_name in ordered_file_list:
            file_path = os.path.join(self.source_texts_dir, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                info = self._extract_info(content, file_name, uid_counter, display_index)
                entry = self._create_entry(info, file_name)
                
                entries[str(uid_counter)] = entry
                uid_counter += 1
                display_index += 1
                total_files_processed += 1
                print(f"\r  处理中: {total_files_processed}/{len(ordered_file_list)} ({file_name})", end="")
            except Exception as e:
                print(f"\n  读取文件 {file_path} 失败: {e}")
                continue
        
        print("\n")
        worldbook_name = os.path.basename(self.root_dir)
        worldbook = {"name": worldbook_name, "entries": entries, "description": ""}
        output = json.dumps(worldbook, indent=2, ensure_ascii=False)

        timestamp = datetime.now().strftime("%m-%d-%M")
        
        # --- 智能前缀逻辑 ---
        prefix_to_add = f"「{identifier}」-"
        if worldbook_name.startswith(prefix_to_add):
            base_output_name = worldbook_name
        else:
            base_output_name = f"{prefix_to_add}{worldbook_name}"
        
        output_filepath = f"{base_output_name} ({timestamp}).json"
        
        try:
            with open(output_filepath, "w", encoding="utf-8") as outfile:
                outfile.write(output)
            print(f"世界书生成成功: {output_filepath}")
            print(f"共处理 {total_files_processed} 个文件。")
        except Exception as e:
            print(f"生成文件失败: {e}")


# ==============================================================================
#  部分 2: 世界书分解器 (.json -> 文件夹)
# ==============================================================================
class WorldbookDeconstructor:
    """逆向工程一个世界书 .json 文件到配置文件夹。"""
    def __init__(self, source_path: str):
        if not os.path.isfile(source_path):
            raise FileNotFoundError(f"源文件未找到: {source_path}")
        self.source_path = source_path
        self.worldbook_data = self._load_source_json()
        self.chinese_context_re = re.compile(r'[\u4e00-\u9fa5\uFF00-\uFFEF]')

    def _load_source_json(self) -> Dict[str, Any]:
        print(f"\n[分解器] 正在加载源文件: {self.source_path}")
        try:
            with open(self.source_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "entries" not in data or not isinstance(data["entries"], dict):
                raise ValueError("JSON 文件格式无效：缺少 'entries' 字典。")
            print("  文件加载并验证成功。")
            return data
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  错误: {e}")
            sys.exit(1)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        name = name.strip(' .')
        return name

    @staticmethod
    def _write_json(data: Dict, path: str):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"  成功写入: {os.path.basename(path)}")
        except IOError as e:
            print(f"  写入文件失败 {path}: {e}")
    
    @staticmethod
    def _clean_content(content: str) -> str:
        """清理内容字符串中的特定Markdown标记 (**, *, #)。"""
        content = content.replace('**', '')
        content = content.replace('*', '')
        content = content.replace('#', '')
        return content
            
    def _expand_keys(self, key_list: List[str]) -> List[str]:
        """使用中英文逗号分割并展平关键词列表。"""
        expanded_keys = []
        for key in key_list:
            parts = re.split(r'[,\uff0c]', key)
            expanded_keys.extend([part.strip() for part in parts if part.strip()])
        return expanded_keys

    def _reorder_comment_parts(self, comment_str: str) -> str:
        """对comment字符串内的部分进行排序，中文优先。"""
        if not comment_str: return ""
        parts = re.split(r'[,\uff0c]', comment_str)
        chinese_parts, other_parts = [], []
        for part in parts:
            stripped_part = part.strip()
            if not stripped_part: continue
            if self.chinese_context_re.search(stripped_part):
                chinese_parts.append(stripped_part)
            else:
                other_parts.append(stripped_part)
        reordered_list = chinese_parts + other_parts
        return ", ".join(reordered_list)

    def _clean_base_name_for_folder(self, base_name: str) -> str:
        """从文件名中移除特定前缀、后缀和时间戳，用于生成干净的文件夹名。"""
        clean_name = base_name
        # 1. 移除常见前缀, e.g., 「Touhou」-世界书 -  或 「Touhou」-
        clean_name = re.sub(r'^「.*?」-(世界书\s*-\s*)?', '', clean_name).strip()
        # 2. 移除时间戳后缀, e.g., (10-22-08)
        clean_name = re.sub(r'\s*\(\d{2}-\d{2}-\d{2,}\)$', '', clean_name).strip()
        # 3. 移除 _configs 后缀
        if clean_name.endswith('_configs'):
            clean_name = clean_name[:-8].strip()
        
        return clean_name or base_name

    def deconstruct(self):
        """执行分解过程。"""
        base_name_from_file = os.path.splitext(os.path.basename(self.source_path))[0]
        output_dir = self._clean_base_name_for_folder(base_name_from_file)
        
        source_texts_dir = os.path.join(output_dir, "source_texts")
        
        try:
            os.makedirs(source_texts_dir, exist_ok=True)
            print(f"\n[分解器] 已创建/使用输出目录: {output_dir}")
        except OSError as e:
            print(f"创建目录失败: {e}")
            return

        keyword_mapping, rules, processing_order = {}, [], []
        
        entries = sorted(
            list(self.worldbook_data["entries"].values()),
            key=lambda e: e.get("displayIndex", e.get("uid", 0))
        )
        
        total_entries = len(entries)
        print(f"发现 {total_entries} 个条目，开始分解...")
        used_filenames = set()

        for i, entry in enumerate(entries, 1):
            original_comment = entry.get("comment", f"entry_{entry.get('uid', i)}")
            reordered_comment = self._reorder_comment_parts(original_comment)

            base_filename = self._sanitize_filename(reordered_comment)
            filename = f"{base_filename}.txt"
            counter = 1
            while filename in used_filenames:
                filename = f"{base_filename}_{counter}.txt"
                counter += 1
            used_filenames.add(filename)

            print(f"\r  处理中: {i}/{total_entries} ({filename})", end="")
            
            # 获取原始内容并使用新方法进行清理
            original_content = entry.get("content", "")
            cleaned_content = self._clean_content(original_content)

            with open(os.path.join(source_texts_dir, filename), "w", encoding="utf-8") as f:
                f.write(cleaned_content)
            
            expanded_key = self._expand_keys(entry.get("key", []))
            expanded_keysecondary = self._expand_keys(entry.get("keysecondary", []))
            keyword_mapping[filename] = {"key": expanded_key, "keysecondary": expanded_keysecondary}
            
            settings = {k: v for k, v in entry.items() if k not in ["uid", "key", "keysecondary", "comment", "content", "displayIndex"]}
            rules.append({"identifiers": [filename], "settings": settings})
            
            processing_order.append(filename)

        print("\n\n所有条目处理完成，正在生成配置文件...")
        worldbook_rules_data = {
            "rules": rules, "processing_order": processing_order, "pinned_files": [],
            "default": {"settings": {"selective": True, "position": 1}}
        }
        self._write_json(worldbook_rules_data, os.path.join(output_dir, "worldbook_rules.json"))
        self._write_json(keyword_mapping, os.path.join(output_dir, "keyword_mapping.json"))


# ==============================================================================
#  部分 3: 主程序入口和交互逻辑
# ==============================================================================
def select_directory_interactive() -> Optional[str]:
    """交互式选择文件夹。"""
    dirs = [d for d in os.listdir('.') if os.path.isdir(d) and os.path.exists(os.path.join(d, "worldbook_rules.json"))]
    if not dirs:
        print("\n当前目录下没有找到有效的世界书配置文件夹。")
        return None
    print("\n请选择一个配置文件夹来生成世界书:")
    for i, name in enumerate(dirs): print(f"  {i+1}. {name}")
    print("  0. 返回")
    while True:
        try:
            choice = int(input(f"请输入数字 (0-{len(dirs)}): "))
            if 0 <= choice <= len(dirs): return None if choice == 0 else dirs[choice-1]
        except (ValueError, IndexError): pass
        print("无效输入。")

def select_file_interactive() -> Optional[str]:
    """交互式选择.json文件。"""
    files = [f for f in os.listdir('.') if f.lower().endswith('.json')]
    if not files:
        print("\n当前目录下没有找到.json文件。")
        return None
    print("\n请选择一个世界书.json文件进行分解:")
    for i, name in enumerate(files): print(f"  {i+1}. {name}")
    print("  0. 返回")
    while True:
        try:
            choice = int(input(f"请输入数字 (0-{len(files)}): "))
            if 0 <= choice <= len(files): return None if choice == 0 else files[choice-1]
        except (ValueError, IndexError): pass
        print("无效输入。")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("SillyTavern 世界书 (Lorebook) 双向转换工具".center(46))
    print("=" * 50)

    # --- 拖放模式 ---
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        print(f"\n检测到拖放项目: {input_path}")
        
        if os.path.isdir(input_path):
            print("模式: 【生成】 (文件夹 -> .json)")
            if not os.path.exists(os.path.join(input_path, "worldbook_rules.json")):
                 print("\n错误: 该文件夹不是有效的配置文件夹 (缺少 worldbook_rules.json)。")
            else:
                identifier = input("请输入此世界书的识别名 (默认: Touhou): ").strip() or "Touhou"
                generator = WorldbookGenerator(input_path)
                generator.generate_worldbook(identifier)
        
        elif os.path.isfile(input_path) and input_path.lower().endswith('.json'):
            print("模式: 【分解】 (.json -> 文件夹)")
            deconstructor = WorldbookDeconstructor(input_path)
            deconstructor.deconstruct()
            
        else:
            print("\n错误: 拖放的项目既不是文件夹，也不是.json文件。")

    # --- 交互模式 ---
    else:
        while True:
            print("\n请选择要执行的操作:")
            print("  1. 【分解】世界书 (.json -> 配置文件夹)")
            print("  2. 【生成】世界书 (从配置文件夹 -> .json)")
            print("  0. 退出")
            
            choice = input("请输入选项 (0-2): ").strip()

            if choice == '1':
                target_file = select_file_interactive()
                if target_file:
                    deconstructor = WorldbookDeconstructor(target_file)
                    deconstructor.deconstruct()
            elif choice == '2':
                target_dir = select_directory_interactive()
                if target_dir:
                    identifier = input("请输入此世界书的识别名 (默认: Touhou): ").strip() or "Touhou"
                    generator = WorldbookGenerator(target_dir)
                    generator.generate_worldbook(identifier)
            elif choice == '0':
                break
            else:
                print("无效选项，请重新输入。")

    print("\n操作完成。")
    input("按 Enter键 退出...")
