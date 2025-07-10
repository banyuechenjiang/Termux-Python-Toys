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
from PIL import Image # Pillow
from typing import Optional, List, Tuple, Dict, Any, Set
from dataclasses import dataclass, field
import math

# === 全局配置 v5.5 ===
PROGRAM_VERSION = "v5.5"
DHASH_SIZE = 8
DHASH_SIMILARITY_THRESHOLD = 10
SD_RAW_TEXT_PARAM_KEYWORDS = ["steps:", "sampler:", "cfg scale:", "seed:", "size:", "model hash:", "model:"]
NAI_SOFTWARE_TAG_LOWER = "novelai"
NAI_COMMENT_JSON_EXPECTED_KEYS = {"prompt", "steps", "sampler", "seed", "uc"}

# --- 信号常量 ---
SIGNAL_PIC_NAI_PARAMS = "__PIC_NAI_PARAMS__"
SIGNAL_PIC_SD_PARAMS = "__PIC_SD_PARAMS__"
SIGNAL_PIC_MIXED_SOURCE = "__PIC_MIXED_SOURCE__"
SIGNAL_PIC_NO_TEXT_PURE_IMAGE = "__PIC_NO_TEXT_PURE_IMAGE__"
SIGNAL_SKIP_OTHER_TEXT_NO_TYPE = "__SKIP__OTHER_TEXT_NO_RECOGNIZED_TYPE__"
SIGNAL_SKIP_FILE_ERROR = "__SKIP__FILE_ERROR__"
SIGNAL_SKIP_UNKNOWN_READ_ERROR = "__SKIP__UNKNOWN_READ_ERROR__"
SIGNAL_UNKNOWN_CHARA_NO_NAME = "UnknownChara_NoName"
SIGNAL_UNKNOWN_CHARA_PARSE_ERROR = "UnknownChara_ParseError"

# --- 数据驱动配置表 (核心改进) ---
FILE_TYPE_CONFIG = {
    SIGNAL_PIC_SD_PARAMS: {
        "base_name": "Pic-SD参数",
        "stat_key": "sd",
        "display_name": "SD参数图"
    },
    SIGNAL_PIC_NAI_PARAMS: {
        "base_name": "Pic-NAI参数",
        "stat_key": "nai",
        "display_name": "NAI参数图"
    },
    SIGNAL_PIC_MIXED_SOURCE: {
        "base_name": "Pic-混合来源",
        "stat_key": "mixed",
        "display_name": "混合来源图"
    },
    SIGNAL_PIC_NO_TEXT_PURE_IMAGE: {
        "base_name": "Pic-纯图片",
        "stat_key": "pure",
        "display_name": "纯图片"
    }
}

# === 辅助工具类 ===
class ScriptUtils:
    @staticmethod
    def find_unique_filepath(root_path, base_name, original_filepath):
        candidate_path = os.path.join(root_path, f"{base_name}.png")
        if not os.path.exists(candidate_path) or candidate_path == original_filepath:
            return candidate_path
        index = 1
        while True:
            new_name = f"{base_name}_{index}.png"
            new_path = os.path.join(root_path, new_name)
            if not os.path.exists(new_path) or new_path == original_filepath:
                return new_path
            index += 1

    @staticmethod
    def print_sorted_file_group(report_dict, base_directory):
        for group_name, filepaths_set in sorted(report_dict.items()):
            if len(filepaths_set) > 1:
                sorted_paths = sorted(
                    list(filepaths_set),
                    key=lambda p: _extract_size_info_from_filename(os.path.basename(p))
                )
                print(f"{group_name}：")
                for path in sorted_paths:
                    print(f"  - {os.path.relpath(path, base_directory)}")

    @staticmethod
    def format_directory_summary(renames_dict: Dict[str, int]) -> str:
        parts = []
        if renames_dict.get('chara', 0) > 0:
            parts.append(f"角色卡 {renames_dict['chara']} 个")
        for config in FILE_TYPE_CONFIG.values():
            stat_key = config['stat_key']
            if renames_dict.get(stat_key, 0) > 0:
                parts.append(f"{config['display_name']} {renames_dict[stat_key]} 个")
        return "处理 " + ", ".join(parts) + "。"

    @staticmethod
    def print_phase1_summary(stats: Dict[str, Any]):
        print("\n--- 初步扫描与重命名摘要 (阶段 1 完成) ---")
        print(f"  总共迭代 {stats.get('files_iterated', 0)} 个文件系统条目。")
        print(f"  总共处理(重命名或检查) {stats.get('png_processed', 0)} 个PNG文件。")
        chara_cards_count = len(stats.get('character_cards_info', []))
        print(f"    其中 {chara_cards_count} 个被识别为角色卡，将进入后续分析。")
        for config in FILE_TYPE_CONFIG.values():
            count = stats.get(config['stat_key'], 0)
            if count > 0:
                extra_info = " (部分可能待确认重命名)" if config['stat_key'] == 'pure' else ""
                print(f"    {count} 个被识别为{config['display_name']}{extra_info}。")
        if stats.get('skipped', 0) > 0:
            print(f"  跳过 {stats.get('skipped', 0)} 个文件 (数据不足、错误等)。")

    @staticmethod
    def print_undo_summary(undone_count, skipped_count, error_count):
        print("\n--- 撤销操作完成 ---")
        print(f"  成功撤销: {undone_count} 个文件")
        if skipped_count > 0:
            print(f"  跳过操作: {skipped_count} 个文件 (目标不存在或为防止覆盖)")
        if error_count > 0:
            print(f"  发生错误: {error_count} 个文件")

