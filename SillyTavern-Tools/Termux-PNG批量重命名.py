import base64
import zlib
import sys
import png
import json
import os
import re
import collections
import subprocess
import time
import hashlib
import math
from typing import Optional, List, Tuple, Dict, Any, Set
from dataclasses import dataclass
from enum import Enum, auto

# === 全局配置 ===
PROGRAM_VERSION = "Termux-Pro"
DHASH_SIZE = 8
LOGS_DIR_NAME = "logs"

# === 核心正则与常量 ===
# 匹配: 前缀-1024KB&5KB-123.png 或 前缀-1024KB-123.png
PROCESSED_FILENAME_PATTERN = re.compile(r'^(.+)-(\d+KB(?:&\d+KB)?)-(\d+)(?:_\d+)?\.png$', re.IGNORECASE)
ILLEGAL_FILENAME_CHARS_PATTERN = re.compile(r'[\\/:*?"<>|\r\n\t]')

# 关键词库
SD_KEYWORDS = ["steps:", "sampler:", "cfg scale:", "seed:", "size:", "model hash:", "model:", "denoising strength:"]
NAI_TAG = "novelai"
COMFY_KEYS = ["prompt", "workflow"] # ComfyUI 特有key

# === 界面与交互工具 (UI) ===
class ConsoleUI:
    SEP_LINE = "=" * 60
    SEP_DASH = "-" * 60
    
    @staticmethod
    def header(text: str):
        print(f"\n{ConsoleUI.SEP_LINE}\n{text}\n{ConsoleUI.SEP_LINE}")

    @staticmethod
    def sub_header(text: str):
        print(f"\n{ConsoleUI.SEP_DASH}\n{text}\n{ConsoleUI.SEP_DASH}")

    @staticmethod
    def warn(text: str):
        print(f"\n! 警告: {text}")

    @staticmethod
    def ask_yes_no(question: str, default: str = 'n') -> bool:
        hint = "[Y/n]" if default == 'y' else "[y/N]"
        choice = input(f"{question} {hint}: ").strip().lower()
        if not choice: choice = default
        return choice == 'y'

    @staticmethod
    def check_storage_permission(path: str):
        if not os.access(path, os.W_OK):
            ConsoleUI.warn(f"无法写入目录: {path}")
            print("  请确保已在 Termux 执行 'termux-setup-storage'")
            print("  或检查路径拼写是否正确。")
            sys.exit(1)

    @staticmethod
    def safety_check_sillytavern(path: str):
        path_lower = path.lower()
        risky_keywords = ["sillytavern", "agnai", "risuai", "characters", "chats", "worlds"]
        if any(k in path_lower for k in risky_keywords):
            ConsoleUI.warn(f"目标目录 '{os.path.basename(path)}' 看起来像是 SillyTavern 或类似软件的数据目录。")
            print("  在此处批量重命名可能会导致软件无法识别角色卡！")
            if not ConsoleUI.ask_yes_no("  你确定要继续吗？(风险自负)", 'n'):
                print("  操作已取消。")
                sys.exit(0)

# === 数据结构 ===
class FileType(Enum):
    UNKNOWN = auto()
    ERROR = auto()
    PURE_IMAGE = auto()
    CHARACTER_CARD = auto()
    SD_PARAM = auto()
    NAI_PARAM = auto()
    COMFY_PARAM = auto() # 新增
    MIXED = auto()

@dataclass
class DetailedCharaData:
    norm_name: str
    norm_first_mes: str

@dataclass
class ClassificationResult:
    file_type: FileType
    name_or_prefix: str
    text_size_bytes: int
    chara_json_str: Optional[str] = None

@dataclass
class ProcessedFileInfo:
    original_filepath: str
    new_filepath: str
    file_type: FileType
    file_total_size_kb: int
    chara_json_str: Optional[str] = None
    detailed_data: Optional[DetailedCharaData] = None
    file_hash: Optional[str] = None
    dhash: Optional[str] = None

