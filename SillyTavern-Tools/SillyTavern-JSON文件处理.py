import os
import sys
import json
import shutil
import re
import collections
import time
from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Tuple, Set
from pathlib import Path

# 尝试加载 GUI 库，用于文件夹选择器
try:
    import tkinter as tk
    from tkinter import filedialog
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

# =================================================================
# --- 全局配置 ---
# =================================================================

# 控制是否启用“移动文件”功能。若为 False，则只重命名不移动。
MOVE_FILES = False

# 预览模式。若为 True，则不会对磁盘文件产生任何实际修改。
DRY_RUN = False

# 自动检测手动分类：当一个文件夹内包含等于或超过此数量的“同一种类型”JSON时，
# 系统判定该文件夹为用户手动整理，将不再从中移出文件。
MANUAL_SORT_THRESHOLD = 80

# 受保护的文件夹名称 (不区分大小写)。位于这些文件夹内的文件不会被移动。
PRESET_NAMES = {
    "kemini", "mygo", "nova", "戏剧", "贝露", "dreammini", "gemini", 
    "boxbear", "karu", "virgo", "处女座", "逍遥", "janus", "lsr"
}

# 移动模式下，各类型文件对应的目标文件夹名称
TARGET_FOLDERS = {
    "主题": "主题",
    "酒馆脚本": "酒馆脚本",
    "角色卡": "JSON角色卡",
    "QuickReply": "QuickReply",
    "正则": "正则",
    "世界书": "世界书",
    "预设": "预设"
}

# (为 Termux/命令行环境预设) 常用下载或文档路径。
COMMON_PATHS = [
    "~/storage/shared/Download",
    "~/storage/shared/Download/Json文件",
    "~/Downloads",
    "~/Documents"
]

# =================================================================
# --- 核心数据结构与验证器 ---
# =================================================================

@dataclass
class FileTask:
    """定义一个待处理的文件任务"""
    old_path: Path
    file_type: str
    data: Dict
    new_name: Optional[str] = None
    target_dir: Optional[Path] = None

def get_validators() -> Dict[str, Any]:
    """返回各文件类型的识别逻辑"""
    return {
        "主题": lambda d: isinstance(d, dict) and all(k in d for k in ["name", "main_text_color", "font_scale"]),
        "酒馆脚本": lambda d: isinstance(d, dict) and "buttons" in d and "info" in d and "content" in d,
        "角色卡": lambda d: isinstance(d, dict) and (d.get("spec") == "chara_card_v2" or ("first_mes" in d and "name" in d)),
        "QuickReply": lambda d: isinstance(d, dict) and "qrList" in d and "name" in d,
        "正则": lambda d: isinstance(d, dict) and "findRegex" in d and "replaceString" in d,
        "世界书": lambda d: isinstance(d, dict) and "entries" in d and isinstance(d["entries"], dict),
        "预设": lambda d: isinstance(d, dict) and sum(1 for k in ["custom_url", "openai_model", "assistant_prefill"] if k in d) >= 2
    }

# =================================================================
# --- 辅助工具函数 ---
# =================================================================

def sanitize(name: Any) -> str:
    """清洗文件名非法字符并限制长度"""
    if not name or not isinstance(name, str): return "未命名"
    clean_name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return clean_name[:40]

def load_json(path: Path) -> Optional[Dict]:
    """多编码安全加载 JSON"""
    for enc in ['utf-8', 'utf-8-sig', 'utf-16', 'gbk']:
        try:
            with path.open('r', encoding=enc) as f:
                return json.load(f)
        except: continue
    return None

def is_safe_path(path: Path) -> bool:
    """防止误触 SillyTavern 系统核心数据目录"""
    return not re.search(r'SillyTavern[/\\]data[/\\](system|initial|default)', str(path), re.IGNORECASE)

# =================================================================
# --- 处理核心类 ---
# =================================================================