# === 数据结构定义 ===
@dataclass
class DetailedCharaData:
    norm_name: Optional[str] = None
    norm_first_mes: Optional[str] = None
    book_entries_set_str: Optional[str] = None

@dataclass
class ProcessedFileInfo:
    original_filepath: str
    new_filepath: str
    initial_meta_name_or_type_signal: str
    is_character_card: bool = False
    is_sd_params_pic: bool = False
    is_nai_params_pic: bool = False
    is_mixed_source_pic: bool = False
    is_pure_image_pic: bool = False
    file_total_size_kb: int = 0
    file_text_size_kb: int = 0
    chara_json_str: Optional[str] = None
    file_hash: Optional[str] = None
    dhash: Optional[str] = None
    detailed_chara_data: Optional[DetailedCharaData] = None

@dataclass
class PureImagePendingRenameInfo:
    original_filepath: str
    target_new_filename_base: str
    root_path: str
    file_total_size_kb: int

# === 核心逻辑函数  ===

def _parse_all_text_chunks(png_file_path: str) -> Tuple[Dict[str, str], int]:
    """只解析PNG的tEXt块，不进行逻辑判断。返回解析后的字典和总文本大小。"""
    parsed_chunks = {}
    total_text_chunk_bytes = 0
    with open(png_file_path, 'rb') as f:
        reader = png.Reader(file=f)
        for chunk_type, chunk_data in reader.chunks():
            if chunk_type == b'tEXt':
                total_text_chunk_bytes += len(chunk_data)
                try:
                    keyword_bytes, text_bytes_raw = chunk_data.split(b'\x00', 1)
                    keyword = keyword_bytes.decode('utf-8', errors='ignore').lower()
                    # 为 'chara' 块进行特殊预处理
                    if keyword == 'chara':
                        processed_text = text_bytes_raw
                        try: processed_text = zlib.decompress(processed_text)
                        except zlib.error: pass
                        try:
                            decoded_base64 = base64.b64decode(processed_text)
                            parsed_chunks[keyword] = decoded_base64.decode('utf-8')
                        except Exception:
                            # 如果解码失败，也记录下来，让后续逻辑处理
                            parsed_chunks[keyword] = "__DECODE_ERROR__"
                    else:
                        parsed_chunks[keyword] = text_bytes_raw.decode('utf-8', errors='strict')
                except (ValueError, UnicodeDecodeError):
                    continue # 忽略格式不正确的tEXt块
    return parsed_chunks, total_text_chunk_bytes

def _determine_file_type_from_chunks(chunks: Dict[str, str]) -> Tuple[str, Optional[str]]:
    """根据解析出的文本块字典，进行逻辑判断，返回信号和角色卡数据。"""
    chara_payload = chunks.get('chara')
    if chara_payload:
        if chara_payload == "__DECODE_ERROR__":
            return SIGNAL_UNKNOWN_CHARA_PARSE_ERROR, None
        try:
            data_root = json.loads(chara_payload)
            data_section = data_root.get("data", {}) if isinstance(data_root, dict) else {}
            name = data_section.get("name") if isinstance(data_section, dict) else data_root.get("name")
            if isinstance(name, str) and name.strip():
                return sanitize_filename_component(name.strip()), chara_payload
            return SIGNAL_UNKNOWN_CHARA_NO_NAME, chara_payload
        except (json.JSONDecodeError, AttributeError):
            return SIGNAL_UNKNOWN_CHARA_PARSE_ERROR, chara_payload

    # 检查NAI
    is_nai_software = NAI_SOFTWARE_TAG_LOWER in chunks.get('software', '').lower()
    try:
        nai_comment_data = json.loads(chunks.get('comment', '{}'))
        is_nai_comment_valid = isinstance(nai_comment_data, dict) and \
                               len(NAI_COMMENT_JSON_EXPECTED_KEYS.intersection(nai_comment_data.keys())) >= 4
    except json.JSONDecodeError:
        is_nai_comment_valid = False
    if is_nai_software and is_nai_comment_valid:
        return SIGNAL_PIC_NAI_PARAMS, None

    # 检查SD
    sd_params_text = chunks.get('parameters', '')
    if sd_params_text and sum(1 for kw in SD_RAW_TEXT_PARAM_KEYWORDS if kw in sd_params_text.lower()) >= 2:
        return SIGNAL_PIC_SD_PARAMS, None

    # 检查混合来源
    is_sd_in_source = "stable diffusion" in chunks.get('source', '').lower()
    if is_nai_software and is_sd_in_source:
        return SIGNAL_PIC_MIXED_SOURCE, None

    return SIGNAL_SKIP_OTHER_TEXT_NO_TYPE, None

def read_chara_json_and_text_size_from_png(png_file_path: str) -> Tuple[Optional[str], int, str]:
    """重构后的主入口：协调解析和判断。"""
    try:
        parsed_chunks, total_bytes = _parse_all_text_chunks(png_file_path)
        if not parsed_chunks:
            return None, 0, SIGNAL_PIC_NO_TEXT_PURE_IMAGE
        
        signal, payload = _determine_file_type_from_chunks(parsed_chunks)
        return payload, total_bytes, signal

    except (FileNotFoundError, png.FormatError):
        return None, 0, SIGNAL_SKIP_FILE_ERROR
    except Exception:
        return None, 0, SIGNAL_SKIP_UNKNOWN_READ_ERROR

