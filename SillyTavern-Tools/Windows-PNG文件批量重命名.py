import base64
import zlib
import png # pypng
import json
import os
import re
import collections
import time
import hashlib
import tkinter # 仅用于 filedialog
from tkinter import filedialog
from PIL import Image # Pillow
from typing import Optional, List, Tuple, Dict, Any, Set
from dataclasses import dataclass, field
import math # For ceil

# === 全局配置 ===
PROGRAM_VERSION = "v4.9-PureImageHandle"
DHASH_SIZE = 8
DHASH_SIMILARITY_THRESHOLD = 10
SD_RAW_TEXT_PARAM_KEYWORDS = ["steps:", "sampler:", "cfg scale:", "seed:", "size:", "model hash:", "model:"]
NAI_SOFTWARE_TAG_LOWER = "novelai"
NAI_COMMENT_JSON_EXPECTED_KEYS = {"prompt", "steps", "sampler", "seed", "uc"}

# --- 新增信号常量 ---
SIGNAL_PIC_CHARA_CARD = "CHARA_CARD" # 用于区分角色卡和其他图片类型
SIGNAL_PIC_NAI_PARAMS = "__PIC_NAI_PARAMS__"
SIGNAL_PIC_SD_PARAMS = "__PIC_SD_PARAMS__"
SIGNAL_PIC_MIXED_SOURCE = "__PIC_MIXED_SOURCE__"
SIGNAL_PIC_NO_TEXT_PURE_IMAGE = "__PIC_NO_TEXT_PURE_IMAGE__" # 修改
SIGNAL_SKIP_OTHER_TEXT_NO_TYPE = "__SKIP__OTHER_TEXT_NO_RECOGNIZED_TYPE__"
SIGNAL_SKIP_FILE_ERROR = "__SKIP__FILE_ERROR__"
SIGNAL_SKIP_UNKNOWN_READ_ERROR = "__SKIP__UNKNOWN_READ_ERROR__"
SIGNAL_UNKNOWN_CHARA_NO_NAME = "UnknownChara_NoName"
SIGNAL_UNKNOWN_CHARA_PARSE_ERROR = "UnknownChara_ParseError"


# === 数据类定义 ===
@dataclass
class DetailedCharaData:
    norm_name: Optional[str] = None
    norm_first_mes: Optional[str] = None
    book_entries_set_str: Optional[str] = None

@dataclass
class ProcessedFileInfo:
    original_filepath: str
    new_filepath: str
    # initial_meta_name: 对于角色卡是名字，对于参数图/纯图片是类型信号
    initial_meta_name_or_type_signal: str 
    is_character_card: bool = False
    is_sd_params_pic: bool = False
    is_nai_params_pic: bool = False
    is_mixed_source_pic: bool = False
    is_pure_image_pic: bool = False # 新增
    file_total_size_kb: int = 0
    file_text_size_kb: int = 0
    chara_json_str: Optional[str] = None # 仅角色卡
    file_hash: Optional[str] = None
    dhash: Optional[str] = None
    detailed_chara_data: Optional[DetailedCharaData] = None # 仅角色卡

@dataclass
class PureImagePendingRenameInfo: # 用于暂存待用户确认重命名的纯图片信息
    original_filepath: str
    target_new_filename_base: str # 不含后缀和冲突处理的 _idx
    root_path: str
    file_total_size_kb: int

# === 辅助函数 - PNG元数据处理 ===
def _is_sd_parameter_text_content(text_content: str) -> bool:
    if not text_content: return False
    text_lower = text_content.lower()
    matches = sum(1 for keyword in SD_RAW_TEXT_PARAM_KEYWORDS if keyword in text_lower)
    return matches >= 2

def _is_nai_parameter_json_content_in_comment(comment_json_str: Optional[str]) -> bool:
    if not comment_json_str: return False
    try:
        data = json.loads(comment_json_str)
        if not isinstance(data, dict): return False
        present_keys = sum(1 for key in NAI_COMMENT_JSON_EXPECTED_KEYS if key in data)
        return present_keys >= (len(NAI_COMMENT_JSON_EXPECTED_KEYS) -1)
    except json.JSONDecodeError: return False