# === 核心逻辑工具 ===
class Utils:
    @staticmethod
    def sanitize_filename(name: str) -> str:
        if not name: return "未命名"
        return ILLEGAL_FILENAME_CHARS_PATTERN.sub('_', name).strip('_ ')

    @staticmethod
    def contains_chinese(text: str) -> bool:
        return any('\u4e00' <= char <= '\u9fff' for char in text)

    @staticmethod
    def calculate_file_hash(filepath: str) -> Optional[str]:
        hasher = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192): hasher.update(chunk)
            return hasher.hexdigest()
        except: return None

    @staticmethod
    def calculate_dhash(image_path: str) -> Optional[str]:
        try:
            from PIL import Image
            img = Image.open(image_path).convert('L').resize((9, 8), Image.Resampling.LANCZOS)
            return "".join(['1' if img.getpixel((c, r)) > img.getpixel((c + 1, r)) else '0' for r in range(8) for c in range(8)])
        except ImportError: return None
        except: return None

    @staticmethod
    def set_clipboard(text: str):
        try:
            p = subprocess.Popen(['termux-clipboard-set'], stdin=subprocess.PIPE, text=True)
            p.communicate(text)
        except: print("  (提示: 未安装 Termux:API，无法自动复制到剪贴板)")

# === PNG 分析器 (引擎) - 核心修正部分 ===
class PNGMetadataAnalyzer:
    @staticmethod
    def analyze(filepath: str) -> ClassificationResult:
        total_text_bytes = 0
        # 增加 'prompt', 'workflow' 用于识别 ComfyUI
        chunks_data = {'chara': None, 'parameters': None, 'comment': None, 'software': None, 'source': None, 'prompt': None, 'workflow': None}
        has_text = False

        try:
            with open(filepath, 'rb') as f:
                reader = png.Reader(file=f)
                chunks = list(reader.chunks())
                if not chunks or chunks[0][0] != b'IHDR': raise png.FormatError
                
                for k_bytes, v_bytes in chunks:
                    if k_bytes == b'tEXt' or k_bytes == b'iTXt': # 增加 iTXt 支持 (ComfyUI常用)
                        has_text = True
                        # iTXt 结构更复杂，这里简化处理，只看 tEXt 或尝试简单解码
                        # 多数 ComfyUI 也用 tEXt 存 prompt
                        length = len(v_bytes)
                        total_text_bytes += length
                        try:
                            # 简化解析：尝试分割 keyword
                            # tEXt: Keyword\0Text
                            if k_bytes == b'tEXt':
                                split = v_bytes.split(b'\x00', 1)
                                if len(split) == 2:
                                    k_str = split[0].decode('utf-8', 'ignore').lower()
                                    if k_str in chunks_data: chunks_data[k_str] = split[1]
                            # 粗暴检查内容：如果chunks_data没命中，但内容里有 Comfy 标记
                            # (此处为了性能暂不深度解析 iTXt，通常 tEXt 足够覆盖)
                        except: pass
        except: return ClassificationResult(FileType.ERROR, "文件损坏", 0)

        # 1. 角色卡识别 (最高优先级)
        if chunks_data['chara']:
            try:
                raw = chunks_data['chara']
                try: 
                    if raw.startswith(b'x\x9c') or raw.startswith(b'x\xda'): raw = zlib.decompress(raw)
                except: pass
                payload = base64.b64decode(raw).decode('utf-8')
                data = json.loads(payload)
                name = (data.get("data", {}).get("name") if isinstance(data.get("data"), dict) else data.get("name")) or "角色名未知"
                return ClassificationResult(FileType.CHARACTER_CARD, Utils.sanitize_filename(name), total_text_bytes, payload)
            except: 
                # 解析失败的角色卡，回退到纯图片还是Error? 建议Error或者Unknown
                return ClassificationResult(FileType.ERROR, "角色卡解析错误", total_text_bytes)

        # 辅助解码函数
        def dec(b): return b.decode('utf-8', 'ignore') if b else ""
        
        sd_text = dec(chunks_data['parameters'])
        software = dec(chunks_data['software']).lower()
        comment = dec(chunks_data['comment'])
        source = dec(chunks_data['source']).lower()
        comfy_prompt = dec(chunks_data['prompt'])
        comfy_workflow = dec(chunks_data['workflow'])

        # 2. 识别各种 Generation Info
        is_sd = sd_text and sum(1 for k in SD_KEYWORDS if k in sd_text.lower()) >= 2
        is_nai = NAI_TAG in software and comment and "{" in comment
        is_comfy = (comfy_prompt and "{" in comfy_prompt) or (comfy_workflow and "{" in comfy_workflow)

        if is_nai and not is_sd: return ClassificationResult(FileType.NAI_PARAM, "Pic-NAI", total_text_bytes)
        if is_sd: return ClassificationResult(FileType.SD_PARAM, "Pic-SD", total_text_bytes)
        if is_comfy: return ClassificationResult(FileType.COMFY_PARAM, "Pic-Comfy", total_text_bytes) # 新增
        if "stable diffusion" in source: return ClassificationResult(FileType.MIXED, "Pic-Mixed", total_text_bytes)
        
        # 3. 兜底逻辑修正
        # 只要不是以上特定的 AI 格式，哪怕有文本 (比如 Photoshop 信息、Pixiv 时间戳)，
        # 也统统视为 "纯图片"。
        return ClassificationResult(FileType.PURE_IMAGE, "Pic-纯图片", total_text_bytes)