def extract_and_normalize_key_chara_data(chara_json_str: Optional[str]) -> Optional[DetailedCharaData]:
    if not chara_json_str: return None
    try:
        data_root = json.loads(chara_json_str); data_section = data_root.get("data", {})
        if not isinstance(data_section, dict):
            if "name" in data_root: data_section = data_root
            else: return None
        details = DetailedCharaData(); name_val = data_section.get("name")
        if not (isinstance(name_val, str) and name_val.strip()): name_val = data_root.get("name")
        details.norm_name = name_val.strip().lower() if isinstance(name_val, str) and name_val.strip() else None
        first_mes_val = data_section.get("first_mes")
        details.norm_first_mes = first_mes_val.strip() if isinstance(first_mes_val, str) else ""
        book_entry_names: List[str] = []
        char_book = data_section.get("character_book")
        if isinstance(char_book, dict):
            entries = char_book.get("entries")
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        entry_name = entry.get("name")
                        if isinstance(entry_name, str) and entry_name.strip(): book_entry_names.append(entry_name.strip().lower())
        details.book_entries_set_str = "||".join(sorted(list(set(book_entry_names)))) if book_entry_names else ""
        return details
    except (json.JSONDecodeError, TypeError, AttributeError): return None

def compare_detailed_chara_data(data1: Optional[DetailedCharaData], data2: Optional[DetailedCharaData]) -> bool:
    if data1 is None and data2 is None: return True
    if data1 is None or data2 is None: return False
    return (data1.norm_name == data2.norm_name and
            data1.norm_first_mes == data2.norm_first_mes and
            data1.book_entries_set_str == data2.book_entries_set_str)

def sanitize_filename_component(filename_part: str) -> str:
    if not filename_part: return "Unnamed"
    return re.sub(r'[\\/:*?"<>|\r\n\t]', '_', filename_part)

def _contains_chinese_char(text: str) -> bool:
    for char in text:
        if '\u4e00' <= char <= '\u9fff': return True
    return False

def calculate_file_hash(filepath: str) -> Optional[str]:
    hasher = hashlib.sha256();
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192): hasher.update(chunk)
        return hasher.hexdigest()
    except (FileNotFoundError, Exception): return None

def calculate_dhash(image_path: str) -> Optional[str]:
    try:
        img = Image.open(image_path).convert('L').resize((DHASH_SIZE + 1, DHASH_SIZE), Image.Resampling.LANCZOS)
        return "".join(['1' if img.getpixel((c, r)) > img.getpixel((c + 1, r)) else '0'
                        for r in range(DHASH_SIZE) for c in range(DHASH_SIZE)])
    except (FileNotFoundError, Exception): return None

def compare_dhashes(hash1: Optional[str], hash2: Optional[str]) -> bool:
    if not hash1 or not hash2 or len(hash1) != len(hash2): return False
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2)) <= DHASH_SIMILARITY_THRESHOLD

def _extract_size_info_from_filename(filename_basename: str) -> Tuple[int, int, str]:
    pure_match = re.search(r'Pic-纯图片-(\d+)KB-\d+.*?\.png$', filename_basename)
    if pure_match:
        try: return (int(pure_match.group(1)), 0, filename_basename)
        except ValueError: pass
    text_match = re.search(r'-(\d+)KB&(\d+)KB-\d+.*?\.png$', filename_basename)
    if text_match:
        try: return (int(text_match.group(1)), int(text_match.group(2)), filename_basename)
        except ValueError: pass
    return (0, 0, filename_basename)

def _decode_generic_text_chunk_data_for_viewer(chunk_data: bytes) -> Tuple[Optional[str], Any, str]:
    keyword_str: Optional[str] = None; text_bytes_raw: Optional[bytes] = None
    try:
        keyword_bytes, text_bytes_raw = chunk_data.split(b'\x00', 1)
        try: keyword_str = keyword_bytes.decode('utf-8', errors='replace')
        except UnicodeDecodeError: keyword_str = keyword_bytes.hex() + f" (raw: {keyword_bytes!r})"
    except ValueError: return None, chunk_data, "raw_malformed_chunk"
    keyword_lower = keyword_str.lower() if keyword_str else ""
    if keyword_lower == 'chara':
        processed_chara_text = text_bytes_raw
        try: processed_chara_text = zlib.decompress(processed_chara_text)
        except zlib.error: pass
        try:
            decoded_base64_bytes = base64.b64decode(processed_chara_text)
            return keyword_str, decoded_base64_bytes.decode('utf-8', errors='replace'), "chara_like_decoded_utf8"
        except (base64.binascii.Error, UnicodeDecodeError): return keyword_str, processed_chara_text, "chara_like_raw_or_undecodable"
    if keyword_lower in ['parameters', 'comment', 'software', 'source', 'title', 'description']:
        try:
            text_content_str = text_bytes_raw.decode('utf-8', errors='strict')
            return keyword_str, text_content_str, f"raw_utf8_text ({keyword_lower})"
        except UnicodeDecodeError: pass
    try:
        text_content_str = text_bytes_raw.decode('utf-8', errors='strict')
        return keyword_str, text_content_str, "raw_utf8_text_generic"
    except UnicodeDecodeError: pass
    try: return keyword_str, base64.b64decode(text_bytes_raw, validate=True), "base64_decoded_bytes"
    except base64.binascii.Error: return keyword_str, text_bytes_raw, "raw_bytes_not_base64_or_utf8"
    except Exception: return keyword_str, text_bytes_raw, "raw_bytes_decoding_error_generic"