class JsonOrganizer:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path).expanduser().resolve()
        self.validators = get_validators()
        self.tasks: List[FileTask] = []
        self.stats = collections.defaultdict(lambda: {"total": 0, "action": 0})
        self.scanned_count = 0

    def _generate_new_name(self, f_type: str, data: Dict, original_path: Path) -> Optional[str]:
        """根据类型生成标准文件名"""
        name_map = {
            "主题": lambda d: f"主题-{sanitize(d.get('name'))}.json",
            "酒馆脚本": lambda d: f"脚本_{sanitize(d.get('name'))}.json",
            "角色卡": lambda d: f"角色卡-{sanitize(d.get('data', {}).get('name') or d.get('name'))}_{original_path.stat().st_size // 1024}KB.json",
            "QuickReply": lambda d: f"QR-{sanitize(d.get('name'))}.json",
            "正则": lambda d: f"正则-{sanitize(d.get('scriptName') or original_path.stem)}.json"
        }
        return name_map[f_type](data) if f_type in name_map else None

    def plan(self, specific_type: Optional[str] = None):
        """单次遍历：扫描文件并制定处理计划"""
        print(f"正在分析目录: {self.base_path}")
        all_jsons = list(self.base_path.rglob("*.json"))
        self.scanned_count = len(all_jsons)
        
        # 预存文件信息，统计各目录分布情况
        dir_content_stats = collections.defaultdict(lambda: collections.defaultdict(int))
        temp_results = []

        for p in all_jsons:
            if 'logs' in p.parts: continue
            data = load_json(p)
            if not data: continue

            # 匹配类型
            found_type = None
            check_list = [specific_type] if specific_type else self.validators.keys()
            for t in check_list:
                if self.validators[t](data):
                    found_type = t
                    break
            
            if found_type:
                temp_results.append((p, found_type, data))
                dir_content_stats[p.parent][found_type] += 1

        # 确定“手动分类”目录白名单
        manual_dirs = {d for d, counts in dir_content_stats.items() if any(v >= MANUAL_SORT_THRESHOLD for v in counts.values())}

        # 制定具体任务
        for p, t, data in temp_results:
            new_name = self._generate_new_name(t, data, p)
            
            # 移动逻辑判定
            is_manual = p.parent in manual_dirs
            is_preset = p.parent.name.lower() in PRESET_NAMES
            is_already_sorted = p.parent.name == TARGET_FOLDERS[t]
            
            target_dir = None
            if MOVE_FILES and not any([is_manual, is_preset, is_already_sorted]):
                target_dir = self.base_path / TARGET_FOLDERS[t]

            # 只有当名字不同或需要移动时才加入任务
            needs_rename = new_name and p.name.lower() != new_name.lower()
            if needs_rename or target_dir:
                self.tasks.append(FileTask(p, t, data, new_name, target_dir))
                self.stats[t]["action"] += 1
            
            self.stats[t]["total"] += 1

    def execute(self) -> List[Dict]:
        """执行任务并记录日志"""
        logs = []
        if not self.tasks:
            print("\n[结果] 所有文件已符合规范，无需处理。")
            return logs

        print(f"\n{f'预览模式 (DRY RUN)' if DRY_RUN else '执行模式'}：处理中...")
        for task in self.tasks:
            current_path = task.old_path
            
            # 1. 重命名逻辑
            if task.new_name and current_path.name.lower() != task.new_name.lower():
                new_path = self._get_unique_path(current_path.with_name(task.new_name))
                if not DRY_RUN:
                    try:
                        current_path.rename(new_path)
                        logs.append({"type": "rename", "old": str(current_path), "new": str(new_path)})
                        current_path = new_path
                    except Exception as e: print(f"错误: 无法重命名 {current_path.name}: {e}")
                else:
                    logs.append({"type": "rename", "old": str(current_path), "new": str(new_path)})
                    current_path = new_path

            # 2. 移动逻辑
            if task.target_dir:
                task.target_dir.mkdir(parents=True, exist_ok=True)
                dest = self._get_unique_path(task.target_dir / current_path.name)
                if not DRY_RUN:
                    try:
                        shutil.move(str(current_path), str(dest))
                        logs.append({"type": "move", "old": str(current_path), "new": str(dest)})
                    except Exception as e: print(f"错误: 无法移动 {current_path.name}: {e}")
                else:
                    logs.append({"type": "move", "old": str(current_path), "new": str(dest)})

        self._print_report()
        return logs

    def _get_unique_path(self, path: Path) -> Path:
        """解决文件名冲突"""
        if not path.exists() or DRY_RUN: return path
        idx = 1
        while path.exists():
            path = path.with_stem(f"{path.stem}_{idx}")
            idx += 1
        return path

    def _print_report(self):
        """打印摘要报告"""
        print(f"\n{'━'*10} 任务摘要 {'━'*10}")
        print(f"总扫描文件: {self.scanned_count}")
        for t, s in self.stats.items():
            if s['total'] > 0:
                action_text = "待处理" if DRY_RUN else "已修改"
                print(f" - {t:8}: 识别 {s['total']:3} 个 | {action_text} {s['action']:3} 个")
        print(f"{'━'*30}")