# === 主处理器 ===
class PNGProcessor:
    def __init__(self, root_dir: str):
        self.root_dir = os.path.normpath(root_dir)
        self.sd_dir = os.path.join(self.root_dir, "SD")
        self.nai_dir = os.path.join(self.root_dir, "NAI")
        self.comfy_dir = os.path.join(self.root_dir, "ComfyUI") # 新增目录
        self.logs_dir = os.path.join(os.path.dirname(__file__), LOGS_DIR_NAME)
        
        self.global_counter = 0
        self.processed_list: List[ProcessedFileInfo] = []
        self.op_log: List[Dict] = []
        self.stats = collections.defaultdict(int)
        
        os.makedirs(self.logs_dir, exist_ok=True)
        if os.path.isdir(os.path.dirname(self.root_dir)):
            os.makedirs(self.sd_dir, exist_ok=True)
            os.makedirs(self.nai_dir, exist_ok=True)
            os.makedirs(self.comfy_dir, exist_ok=True)

    def _get_new_path(self, dir_path: str, prefix: str, file_kb: int, text_kb: int) -> str:
        size_str = f"{file_kb}KB" + (f"&{text_kb}KB" if text_kb > 0 else "")
        base = f"{prefix}-{size_str}-{self.global_counter}"
        
        idx = 0
        while True:
            suffix = f"_{idx}" if idx > 0 else ""
            candidate = os.path.join(dir_path, f"{base}{suffix}.png")
            if not os.path.exists(candidate): return candidate
            idx += 1

    def phase1_scan_and_organize(self):
        ConsoleUI.header("阶段 1: 扫描与智能整理")
        print(f"  正在扫描目录: {self.root_dir}")
        print("  (已规范命名的文件将自动跳过解析，仅更新索引)\n")
        
        cjk_pending = []
        start_time = time.time()
        
        for root, _, files in os.walk(self.root_dir):
            if LOGS_DIR_NAME in root: continue
            
            for f in files:
                if not f.lower().endswith(".png"): continue
                f_path = os.path.join(root, f)
                self.stats['total_scanned'] += 1
                
                # 正则预检
                match = PROCESSED_FILENAME_PATTERN.match(f)
                if match:
                    try:
                        self.global_counter = max(self.global_counter, int(match.group(3)))
                        prefix = match.group(1)
                        # 将 Comfy 也加入白名单
                        if prefix not in ["Pic-SD", "Pic-NAI", "Pic-Comfy", "Pic-Mixed", "Pic-纯图片", "未命名", "未知类型"]:
                            self.processed_list.append(ProcessedFileInfo(f_path, f_path, FileType.CHARACTER_CARD, 0))
                            self.stats['角色卡'] += 1
                        self.stats['跳过(已整理)'] += 1
                    except: pass
                    continue
                
                # 全量解析
                try: f_size_kb = math.ceil(os.path.getsize(f_path) / 1024)
                except: continue

                res = PNGMetadataAnalyzer.analyze(f_path)
                
                if res.file_type == FileType.ERROR:
                    self.stats['错误文件'] += 1; continue

                self.global_counter += 1
                text_kb = math.ceil(res.text_size_bytes / 1024)
                
                # 目录分流
                target_root = root
                if res.file_type == FileType.SD_PARAM: target_root = self.sd_dir
                elif res.file_type == FileType.NAI_PARAM: target_root = self.nai_dir
                elif res.file_type == FileType.COMFY_PARAM: target_root = self.comfy_dir # Comfy 分流
                
                # 中文纯图拦截
                if res.file_type == FileType.PURE_IMAGE and Utils.contains_chinese(f):
                    cjk_pending.append((f_path, target_root, f_size_kb))
                    self.global_counter -= 1
                    self.stats['待确认中文图'] += 1
                    continue

                new_path = self._get_new_path(target_root, res.name_or_prefix, f_size_kb, text_kb)
                
                if os.path.abspath(f_path) != os.path.abspath(new_path):
                    try:
                        os.rename(f_path, new_path)
                        op_type = "move" if os.path.dirname(f_path) != os.path.dirname(new_path) else "rename"
                        self.op_log.append({"type": op_type, "original_path": f_path, "new_path": new_path})
                        print(f"  [{res.file_type.name}] {f} -> {os.path.basename(new_path)}")
                    except Exception as e:
                        print(f"  ! 错误: {e}")
                        self.global_counter -= 1; self.stats['操作失败'] += 1
                        continue
                else: new_path = f_path

                if res.file_type == FileType.CHARACTER_CARD:
                    self.processed_list.append(ProcessedFileInfo(f_path, new_path, FileType.CHARACTER_CARD, f_size_kb, chara_json_str=res.chara_json_str))
                
                self.stats[res.file_type.name] += 1

        # 中文纯图处理
        if cjk_pending:
            ConsoleUI.warn(f"发现 {len(cjk_pending)} 张纯图片的文件名包含中文。")
            if ConsoleUI.ask_yes_no("  是否将它们统一重命名为 'Pic-纯图片-xxx.png'?", 'n'):
                print("  正在重命名...")
                for old_path, t_root, size in cjk_pending:
                    self.global_counter += 1
                    new_path = self._get_new_path(t_root, "Pic-纯图片", size, 0)
                    try:
                        os.rename(old_path, new_path)
                        self.op_log.append({"type": "rename", "original_path": old_path, "new_path": new_path})
                        self.stats['PURE_IMAGE'] += 1
                    except: pass
            else:
                print("  已保留原文件名。")

        duration = time.time() - start_time
        ConsoleUI.sub_header(f"阶段 1 完成 (耗时 {duration:.2f}s)")
        print(f"  扫描总数: {self.stats['total_scanned']}")
        print(f"  角色卡:   {self.stats['CHARACTER_CARD'] + self.stats['角色卡']} (含已存)")
        print(f"  SD/NAI:   {self.stats['SD_PARAM'] + self.stats['NAI_PARAM']}")
        print(f"  ComfyUI:  {self.stats['COMFY_PARAM']}")
        print(f"  纯图片:   {self.stats['PURE_IMAGE']}")
        print(f"  跳过:     {self.stats['跳过(已整理)']}")

    def phase2_deduplication(self):
        cards = [c for c in self.processed_list if c.file_type == FileType.CHARACTER_CARD]
        if len(cards) < 2: return

        ConsoleUI.header("阶段 2: 精确重复检测 (可选)")
        print(f"  现有 {len(cards)} 张角色卡。")
        if not ConsoleUI.ask_yes_no("  开始查重吗？", 'n'): return

        print("\n  正在分析数据 (Lazy Load)...")
        for i, p in enumerate(cards):
            print(f"\r  进度: {int((i+1)/len(cards)*100)}%", end="")
            if not p.file_hash and os.path.exists(p.new_filepath):
                p.file_hash = Utils.calculate_file_hash(p.new_filepath)
                p.dhash = Utils.calculate_dhash(p.new_filepath)
                if not p.detailed_data:
                    json_str = p.chara_json_str
                    if not json_str: 
                         tmp = PNGMetadataAnalyzer.analyze(p.new_filepath)
                         json_str = tmp.chara_json_str
                    if json_str:
                        try:
                            d = json.loads(json_str)
                            src = d.get("data", d)
                            name = src.get("name") or src.get("displayName") or ""
                            fm = src.get("first_mes") or src.get("description") or ""
                            p.detailed_data = DetailedCharaData(name.strip(), fm.strip())
                        except: pass
        print("\n")

        duplicates_map = collections.defaultdict(list)
        seen = {}

        for p in cards:
            if not p.file_hash or not p.detailed_data: continue
            key = (p.file_hash, p.dhash, p.detailed_data.norm_name, p.detailed_data.norm_first_mes)
            if key in seen: duplicates_map[p.detailed_data.norm_name].append((seen[key], p.new_filepath))
            else: seen[key] = p.new_filepath

        if not duplicates_map:
            print("  ✅ 未发现完全重复的角色卡。")
        else:
            ConsoleUI.warn(f"发现 {len(duplicates_map)} 组重复卡片！")
            report_lines = ["=== 重复文件报告 ==="]
            for name, pairs in duplicates_map.items():
                report_lines.append(f"\n角色: {name}")
                for keep, remove in pairs:
                    report_lines.append(f"  建议保留: {os.path.basename(keep)}")
                    report_lines.append(f"  建议删除: {os.path.basename(remove)}")
            
            report_text = "\n".join(report_lines)
            print(report_text)
            Utils.set_clipboard(report_text)

    def save_logs(self):
        if not self.op_log: return
        log_file = os.path.join(self.logs_dir, f"log_{time.strftime('%Y%m%d_%H%M%S')}.json")
        try:
            with open(log_file, 'w') as f: json.dump(self.op_log, f, indent=2)
            print(f"\n  [日志] 已保存至: {LOGS_DIR_NAME}/{os.path.basename(log_file)}")
        except: pass