def view_png_all_text_chunks_console():
    filepath = filedialog.askopenfilename(title="选择PNG文件以查看tEXt元数据", filetypes=(("PNG 文件", "*.png"), ("所有文件", "*.*")))
    if not filepath: print("  未选择文件，操作取消。"); return
    print(f"\n分析文件: {filepath}\n\n  tEXt Chunks 内容:")
    text_chunks_found = 0
    try:
        with open(filepath, 'rb') as f:
            reader = png.Reader(file=f)
            for chunk_type, chunk_data in reader.chunks():
                if chunk_type == b'tEXt':
                    text_chunks_found += 1
                    keyword, content, repr_type = _decode_generic_text_chunk_data_for_viewer(chunk_data)
                    print(f"    Chunk {text_chunks_found}: Keyword: {keyword if keyword else 'N/A'} (Type: {repr_type})")
                    if repr_type == "chara_like_decoded_utf8":
                        try:
                            json_formatted = json.dumps(json.loads(content), indent=2, ensure_ascii=False)
                            print(json_formatted + "\n")
                        except json.JSONDecodeError: print(f"        文本内容: {content!r}\n")
                    elif "raw_utf8_text" in repr_type:
                        print(f"        文本内容: {content}\n")
                    elif isinstance(content, bytes): print(f"        HEX: {content.hex()}\n        Bytes (repr): {content!r}\n")
                    else: print(f"        Content: {content!r}\n")
            if not text_chunks_found: print("    未在此文件中找到 tEXt chunks。\n")
    except Exception as e: print(f"  处理PNG时发生错误: {e}\n")
    print("-" * 20)

# === 主流程函数 (重构后) ===
GLOBAL_FILE_COUNTER = 0

def _phase1_scan_and_rename(directory, verbose_output_for_rename, rename_log):
    global GLOBAL_FILE_COUNTER; GLOBAL_FILE_COUNTER = 0
    stats = collections.defaultdict(int)
    character_cards_info = []
    stats['character_cards_info'] = character_cards_info
    pure_image_cjk_filenames_to_rename_later = []

    print("\n[阶段 1/3] 逐一扫描、重命名PNG文件...")
    for root, dirs, files in os.walk(directory):
        if 'log-png' in dirs: dirs.remove('log-png')
        relative_root_path = os.path.relpath(root, directory)
        if relative_root_path == ".": relative_root_path = ""
        renames_in_current_root = collections.defaultdict(int)

        for filename in files:
            stats['files_iterated'] += 1
            if not filename.lower().endswith(".png"): continue
            
            original_filepath = os.path.join(root, filename)
            payload_str, total_bytes, signal = read_chara_json_and_text_size_from_png(original_filepath)

            if signal.startswith("__SKIP__"):
                stats['skipped'] += 1
                if verbose_output_for_rename: print(f"  跳过(P1): {filename} (原因: {signal.split('__', 2)[-1]})")
                continue

            is_character_card = signal not in FILE_TYPE_CONFIG and not signal.startswith("UnknownChara")
            is_pure_image = signal == SIGNAL_PIC_NO_TEXT_PURE_IMAGE
            
            base_name_for_file = signal
            file_type_str = "角色卡" if is_character_card else "无法识别"
            if not is_character_card and signal in FILE_TYPE_CONFIG:
                config = FILE_TYPE_CONFIG[signal]
                base_name_for_file = config["base_name"]
                file_type_str = config["display_name"]

            try: file_size_kb = math.ceil(os.path.getsize(original_filepath) / 1024)
            except FileNotFoundError:
                if verbose_output_for_rename: print(f"  警告(P1): {filename} 大小获取失败，跳过。");
                stats['skipped'] += 1; continue
            
            total_text_kb = math.ceil(total_bytes / 1024) if not is_pure_image else 0
            
            new_filename_base = (f"{base_name_for_file}-{file_size_kb}KB-{GLOBAL_FILE_COUNTER}" if is_pure_image else
                                 f"{base_name_for_file}-{file_size_kb}KB&{total_text_kb}KB-{GLOBAL_FILE_COUNTER}")
            
            final_new_filepath = ScriptUtils.find_unique_filepath(root, new_filename_base, original_filepath)
            
            perform_rename_now = not (is_pure_image and _contains_chinese_char(filename))
            
            if not perform_rename_now:
                pure_image_cjk_filenames_to_rename_later.append(
                    PureImagePendingRenameInfo(original_filepath, new_filename_base, root, file_size_kb)
                )
                renames_in_current_root['pure'] += 1
                stats['pure'] += 1
                if verbose_output_for_rename:
                    print(f"  暂缓(P1): {filename} (纯图片,含中文,待确认) -> 目标: {os.path.basename(final_new_filepath)}")
            
            renamed_this_file = False
            if perform_rename_now and original_filepath != final_new_filepath:
                if "SillyTavern" in root and "characters" in root.lower() and is_character_card:
                     print(f"  ST警告(P1): 重命名角色卡 {filename} -> {os.path.basename(final_new_filepath)}")
                try:
                    os.rename(original_filepath, final_new_filepath)
                    renamed_this_file = True
                    rename_log.append({"original_path": original_filepath, "new_path": final_new_filepath})
                except OSError as e:
                    if verbose_output_for_rename: print(f"  错误(P1): 重命名失败 {filename}: {e}")
                    stats['skipped'] += 1; continue
            
            if (renamed_this_file or (original_filepath == final_new_filepath)) and perform_rename_now:
                if is_character_card:
                    renames_in_current_root['chara'] += 1
                elif signal in FILE_TYPE_CONFIG:
                    stat_key = FILE_TYPE_CONFIG[signal]['stat_key']
                    renames_in_current_root[stat_key] += 1
                    stats[stat_key] += 1
            
            if verbose_output_for_rename and renamed_this_file and perform_rename_now:
                 print(f"  {relative_root_path or '.'}: {filename} -> {os.path.basename(final_new_filepath)} ({file_type_str})")
            
            if not (is_pure_image and not perform_rename_now):
                p_info_obj = ProcessedFileInfo(
                    original_filepath, final_new_filepath, signal, is_character_card,
                    signal == SIGNAL_PIC_SD_PARAMS, signal == SIGNAL_PIC_NAI_PARAMS,
                    signal == SIGNAL_PIC_MIXED_SOURCE, is_pure_image,
                    file_size_kb, total_text_kb, payload_str if is_character_card else None
                )
                if is_character_card: character_cards_info.append(p_info_obj)

            GLOBAL_FILE_COUNTER += 1
        
        if renames_in_current_root:
            summary_text = ScriptUtils.format_directory_summary(renames_in_current_root)
            print(f"  目录 {relative_root_path or '.'}: {summary_text}")

    stats['png_processed'] = GLOBAL_FILE_COUNTER
    ScriptUtils.print_phase1_summary(stats)
    
    # 处理待确认重命名的纯图片逻辑
    if pure_image_cjk_filenames_to_rename_later:
        user_confirm_rename_cjk_pure = input(
            f"  检测到 {len(pure_image_cjk_filenames_to_rename_later)} 张无元数据且原始文件名含中文的PNG。是否将这些文件也统一重命名为 \"Pic-纯图片-...\" 格式? (y/n, 默认 n): "
        ).strip().lower()
        if user_confirm_rename_cjk_pure == 'y':
            renamed_cjk_pure_count = 0
            for item_to_rename in pure_image_cjk_filenames_to_rename_later:
                final_new_filepath_confirm = ScriptUtils.find_unique_filepath(
                    item_to_rename.root_path, 
                    item_to_rename.target_new_filename_base, 
                    item_to_rename.original_filepath
                )
                if item_to_rename.original_filepath != final_new_filepath_confirm:
                    try:
                        os.rename(item_to_rename.original_filepath, final_new_filepath_confirm)
                        renamed_cjk_pure_count +=1
                        rename_log.append({"original_path": item_to_rename.original_filepath, "new_path": final_new_filepath_confirm})
                        if verbose_output_for_rename:
                            print(f"  确认重命名(纯图片,中文): {os.path.basename(item_to_rename.original_filepath)} -> {os.path.basename(final_new_filepath_confirm)}")
                    except OSError as e:
                        if verbose_output_for_rename:
                            print(f"  错误(确认重命名): {os.path.basename(item_to_rename.original_filepath)}: {e}")
            if renamed_cjk_pure_count > 0: print(f"  已额外重命名 {renamed_cjk_pure_count} 个含中文文件名的纯图片。")
        else:
            print("  未对含中文文件名的纯图片执行统一重命名。")

    if not character_cards_info and GLOBAL_FILE_COUNTER == 0 : print("  未找到任何有效PNG文件进行处理。")
    return character_cards_info


