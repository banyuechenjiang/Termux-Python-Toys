import base64
import zlib
import png
import sys
import json
import os
import re
import collections
import time
import hashlib
import tkinter
from tkinter import filedialog
from PIL import Image
from typing import Optional, List, Tuple, Dict, Any, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import math

# === 常量与正则 ===
PROGRAM_VERSION = "Windows-Pro-v5.6"
DHASH_SIZE = 8
DHASH_SIMILARITY_THRESHOLD = 10
# 匹配: 前缀-大小-计数器.png
PROCESSED_PATTERN = re.compile(r'^(.+)-(\d+KB(?:&\d+KB)?)-(\d+)(?:_\d+)?\.png$', re.IGNORECASE)
SD_KEYWORDS = ["steps:", "sampler:", "cfg scale:", "seed:", "size:", "model hash:"]

class FileType(Enum):
    PURE_IMAGE = auto()
    CHARACTER_CARD = auto()
    SD_PARAM = auto()
    NAI_PARAM = auto()
    COMFY_PARAM = auto()
    MIXED = auto()
    ERROR = auto()

@dataclass
class DetailedCharaData:
    norm_name: str
    norm_first_mes: str

@dataclass
class ProcessedFileInfo:
    original_path: str
    new_path: str
    file_type: FileType
    name_prefix: str
    total_size_kb: int
    text_size_kb: int = 0
    chara_json: Optional[str] = None
    file_hash: Optional[str] = None
    dhash: Optional[str] = None
    detailed_data: Optional[DetailedCharaData] = None

# === 分类引擎 ===
class PNGAnalyzer:
    @staticmethod
    def analyze(filepath: str) -> Tuple[FileType, str, int, Optional[str]]:
        """识别PNG类型，返回: (类型, 建议前缀, 文本字节数, 角色卡JSON)"""
        chunks = {}
        total_text_bytes = 0
        try:
            with open(filepath, 'rb') as f:
                reader = png.Reader(file=f)
                for k, v in reader.chunks():
                    if k in [b'tEXt', b'iTXt']:
                        total_text_bytes += len(v)
                        try:
                            if k == b'tEXt':
                                key, val = v.split(b'\x00', 1)
                                key_s = key.decode('utf-8', 'ignore').lower()
                                chunks[key_s] = val
                        except: pass
        except: return FileType.ERROR, "Error", 0, None

        # 1. 角色卡
        if chunks.get('chara'):
            try:
                raw = chunks['chara']
                try: raw = zlib.decompress(raw)
                except: pass
                payload = base64.b64decode(raw).decode('utf-8')
                data = json.loads(payload)
                name = (data.get("data", {}).get("name") or data.get("name") or "Unnamed")
                return FileType.CHARACTER_CARD, re.sub(r'[\\/:*?"<>|\r\n\t]', '_', name), total_text_bytes, payload
            except: return FileType.ERROR, "CharaError", total_text_bytes, None

        # 辅助识别
        def dec(b): return b.decode('utf-8', 'ignore') if b else ""
        sd_info = dec(chunks.get('parameters'))
        software = dec(chunks.get('software')).lower()
        comment = dec(chunks.get('comment'))
        
        if sd_info and any(k in sd_info.lower() for k in SD_KEYWORDS):
            return FileType.SD_PARAM, "Pic-SD参数", total_text_bytes, None
        if "novelai" in software and "{" in comment:
            return FileType.NAI_PARAM, "Pic-NAI参数", total_text_bytes, None
        if chunks.get('prompt') or chunks.get('workflow'):
            return FileType.COMFY_PARAM, "Pic-ComfyUI", total_text_bytes, None
        if "stable diffusion" in dec(chunks.get('source')).lower():
            return FileType.MIXED, "Pic-混合来源", total_text_bytes, None

        return FileType.PURE_IMAGE, "Pic-纯图片", total_text_bytes, None

# === 处理器 ===
class WindowsPNGProcessor:
    def __init__(self, root_dir: str):
        self.root_dir = os.path.normpath(root_dir)
        self.counter = 0
        self.processed_files: List[ProcessedFileInfo] = []
        self.rename_log = []
        self.stats = collections.defaultdict(int)

    def _get_unique_path(self, folder: str, prefix: str, size_kb: int, text_kb: int) -> str:
        s_str = f"{size_kb}KB" + (f"&{text_kb}KB" if text_kb > 0 else "")
        while True:
            base = f"{prefix}-{s_str}-{self.counter}.png"
            path = os.path.join(folder, base)
            if not os.path.exists(path): return path
            self.counter += 1

    def run_organize(self, verbose: bool):
        print(f"\n[阶段 1] 扫描与增量整理: {self.root_dir}")
        for root, _, files in os.walk(self.root_dir):
            if "log-png" in root: continue
            for f in files:
                if not f.lower().endswith(".png"): continue
                f_path = os.path.join(root, f)
                self.stats['total'] += 1

                # 增量跳过逻辑
                match = PROCESSED_PATTERN.match(f)
                if match:
                    self.counter = max(self.counter, int(match.group(3)))
                    self.stats['skipped'] += 1
                    # 即使跳过，如果是角色卡也记录下来用于查重
                    if not match.group(1).startswith("Pic-"):
                        self.processed_files.append(ProcessedFileInfo(f_path, f_path, FileType.CHARACTER_CARD, match.group(1), 0))
                    continue

                # 解析逻辑
                f_type, prefix, text_bytes, chara_json = PNGAnalyzer.analyze(f_path)
                if f_type == FileType.ERROR: continue
                
                self.counter += 1
                f_kb = math.ceil(os.path.getsize(f_path) / 1024)
                t_kb = math.ceil(text_bytes / 1024)
                
                new_path = self._get_unique_path(root, prefix, f_kb, t_kb)
                
                try:
                    os.rename(f_path, new_path)
                    self.rename_log.append({"old": f_path, "new": new_path})
                    if verbose: print(f"  重命名: {f} -> {os.path.basename(new_path)}")
                except: continue

                pinfo = ProcessedFileInfo(f_path, new_path, f_type, prefix, f_kb, t_kb, chara_json)
                if f_type == FileType.CHARACTER_CARD:
                    self.processed_files.append(pinfo)
                self.stats[f_type.name] += 1

    def run_dedup(self):
        cards = [f for f in self.processed_files if f.file_type == FileType.CHARACTER_CARD]
        if len(cards) < 2: return
        print(f"\n[阶段 2] 角色卡去重 (检测中...)")
        
        seen = {} # (hash, name) -> path
        for p in cards:
            if not p.file_hash:
                p.file_hash = hashlib.sha256(open(p.new_path, 'rb').read()).hexdigest()
            
            # 简化版查重：仅物理哈希
            if p.file_hash in seen:
                print(f"  发现重复: \n    保留: {os.path.basename(seen[p.file_hash])}\n    冗余: {os.path.basename(p.new_path)}")
            else:
                seen[p.file_hash] = p.new_path

def main():
    # Windows 环境路径注入支持
    target = ""
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        root = tkinter.Tk(); root.withdraw()
        target = filedialog.askdirectory()
    
    if not target or not os.path.isdir(target): return

    proc = WindowsPNGProcessor(target)
    proc.run_organize(verbose=True)
    proc.run_dedup()
    
    # 日志留存
    if proc.rename_log:
        log_path = os.path.join(target, f"rename_log_{int(time.time())}.json")
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(proc.rename_log, f, indent=2, ensure_ascii=False)
    
    input("\n处理完成，按回车退出...")

if __name__ == "__main__":
    main()