# =================================================================
# --- 交互与恢复 ---
# =================================================================

def run_undo():
    """撤销逻辑"""
    log_dir = Path("logs")
    logs = sorted(list(log_dir.glob("*.json")), reverse=True)
    if not logs:
        print("未找到任何操作日志。")
        return

    print(f"最近的日志: {logs[0].name}")
    if input("确定要撤销此日志中的所有操作吗？(y/n): ").lower() != 'y': return

    with logs[0].open('r', encoding='utf-8') as f:
        history = json.load(f)
    
    for action in reversed(history):
        old, new = Path(action['old']), Path(action['new'])
        if new.exists():
            old.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(new), str(old))
    
    logs[0].unlink()
    print("撤销完成，日志已删除。")

def get_path() -> Optional[str]:
    """获取处理路径"""
    if GUI_AVAILABLE:
        root = tk.Tk(); root.withdraw()
        return filedialog.askdirectory()
    print("常用路径:")
    for i, p in enumerate(COMMON_PATHS): print(f" {i+1}. {p}")
    idx = input("请选择序号或直接输入路径: ")
    if idx.isdigit() and 1 <= int(idx) <= len(COMMON_PATHS):
        return COMMON_PATHS[int(idx)-1]
    return idx

# =================================================================
# --- 主程序入口 ---
# =================================================================

def main():
    global MOVE_FILES, DRY_RUN
    while True:
        move_s = "ON" if MOVE_FILES else "OFF"
        dry_s = "PREVIEW" if DRY_RUN else "LIVE"
        print(f"\n>>> JSON 整理工具 | 移动: {move_s} | 模式: {dry_s} <<<")
        print("1. 全功能处理")
        print("2. 特定类型处理")
        print("3. 撤销上次操作")
        print("M. 切换移动开关")
        print("P. 切换预览模式")
        print("0. 退出")
        
        choice = input("\n请选择: ").lower()
        if choice == '0': break
        elif choice == 'm': MOVE_FILES = not MOVE_FILES; continue
        elif choice == 'p': DRY_RUN = not DRY_RUN; continue
        elif choice == '3': run_undo(); continue
        elif choice in ['1', '2']:
            spec_type = None
            if choice == '2':
                types = list(get_validators().keys())
                for i, t in enumerate(types, 1): print(f"{i}. {t}")
                spec_type = types[int(input("选择类型序号: "))-1]
            
            p_str = get_path()
            if not p_str: continue
            
            organizer = JsonOrganizer(p_str)
            if not is_safe_path(organizer.base_path):
                print("警告: 禁止操作 SillyTavern 核心系统目录！")
                continue
            
            organizer.plan(spec_type)
            results = organizer.execute()
            
            if results and not DRY_RUN:
                log_p = Path("logs")
                log_p.mkdir(exist_ok=True)
                log_f = log_p / f"log_{time.strftime('%Y%m%d_%H%M%S')}.json"
                with log_f.open('w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"操作日志已记录: {log_f}")
        else:
            print("无效输入。")

if __name__ == "__main__":
    # 支持拖放处理
    if len(sys.argv) > 1:
        DRY_RUN = False
        MOVE_FILES = False
        for arg in sys.argv[1:]:
            target = Path(arg).resolve()
            # 如果拖进来的是文件，则处理它所在的目录
            if target.is_file(): target = target.parent
            org = JsonOrganizer(str(target))
            if is_safe_path(org.base_path):
                org.plan()
                org.execute()
        input("\n处理完成，按回车退出...")
    else:
        main()