def _phase2_identify_groups_and_compute_data(character_cards_info, directory_base, verbose_output):
    print("\n[阶段 2/3] 角色卡分组、计算核心数据、检测精确重复...")
    grouped_by_initial_name = collections.defaultdict(list)
    for p_info in character_cards_info:
        if p_info.is_character_card: grouped_by_initial_name[p_info.initial_meta_name_or_type_signal].append(p_info)

    processed_groups_filled_data = {}
    exact_duplicates_by_meta_name = collections.defaultdict(list); found_any_exact_duplicates = False

    for initial_name, group_files_info_list in grouped_by_initial_name.items():
        if len(group_files_info_list) < 1: continue
        files_in_group_with_data = []
        hashes_in_this_group = collections.defaultdict(list)
        for p_info_item in group_files_info_list:
            p_info_item.file_hash = calculate_file_hash(p_info_item.new_filepath)
            p_info_item.detailed_chara_data = extract_and_normalize_key_chara_data(p_info_item.chara_json_str)
            p_info_item.chara_json_str = None
            p_info_item.dhash = calculate_dhash(p_info_item.new_filepath)
            files_in_group_with_data.append(p_info_item)
            if p_info_item.file_hash: hashes_in_this_group[p_info_item.file_hash].append(p_info_item.new_filepath)
        processed_groups_filled_data[initial_name] = files_in_group_with_data
        if len(group_files_info_list) > 1:
            for f_hash, paths_with_same_hash in hashes_in_this_group.items():
                if len(paths_with_same_hash) > 1:
                    exact_duplicates_by_meta_name[initial_name].extend(paths_with_same_hash)
                    found_any_exact_duplicates = True

    print("\n--- 内容完全相同的精确重复角色卡 (阶段 2 完成) ---")
    if not found_any_exact_duplicates:
        print("  无")
    else:
        report_data = {name: set(paths) for name, paths in exact_duplicates_by_meta_name.items()}
        ScriptUtils.print_sorted_file_group(report_data, directory_base)
        
    return processed_groups_filled_data