# === 撤销功能 ===
def run_undo():
    log_dir = os.path.join(os.path.dirname(__file__), LOGS_DIR_NAME)
    if not os.path.exists(log_dir): return print("  没有日志。")
    logs = sorted([f for f in os.listdir(log_dir) if f.endswith(".json")], reverse=True)
    if not logs: return print("  没有日志。")

    ConsoleUI.sub_header("撤销操作")
    for i, l in enumerate(logs[:5]): print(f"  {i+1}. {l}")
    try:
        idx = int(input("  序号 (0退出): ")) - 1
        if idx < 0: return
        target_log = os.path.join(log_dir, logs[idx])
        with open(target_log, 'r') as f: ops = json.load(f)
    except: return

    print(f"\n  将撤销 {len(ops)} 个操作。")
    if not ConsoleUI.ask_yes_no("  确认吗？", 'n'): return

    success, fail = 0, 0
    print("  执行中...")
    for op in reversed(ops):
        src, dst = op['original_path'], op['new_path']
        try:
            if os.path.exists(dst):
                if op['type'] == 'move': os.makedirs(os.path.dirname(src), exist_ok=True)
                os.rename(dst, src)
                success += 1
            else: fail += 1
        except: fail += 1
    
    print(f"  成功: {success}, 失败: {fail}")
    try: os.remove(target_log)
    except: pass