def read_chara_json_and_text_size_from_png(png_file_path: str) -> Tuple[Optional[str], int, str]:
    total_text_chunk_bytes = 0; has_any_text_chunk = False
    chara_payload: Optional[str] = None; initial_chara_name_signal: Optional[str] = None
    sd_parameters_text: Optional[str] = None
    nai_comment_json_text: Optional[str] = None
    software_tag_text: Optional[str] = None
    source_tag_text: Optional[str] = None

    try:
        with open(png_file_path, 'rb') as f:
            reader = png.Reader(file=f); raw_chunks = list(reader.chunks()) # type: ignore
            for chunk_type, chunk_data in raw_chunks:
                if chunk_type == b'tEXt':
                    has_any_text_chunk = True
                    total_text_chunk_bytes += len(chunk_data) # 累加原始chunk数据长度
                    try:
                        keyword_bytes, text_bytes_raw = chunk_data.split(b'\x00', 1)
                        keyword_str_lower = keyword_bytes.decode('utf-8', errors='ignore').lower()
                        if keyword_str_lower == 'chara':
                            processed_chara_text_bytes = text_bytes_raw
                            try: processed_chara_text_bytes = zlib.decompress(processed_chara_text_bytes)
                            except zlib.error: pass
                            try:
                                decoded_base64_bytes = base64.b64decode(processed_chara_text_bytes)
                                chara_payload_temp = decoded_base64_bytes.decode('utf-8')
                                data_root = json.loads(chara_payload_temp)
                                name_from_data = data_root.get("data", {}).get("name") if isinstance(data_root.get("data"), dict) else None
                                if isinstance(name_from_data, str) and name_from_data.strip():
                                    initial_chara_name_signal = sanitize_filename_component(name_from_data.strip())
                                else: # 尝试顶层name/displayName
                                    name_top = data_root.get("name"); disp_name_top = data_root.get("displayName")
                                    chosen_name = (name_top.strip() if isinstance(name_top, str) and name_top.strip() else 
                                                   (disp_name_top.strip() if isinstance(disp_name_top, str) and disp_name_top.strip() else None))
                                    initial_chara_name_signal = sanitize_filename_component(chosen_name) if chosen_name else SIGNAL_UNKNOWN_CHARA_NO_NAME
                                chara_payload = chara_payload_temp
                            except Exception: initial_chara_name_signal = SIGNAL_UNKNOWN_CHARA_PARSE_ERROR
                        elif keyword_str_lower == 'parameters':
                            try: sd_parameters_text = text_bytes_raw.decode('utf-8', errors='strict')
                            except UnicodeDecodeError: pass
                        elif keyword_str_lower == 'comment':
                            try: nai_comment_json_text = text_bytes_raw.decode('utf-8', errors='strict')
                            except UnicodeDecodeError: pass
                        elif keyword_str_lower == 'software':
                            try: software_tag_text = text_bytes_raw.decode('utf-8', errors='strict')
                            except UnicodeDecodeError: pass
                        elif keyword_str_lower == 'source':
                            try: source_tag_text = text_bytes_raw.decode('utf-8', errors='strict')
                            except UnicodeDecodeError: pass
                    except ValueError: pass 

            if not has_any_text_chunk: return None, 0, SIGNAL_PIC_NO_TEXT_PURE_IMAGE # 修改

            if chara_payload and initial_chara_name_signal and \
               initial_chara_name_signal != SIGNAL_UNKNOWN_CHARA_NO_NAME and \
               initial_chara_name_signal != SIGNAL_UNKNOWN_CHARA_PARSE_ERROR:
                return chara_payload, total_text_chunk_bytes, initial_chara_name_signal # 角色卡信号是名字
            
            is_nai_software = software_tag_text and NAI_SOFTWARE_TAG_LOWER in software_tag_text.lower()
            is_nai_comment_valid = _is_nai_parameter_json_content_in_comment(nai_comment_json_text)
            if is_nai_software and is_nai_comment_valid: return None, total_text_chunk_bytes, SIGNAL_PIC_NAI_PARAMS

            if sd_parameters_text and _is_sd_parameter_text_content(sd_parameters_text):
                return None, total_text_chunk_bytes, SIGNAL_PIC_SD_PARAMS
            
            is_sd_in_source = source_tag_text and ("stable diffusion" in source_tag_text.lower() or "sd" in source_tag_text.lower())
            if is_nai_software and is_sd_in_source: return None, total_text_chunk_bytes, SIGNAL_PIC_MIXED_SOURCE

            return None, total_text_chunk_bytes, SIGNAL_SKIP_OTHER_TEXT_NO_TYPE

    except (FileNotFoundError, png.FormatError): return None, 0, SIGNAL_SKIP_FILE_ERROR
    except Exception: return None, 0, SIGNAL_SKIP_UNKNOWN_READ_ERROR

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