def _phase3_detailed_comparison_report(processed_groups_with_data, directory_base, verbose_output):
    print("\n[阶段 3/3] 角色卡详细对比报告: 潜在的相似项 (非精确重复)...")
    potential_similar_items_by_name = collections.defaultdict(set)
    found_any_potential_similarity_in_phase3 = False

    for initial_name, group_p_info_list in processed_groups_with_data.items():
        if len(group_p_info_list) < 2: continue
        for i in range(len(group_p_info_list)):
            for j in range(i + 1, len(group_p_info_list)):
                p_info1, p_info2 = group_p_info_list[i], group_p_info_list[j]
                if not (p_info1.is_character_card and p_info2.is_character_card and \
                        p_info1.file_hash and p_info2.file_hash and \
                        p_info1.detailed_chara_data and p_info2.detailed_chara_data):
                    if verbose_output: print(f"  跳过比较(P3): {os.path.basename(p_info1.new_filepath)} vs {os.path.basename(p_info2.new_filepath)} (非角色卡或数据不全)")
                    continue
                if p_info1.file_hash == p_info2.file_hash: continue
                meta_similar = compare_detailed_chara_data(p_info1.detailed_chara_data, p_info2.detailed_chara_data)
                visual_similar = compare_dhashes(p_info1.dhash, p_info2.dhash)
                if meta_similar or visual_similar:
                    potential_similar_items_by_name[initial_name].add(p_info1.new_filepath)
                    potential_similar_items_by_name[initial_name].add(p_info2.new_filepath)
                    found_any_potential_similarity_in_phase3 = True

    if not found_any_potential_similarity_in_phase3:
        print("  未找到其他潜在的相似角色卡。")
    else:
        print("\n--- 潜在的相似角色卡 (非精确重复，按元数据名分组) ---")
        ScriptUtils.print_sorted_file_group(potential_similar_items_by_name, directory_base)
        
    return potential_similar_items_by_name

def _get_p_info_by_rel_path(rel_path: str, initial_name: str, all_processed_data_groups: Dict[str, List[ProcessedFileInfo]], base_dir: str) -> Optional[ProcessedFileInfo]:
    abs_path = os.path.join(base_dir, rel_path)
    if initial_name in all_processed_data_groups:
        for p_info in all_processed_data_groups[initial_name]:
            if p_info.new_filepath == abs_path: return p_info
    return None

def _phase4_generate_fine_grained_report(
    potential_similar_groups_from_phase3: Dict[str, Set[str]],
    all_processed_data_groups: Dict[str, List[ProcessedFileInfo]],
    directory_base: str
):
    print("\n[阶段 4/可选] 更精细的角色卡相似性报告 (Type A, B, C)...")
    if not potential_similar_groups_from_phase3: print("  阶段3未识别出可供精细报告的组。"); return

    report_type_a: Dict[str, List[Tuple[str, str]]] = collections.defaultdict(list)
    report_type_b: Dict[str, List[Tuple[str, str]]] = collections.defaultdict(list)
    report_type_c: Dict[str, List[Tuple[str, str]]] = collections.defaultdict(list)
    processed_pairs_for_phase4: Set[Tuple[str, str]] = set()

    for initial_name, filepaths_abs_in_group_set in potential_similar_groups_from_phase3.items():
        if initial_name not in all_processed_data_groups: continue
        current_group_p_infos_dict: Dict[str, ProcessedFileInfo] = {
            p.new_filepath: p for p in all_processed_data_groups[initial_name] if p.is_character_card
        }
        current_group_p_infos_list = [current_group_p_infos_dict[fp] for fp in filepaths_abs_in_group_set if fp in current_group_p_infos_dict]
        if len(current_group_p_infos_list) < 2: continue

        for i in range(len(current_group_p_infos_list)):
            for j in range(i + 1, len(current_group_p_infos_list)):
                p_info1, p_info2 = current_group_p_infos_list[i], current_group_p_infos_list[j]
                if not (p_info1.file_hash and p_info2.file_hash and \
                        p_info1.detailed_chara_data and p_info2.detailed_chara_data): continue
                if p_info1.file_hash == p_info2.file_hash: continue
                pair_key_abs = tuple(sorted((p_info1.new_filepath, p_info2.new_filepath)))
                if pair_key_abs in processed_pairs_for_phase4: continue
                processed_pairs_for_phase4.add(pair_key_abs)
                meta_similar = compare_detailed_chara_data(p_info1.detailed_chara_data, p_info2.detailed_chara_data)
                visual_similar = compare_dhashes(p_info1.dhash, p_info2.dhash)
                path1_rel = os.path.relpath(p_info1.new_filepath, directory_base)
                path2_rel = os.path.relpath(p_info2.new_filepath, directory_base)
                size1_text, size1_total = p_info1.file_text_size_kb, p_info1.file_total_size_kb
                size2_text, size2_total = p_info2.file_text_size_kb, p_info2.file_total_size_kb
                if (size1_text > size2_text) or \
                   (size1_text == size2_text and size1_total > size2_total) or \
                   (size1_text == size2_text and size1_total == size2_total and path1_rel < path2_rel):
                    ordered_pair_paths_relative = (path1_rel, path2_rel)
                else: ordered_pair_paths_relative = (path2_rel, path1_rel)
                if meta_similar and visual_similar: report_type_a[initial_name].append(ordered_pair_paths_relative)
                elif meta_similar: report_type_b[initial_name].append(ordered_pair_paths_relative)
                elif visual_similar: report_type_c[initial_name].append(ordered_pair_paths_relative)

    if not any([report_type_a, report_type_b, report_type_c]): print("  未找到符合 Type A, B, C 分类的相似角色卡。")
    else:
        def output_sorted_pairs(report_dict: Dict[str, List[Tuple[str,str]]], type_name: str, base_dir_for_lookup: str, all_data_groups_for_lookup: Dict[str, List[ProcessedFileInfo]]):
            print(f"\n  Type {type_name}:")
            for name, pairs_list in sorted(report_dict.items()):
                def get_sort_key_for_pair(pair_tuple: Tuple[str,str]):
                    p_info_first = _get_p_info_by_rel_path(pair_tuple[0], name, all_data_groups_for_lookup, base_dir_for_lookup)
                    if p_info_first:
                        return (-p_info_first.file_text_size_kb, -p_info_first.file_total_size_kb, pair_tuple[0], pair_tuple[1])
                    return (0,0, pair_tuple[0], pair_tuple[1])
                sorted_pairs_list = sorted(pairs_list, key=get_sort_key_for_pair)
                print(f"    {name}:")
                for p1, p2 in sorted_pairs_list: print(f"      - {p1}\n      - {p2}")
        if report_type_a: output_sorted_pairs(report_type_a, "A (角色卡元数据和视觉均相似)", directory_base, all_processed_data_groups)
        if report_type_b: output_sorted_pairs(report_type_b, "B (仅角色卡元数据相似)", directory_base, all_processed_data_groups)
        if report_type_c: output_sorted_pairs(report_type_c, "C (仅角色卡视觉相似)", directory_base, all_processed_data_groups)
    print("--- 精细报告结束 ---")