def main():
    print(f"\n{ConsoleUI.SEP_LINE}")
    print(f"  PNG 文件批量处理与分析工具 {PROGRAM_VERSION}")
    print(f"{ConsoleUI.SEP_LINE}")

    print("  1. 开始整理")
    print("  2. [撤销] 从日志恢复操作")
    print("  0. 退出")
    
    choice = input("\n选项 [1]: ").strip()
    if choice == '' or choice == '1':
        default_path = os.path.expanduser("~/storage/shared/Download")
        target_dir = default_path
        
        if os.path.exists(default_path):
             print(f"\n默认路径: {default_path}")
             if not ConsoleUI.ask_yes_no("处理此目录?", 'y'):
                 target_dir = input("输入路径: ").strip()
        else:
             target_dir = input("输入路径: ").strip()

        if not target_dir or not os.path.exists(target_dir): return print("路径错误")

        ConsoleUI.check_storage_permission(target_dir)
        ConsoleUI.safety_check_sillytavern(target_dir)
        
        processor = PNGProcessor(target_dir)
        try:
            processor.phase1_scan_and_organize()
            processor.phase2_deduplication()
        except KeyboardInterrupt: print("\n! 中断")
        finally: processor.save_logs()
            
    elif choice == '2': run_undo()

if __name__ == "__main__":
    main()