# === 辅助函数 - 文件名、哈希、dhash、中文检测 ===
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
    # 匹配 Pic-纯图片-XXXKB-Counter.png
    pure_match = re.search(r'Pic-纯图片-(\d+)KB-\d+.*?\.png$', filename_basename)
    if pure_match:
        try: return (int(pure_match.group(1)), 0, filename_basename) # 纯图片 text_size_kb 视为 0
        except ValueError: pass
    # 匹配 Name-XXXKB&YYYKB-Counter.png
    text_match = re.search(r'-(\d+)KB&(\d+)KB-\d+.*?\.png$', filename_basename)
    if text_match:
        try: return (int(text_match.group(1)), int(text_match.group(2)), filename_basename)
        except ValueError: pass
    return (0, 0, filename_basename)

# === 查看PNG的tEXt Chunks (输出到控制台) ===
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
            reader = png.Reader(file=f); # type: ignore
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

# === 核心处理函数 ===
GLOBAL_FILE_COUNTER = 0

def _phase1_scan_and_rename(directory: str, verbose_output_for_rename: bool) -> List[ProcessedFileInfo]:
    global GLOBAL_FILE_COUNTER; GLOBAL_FILE_COUNTER = 0
    character_cards_info: List[ProcessedFileInfo] = []
    skipped_count_various_reasons = 0; files_iterated_in_walk = 0
    renamed_sd_params_count = 0; renamed_nai_params_count = 0
    renamed_mixed_source_count = 0; renamed_pure_image_count = 0 # 新增纯图片计数
    
    # 用于暂存原始文件名含中文的纯图片，等待用户确认是否重命名
    pure_image_cjk_filenames_to_rename_later: List[PureImagePendingRenameInfo] = []

    print("\n[阶段 1/3] 逐一扫描、重命名PNG文件...")
    for root, _, files in os.walk(directory):
        relative_root_path = os.path.relpath(root, directory)
        if relative_root_path == ".": relative_root_path = ""
        renames_in_current_root_chara = 0; renames_in_current_root_sd = 0
        renames_in_current_root_nai = 0; renames_in_current_root_mixed = 0
        renames_in_current_root_pure = 0 # 当前目录纯图片计数

        for filename in files:
            files_iterated_in_walk +=1
            if not filename.lower().endswith(".png"): continue
            original_filepath = os.path.join(root, filename)
            payload_str, total_text_chunk_size_bytes, name_or_type_signal = \
                read_chara_json_and_text_size_from_png(original_filepath)
            
            is_character_card = (name_or_type_signal not in [
                SIGNAL_PIC_NAI_PARAMS, SIGNAL_PIC_SD_PARAMS, SIGNAL_PIC_MIXED_SOURCE,
                SIGNAL_PIC_NO_TEXT_PURE_IMAGE, SIGNAL_SKIP_OTHER_TEXT_NO_TYPE,
                SIGNAL_SKIP_FILE_ERROR, SIGNAL_SKIP_UNKNOWN_READ_ERROR,
                SIGNAL_UNKNOWN_CHARA_NO_NAME, SIGNAL_UNKNOWN_CHARA_PARSE_ERROR
            ] and name_or_type_signal is not None) # 角色卡信号是名字

            is_sd_params = (name_or_type_signal == SIGNAL_PIC_SD_PARAMS)
            is_nai_params = (name_or_type_signal == SIGNAL_PIC_NAI_PARAMS)
            is_mixed_source = (name_or_type_signal == SIGNAL_PIC_MIXED_SOURCE)
            is_pure_image = (name_or_type_signal == SIGNAL_PIC_NO_TEXT_PURE_IMAGE)

            if name_or_type_signal.startswith("__SKIP__"):
                skipped_count_various_reasons += 1
                if verbose_output_for_rename: print(f"  跳过(P1): {filename} (原因: {name_or_type_signal.split('__', 2)[-1]})")
                continue
            
            file_size_kb = 0; total_text_chunk_size_kb = 0
            try: file_size_kb = math.ceil(os.path.getsize(original_filepath) / 1024)
            except FileNotFoundError:
                if verbose_output_for_rename: print(f"  警告(P1): {filename} 大小获取失败，跳过。");
                skipped_count_various_reasons +=1; continue
            
            if not is_pure_image: # 只有非纯图片才计算文本大小
                 total_text_chunk_size_kb = math.ceil(total_text_chunk_size_bytes / 1024)

            base_name_for_file = name_or_type_signal 
            if is_sd_params: base_name_for_file = "Pic-SD参数"
            elif is_nai_params: base_name_for_file = "Pic-NAI参数"
            elif is_mixed_source: base_name_for_file = "Pic-混合来源"
            elif is_pure_image: base_name_for_file = "Pic-纯图片"
            
            if is_pure_image:
                new_filename_base = f"{base_name_for_file}-{file_size_kb}KB-{GLOBAL_FILE_COUNTER}"
            else: # 角色卡或其他有文本的图片
                new_filename_base = (f"{base_name_for_file}-"
                                     f"{file_size_kb}KB&{total_text_chunk_size_kb}KB-"
                                     f"{GLOBAL_FILE_COUNTER}")
            
            new_filename = new_filename_base + ".png"
            new_filepath_candidate = os.path.join(root, new_filename)
            
            _idx = 0; final_new_filepath = new_filepath_candidate
            while os.path.exists(final_new_filepath) and final_new_filepath != original_filepath:
                _idx += 1; final_new_filename_with_suffix = f"{new_filename_base}_{_idx}.png"
                final_new_filepath = os.path.join(root, final_new_filename_with_suffix)
            actual_new_filename_for_print = os.path.basename(final_new_filepath)
            
            renamed_this_file = False
            perform_rename_now = True

            if is_pure_image and _contains_chinese_char(filename):
                perform_rename_now = False # 默认不重命名含中文的纯图片
                pure_image_cjk_filenames_to_rename_later.append(
                    PureImagePendingRenameInfo(
                        original_filepath=original_filepath,
                        target_new_filename_base=new_filename_base, # Pic-纯图片-size-counter
                        root_path=root,
                        file_total_size_kb=file_size_kb
                    )
                )
                # 即使暂时不重命名，也计入纯图片总数，因为它可能稍后被重命名
                renames_in_current_root_pure += 1 
                renamed_pure_image_count += 1
                if verbose_output_for_rename:
                    print(f"  暂缓(P1): {filename} (纯图片,含中文,待确认) -> 目标: {actual_new_filename_for_print}")


            if perform_rename_now and original_filepath != final_new_filepath:
                if "SillyTavern" in root and "characters" in root.lower() and is_character_card:
                     print(f"  ST警告(P1): 重命名角色卡 {filename} -> {actual_new_filename_for_print}")
                try: os.rename(original_filepath, final_new_filepath); renamed_this_file = True
                except OSError as e:
                    if verbose_output_for_rename: print(f"  错误(P1): 重命名失败 {filename} -> {actual_new_filename_for_print}: {e}")
                    skipped_count_various_reasons +=1; continue 
            
            file_type_str = "无法识别类型"
            # 只有当实际执行了重命名，或者文件名原本就符合目标格式，或者是非中文纯图片时，才增加计数
            # 对于中文纯图片，计数已在上面处理
            if (renamed_this_file or (original_filepath == final_new_filepath and perform_rename_now)):
                if is_character_card: renames_in_current_root_chara += 1; file_type_str = "角色卡"
                elif is_sd_params: renames_in_current_root_sd +=1; file_type_str = "SD参数图"
                elif is_nai_params: renames_in_current_root_nai +=1; file_type_str = "NAI参数图"
                elif is_mixed_source: renames_in_current_root_mixed +=1; file_type_str = "混合来源图"
                elif is_pure_image and perform_rename_now: # 只有非中文纯图片执行了重命名才在这里计数
                    renames_in_current_root_pure += 1; file_type_str = "纯图片"; renamed_pure_image_count +=1
            
            if verbose_output_for_rename and renamed_this_file and perform_rename_now:
                 print(f"  {relative_root_path if relative_root_path else '.'}: {filename} -> {actual_new_filename_for_print} ({file_type_str})")
            
            # 只有非纯图片或者执行了重命名的纯图片才创建 ProcessedFileInfo 并加入列表
            # (因为纯图片且含中文的，如果用户选择不重命名，则不应进入后续分析)
            if not (is_pure_image and not perform_rename_now):
                p_info_obj = ProcessedFileInfo(
                    original_filepath=original_filepath, new_filepath=final_new_filepath,
                    initial_meta_name_or_type_signal=name_or_type_signal, 
                    chara_json_str=payload_str if is_character_card else None,
                    is_character_card=is_character_card,
                    is_sd_params_pic=is_sd_params,
                    is_nai_params_pic=is_nai_params,
                    is_mixed_source_pic=is_mixed_source,
                    is_pure_image_pic=is_pure_image, # 标记为纯图片
                    file_total_size_kb=file_size_kb, 
                    file_text_size_kb=total_text_chunk_size_kb if not is_pure_image else 0
                )
                if is_character_card: character_cards_info.append(p_info_obj)
                # SD, NAI, Mixed 的计数在 renamed_this_file or original_filepath == final_new_filepath 时已累加
                if is_sd_params and (renamed_this_file or original_filepath == final_new_filepath): renamed_sd_params_count +=1
                if is_nai_params and (renamed_this_file or original_filepath == final_new_filepath): renamed_nai_params_count +=1
                if is_mixed_source and (renamed_this_file or original_filepath == final_new_filepath): renamed_mixed_source_count +=1
                # 纯图片的 renamed_pure_image_count 已在上面处理
            
            GLOBAL_FILE_COUNTER += 1
        
        summary_parts = []
        if renames_in_current_root_chara > 0: summary_parts.append(f"角色卡 {renames_in_current_root_chara} 个")
        if renames_in_current_root_sd > 0: summary_parts.append(f"SD参数图 {renames_in_current_root_sd} 个")
        if renames_in_current_root_nai > 0: summary_parts.append(f"NAI参数图 {renames_in_current_root_nai} 个")
        if renames_in_current_root_mixed > 0: summary_parts.append(f"混合来源图 {renames_in_current_root_mixed} 个")
        if renames_in_current_root_pure > 0: summary_parts.append(f"纯图片 {renames_in_current_root_pure} 个")
        if summary_parts:
            print(f"  目录 {relative_root_path if relative_root_path else '.'}: 处理 " + ", ".join(summary_parts) + "。")

    print(f"\n--- 初步扫描与重命名摘要 (阶段 1 完成) ---")
    print(f"  总共迭代 {files_iterated_in_walk} 个文件系统条目。")
    print(f"  总共处理(重命名或检查) {GLOBAL_FILE_COUNTER} 个PNG文件。")
    print(f"    其中 {len(character_cards_info)} 个被识别为角色卡，将进入后续分析。")
    if renamed_sd_params_count > 0: print(f"    {renamed_sd_params_count} 个被识别为SD参数文件。")
    if renamed_nai_params_count > 0: print(f"    {renamed_nai_params_count} 个被识别为NAI参数文件。")
    if renamed_mixed_source_count > 0: print(f"    {renamed_mixed_source_count} 个被识别为混合来源文件。")
    if renamed_pure_image_count > 0: print(f"    {renamed_pure_image_count} 个被识别为纯图片文件 (部分可能待确认重命名)。") # 修改提示
    if skipped_count_various_reasons > 0: print(f"  跳过 {skipped_count_various_reasons} 个文件 (数据不足、错误等)。")
    
    if pure_image_cjk_filenames_to_rename_later:
        user_confirm_rename_cjk_pure = input(
            f"  检测到 {len(pure_image_cjk_filenames_to_rename_later)} 张无元数据且原始文件名含中文的PNG。"
            f"是否将这些文件也统一重命名为 \"Pic-纯图片-...\" 格式? (y/n, 默认 n): "
        ).strip().lower()
        if user_confirm_rename_cjk_pure == 'y':
            renamed_cjk_pure_count = 0
            for item_to_rename in pure_image_cjk_filenames_to_rename_later:
                # 重新构建目标文件名，因为全局计数器可能已变，但这里我们用之前的计数器值
                # 注意：new_filename_base 已经包含了正确的计数器
                new_filename = item_to_rename.target_new_filename_base + ".png"
                new_filepath_candidate = os.path.join(item_to_rename.root_path, new_filename)
                
                _idx_confirm = 0; final_new_filepath_confirm = new_filepath_candidate
                while os.path.exists(final_new_filepath_confirm) and final_new_filepath_confirm != item_to_rename.original_filepath:
                    _idx_confirm += 1
                    final_new_filename_with_suffix_confirm = f"{item_to_rename.target_new_filename_base}_{_idx_confirm}.png"
                    final_new_filepath_confirm = os.path.join(item_to_rename.root_path, final_new_filename_with_suffix_confirm)
                
                if item_to_rename.original_filepath != final_new_filepath_confirm:
                    try:
                        os.rename(item_to_rename.original_filepath, final_new_filepath_confirm)
                        renamed_cjk_pure_count +=1
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