def save_rename_log(log_entries: List[Dict[str, str]], log_filepath: str):
    if not log_entries:
        return
    try:
        os.makedirs(os.path.dirname(log_filepath), exist_ok=True)
        with open(log_filepath, 'w', encoding='utf-8') as f:
            json.dump(log_entries, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"\n  错误：无法保存日志文件到 {log_filepath}，原因: {e}")

def rename_and_detect_duplicates_recursive(directory: str, verbose_rename_output: bool):
    print(f"\n--- 开始处理目录: {directory} ---"); start_time = time.time()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, "log-png")
    log_filename = f"rename_log_{time.strftime('%Y%m%d_%H%M%S')}.json"
    log_filepath = os.path.join(log_dir, log_filename)
    
    rename_log_entries: List[Dict[str, str]] = []

    character_cards_info_list = _phase1_scan_and_rename(directory, verbose_rename_output, rename_log_entries)
    
    if rename_log_entries:
        save_rename_log(rename_log_entries, log_filepath)
        print(f"\n  阶段1发生 {len(rename_log_entries)} 次重命名, 临时日志已创建: {log_filepath}")

    if not character_cards_info_list:
        print("  操作结束 (阶段1未识别出可供进一步分析的角色卡)。")
        if rename_log_entries:
            print(f"  最终日志已确认保存。")
        return

    processed_chara_groups_with_data = _phase2_identify_groups_and_compute_data(character_cards_info_list, directory, verbose_rename_output)
    potential_similar_chara_groups_for_phase4 = _phase3_detailed_comparison_report(processed_chara_groups_with_data, directory, verbose_rename_output)
    
    end_time = time.time()
    print(f"\n--- 主要阶段处理完成 (扫描了 {GLOBAL_FILE_COUNTER} 个PNG文件) ---"); print(f"总耗时: {end_time - start_time:.2f} 秒")

    if rename_log_entries:
        save_rename_log(rename_log_entries, log_filepath) # 更新最终日志
        print(f"  包含 {len(rename_log_entries)} 条记录的最终操作日志已保存/更新到: {log_filepath}")
    else:
        print("  本次操作没有执行任何文件重命名。")

    if potential_similar_chara_groups_for_phase4 and any(len(s) > 1 for s in potential_similar_chara_groups_for_phase4.values()):
        if input("\n是否生成更精细的角色卡相似性报告 (阶段4)? (y/n, 默认 n): ").strip().lower() == 'y':
            _phase4_generate_fine_grained_report(potential_similar_chara_groups_for_phase4, processed_chara_groups_with_data, directory)
        else: print("  已跳过生成精细报告。")
    else: print("  阶段3未发现可供精细报告的角色卡组，跳过阶段4询问。")