def _phase2_identify_groups_and_compute_data(character_cards_info: List[ProcessedFileInfo], directory_base: str, verbose_output: bool) -> Dict[str, List[ProcessedFileInfo]]:
    print("\n[阶段 2/3] 角色卡分组、计算核心数据、检测精确重复...")
    grouped_by_initial_name: Dict[str, List[ProcessedFileInfo]] = collections.defaultdict(list)
    for p_info in character_cards_info:
        if p_info.is_character_card: grouped_by_initial_name[p_info.initial_meta_name_or_type_signal].append(p_info)
    
    processed_groups_filled_data: Dict[str, List[ProcessedFileInfo]] = {}
    exact_duplicates_by_meta_name: Dict[str, List[str]] = collections.defaultdict(list); found_any_exact_duplicates = False

    for initial_name, group_files_info_list in grouped_by_initial_name.items():
        if len(group_files_info_list) < 1: continue 
        files_in_group_with_data: List[ProcessedFileInfo] = []
        hashes_in_this_group: Dict[str, List[str]] = collections.defaultdict(list)
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
    if not found_any_exact_duplicates: print("  无")
    else:
        for meta_name, dup_paths_abs_list in sorted(exact_duplicates_by_meta_name.items()):
            sorted_dup_paths_abs = sorted(list(set(dup_paths_abs_list)),
                key=lambda p: _extract_size_info_from_filename(os.path.basename(p)))
            if len(sorted_dup_paths_abs) > 1:
                print(f"{meta_name}：")
                for fp_abs_path in sorted_dup_paths_abs: print(f"  - {os.path.relpath(fp_abs_path, directory_base)}")
    return processed_groups_filled_data

def _phase3_detailed_comparison_report(processed_groups_with_data: Dict[str, List[ProcessedFileInfo]], directory_base: str, verbose_output: bool) -> Dict[str, Set[str]]:
    print("\n[阶段 3/3] 角色卡详细对比报告: 潜在的相似项 (非精确重复)...")
    potential_similar_items_by_name: Dict[str, Set[str]] = collections.defaultdict(set)
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
    
    if not found_any_potential_similarity_in_phase3: print("  未找到其他潜在的相似角色卡。")
    else:
        print("\n--- 潜在的相似角色卡 (非精确重复，按元数据名分组) ---")
        for name, filepaths_abs_set in sorted(potential_similar_items_by_name.items()):
            if len(filepaths_abs_set) > 1 :
                sorted_filepaths_abs = sorted(list(filepaths_abs_set),
                    key=lambda p: _extract_size_info_from_filename(os.path.basename(p)))
                print(f"{name}：")
                for fp_abs_path in sorted_filepaths_abs: print(f"  - {os.path.relpath(fp_abs_path, directory_base)}")
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

def rename_and_detect_duplicates_recursive(directory: str, verbose_rename_output: bool):
    print(f"\n--- 开始处理目录: {directory} ---"); start_time = time.time()
    character_cards_info_list = _phase1_scan_and_rename(directory, verbose_rename_output)
    if not character_cards_info_list:
        print("  操作结束 (阶段1未识别出可供进一步分析的角色卡)。"); return
    processed_chara_groups_with_data = _phase2_identify_groups_and_compute_data(character_cards_info_list, directory, verbose_rename_output)
    potential_similar_chara_groups_for_phase4 = _phase3_detailed_comparison_report(processed_chara_groups_with_data, directory, verbose_rename_output)
    end_time = time.time()
    print(f"\n--- 主要阶段处理完成 (扫描了 {GLOBAL_FILE_COUNTER} 个PNG文件) ---"); print(f"总耗时: {end_time - start_time:.2f} 秒")
    if potential_similar_chara_groups_for_phase4 and any(len(s) > 1 for s in potential_similar_chara_groups_for_phase4.values()):
        if input("\n是否生成更精细的角色卡相似性报告 (阶段4)? (y/n, 默认 n): ").strip().lower() == 'y':
            _phase4_generate_fine_grained_report(potential_similar_chara_groups_for_phase4, processed_chara_groups_with_data, directory)
        else: print("  已跳过生成精细报告。")
    else: print("  阶段3未发现可供精细报告的角色卡组，跳过阶段4询问。")

# === 主函数 (main) ===
def main():
    root_tk_for_dialog = tkinter.Tk(); root_tk_for_dialog.withdraw()
    while True:
        print(f"\nPNG角色卡、NAI/SD参数图、纯图片处理工具 ({PROGRAM_VERSION})")
        print("  1. [批量] 处理PNGs (脚本所在文件夹)")
        print("  2. [批量] 处理PNGs (选择其他文件夹)")
        print("  3. [单文件] 查看PNG tEXt元数据 (控制台)")
        print("  0. 退出")
        choice = input("选项 (0-3): ").strip(); target_directory = ""
        verbose_rename_output_flag = False

        if choice == '1': target_directory = os.path.dirname(os.path.abspath(__file__))
        elif choice == '2':
            selected_dir = filedialog.askdirectory(title="选择包含PNG文件的文件夹")
            if selected_dir: target_directory = selected_dir
            else: print("  未选文件夹。"); continue
        elif choice == '3': view_png_all_text_chunks_console(); continue
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
    main()