def undo_renames_from_log():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, "log-png")

    if not os.path.isdir(log_dir) or not os.listdir(log_dir):
        print(f"\n错误: 未找到 '{log_dir}' 文件夹或其中没有任何日志文件。")
        return

    log_files = sorted([f for f in os.listdir(log_dir) if f.lower().endswith(".json")], reverse=True)
    if not log_files:
        print(f"\n错误: '{log_dir}' 文件夹中没有找到 .json 日志文件。")
        return
        
    print("\n请选择要用于撤销操作的日志文件:")
    for i, f in enumerate(log_files):
        print(f"  {i+1}. {f}")
    
    log_path_to_undo = None
    try:
        choice_str = input(f"请输入选项 (1-{len(log_files)}), 或输入 0 取消: ").strip()
        if choice_str == '0':
             print("  操作已取消。")
             return
        choice_idx = int(choice_str) - 1
        if 0 <= choice_idx < len(log_files):
            log_path_to_undo = os.path.join(log_dir, log_files[choice_idx])
        else:
            print("  无效的选项。")
            return
    except (ValueError, IndexError):
        print("  输入无效，请输入一个列表中的数字。")
        return

    try:
        with open(log_path_to_undo, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
        print(f"  读取日志文件时发生错误: {e}")
        return

    if not isinstance(log_data, list) or not all(isinstance(i, dict) and 'original_path' in i and 'new_path' in i for i in log_data):
        print("  错误: 日志文件内容格式不符合预期。")
        return

    if not log_data:
        print("  日志文件为空，无需执行任何操作。")
        return

    print(f"\n即将根据日志文件 '{os.path.basename(log_path_to_undo)}' 撤销 {len(log_data)} 个文件重命名。")
    if input("  请确认是否继续? (y/n): ").strip().lower() != 'y':
        print("  操作已由用户取消。")
        return

    undone_count, skipped_count, error_count = 0, 0, 0
    for entry in reversed(log_data):
        original_path, new_path = entry['original_path'], entry['new_path']
        if not os.path.exists(new_path):
            print(f"  跳过: 文件 '{new_path}' 不存在，可能已被移动或删除。")
            skipped_count += 1
            continue
        if os.path.exists(original_path):
            print(f"  跳过: 目标路径 '{original_path}' 已存在文件，为防止覆盖已跳过。")
            skipped_count += 1
            continue
        try:
            os.rename(new_path, original_path)
            print(f"  成功: '{os.path.basename(new_path)}' -> '{os.path.basename(original_path)}'")
            undone_count += 1
        except OSError as e:
            print(f"  错误: 无法撤销 '{new_path}' -> '{original_path}': {e}")
            error_count += 1

    ScriptUtils.print_undo_summary(undone_count, skipped_count, error_count)
    
    while True:
        delete_choice = input(f"\n是否删除此日志文件 '{os.path.basename(log_path_to_undo)}'? (y/n): ").lower()
        if delete_choice == 'y':
            try:
                os.remove(log_path_to_undo)
                print(f"  日志文件 '{os.path.basename(log_path_to_undo)}' 已删除。")
            except OSError as e:
                print(f"  删除日志文件失败: {e}")
            break
        elif delete_choice == 'n':
            print("  日志文件已保留。")
            break
        else:
            print("  无效的输入，请输入 'y' 或 'n'。")

def main():
    root_tk_for_dialog = tkinter.Tk(); root_tk_for_dialog.withdraw()
    while True:
        print(f"\nPNG角色卡、NAI/SD参数图、纯图片处理工具 ({PROGRAM_VERSION})")
        print("  1. [批量] 处理PNGs (脚本所在文件夹)")
        print("  2. [批量] 处理PNGs (选择其他文件夹)")
        print("  3. [单文件] 查看PNG tEXt元数据 (控制台)")
        print("  4. [撤销] 根据log日志撤销重命名操作")
        print("  0. 退出")
        choice = input("选项 (0-4): ").strip(); target_directory = ""
        verbose_rename_output_flag = False

        if choice == '1': target_directory = os.path.dirname(os.path.abspath(__file__))
        elif choice == '2':
            selected_dir = filedialog.askdirectory(title="选择包含PNG文件的文件夹")
            if selected_dir: target_directory = selected_dir
            else: print("  未选文件夹。"); continue
        elif choice == '3': view_png_all_text_chunks_console(); continue
        elif choice == '4': undo_renames_from_log(); continue
        elif choice == '0': print("  退出。"); break
        else: print("  无效选项。"); continue

        if target_directory:
            print(f"  将处理: {target_directory}")
            show_details_prompt = ("  是否输出详细的重命名过程 (阶段1)? (y/n, 默认 n): ")
            show_details = input(show_details_prompt).strip().lower()
            verbose_rename_output_flag = (show_details == 'y')
            if "SillyTavern" in target_directory and "characters" in target_directory.lower():
                print("\n  ST警告: 目标为SillyTavern角色卡文件夹。")
                if input("  确认处理? (yes/no): ").strip().lower() != 'yes': print("  操作取消。"); continue
            rename_and_detect_duplicates_recursive(target_directory, verbose_rename_output_flag)
            print("\n批量操作完成。")
    try: root_tk_for_dialog.destroy()
    except tkinter.TclError: pass

if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        target_directory = None  
        if os.path.isdir(input_path):
            target_directory = input_path
            print(f"检测到拖放文件夹，将处理目录: {target_directory}")

        elif os.path.isfile(input_path):
            if input_path.lower().endswith('.png'):
                target_directory = os.path.dirname(input_path)
                print(f"检测到拖放单个PNG文件，将处理其所在目录: {target_directory}")
            else:
                input(f"错误：您拖放了一个非PNG文件。\n请拖放单个PNG文件、或包含PNG文件的整个文件夹。\n\n文件: {input_path}\n按回车键退出。")
                sys.exit(1)

        else:
            input(f"错误：提供的路径无效或不存在。\n路径: {input_path}\n按回车键退出。")
            sys.exit(1)

        if "SillyTavern" in target_directory and "characters" in target_directory.lower():
            print("\n  ST警告: 目标为SillyTavern角色卡文件夹。")
            if input("  确认处理? (yes/no): ").strip().lower() != 'yes':
                print("  操作取消。")
                sys.exit(0)

        # 在拖放模式下，默认不显示详细重命名过程 (verbose_rename_output_flag = False)
        rename_and_detect_duplicates_recursive(target_directory, False)
        input("\n批量操作完成。按回车键退出。")

    else:
        # 如果没有拖放操作，则进入原有的交互式菜单模式
        main()