import base64
import zlib
from PIL import Image
import sys
import png
import json
import os
import re
import collections
import subprocess
import time
import hashlib
from typing import Optional, List, Tuple, Dict, Any, Set
from dataclasses import dataclass
import math

DHASH_SIZE = 8
DHASH_SIMILARITY_THRESHOLD = 10
SD_RAW_TEXT_PARAM_KEYWORDS = ["steps:", "sampler:", "cfg scale:", "seed:", "size:", "model hash:", "model:", "denoising strength:", "clip skip:"]
NAI_SOFTWARE_TAG_LOWER = "novelai"
NAI_COMMENT_JSON_EXPECTED_KEYS = {"prompt", "steps", "sampler", "seed", "uc", "scale"}

SIGNAL_PIC_NAI_PARAMS = "__PIC_NAI_PARAMS__"
SIGNAL_PIC_SD_PARAMS = "__PIC_SD_PARAMS__"
SIGNAL_PIC_MIXED_SOURCE = "__PIC_MIXED_SOURCE__"
SIGNAL_PIC_NO_TEXT_PURE_IMAGE = "__PIC_NO_TEXT_PURE_IMAGE__"
SIGNAL_SKIP_OTHER_TEXT_NO_TYPE = "__SKIP__OTHER_TEXT_NO_RECOGNIZED_TYPE__"
SIGNAL_SKIP_FILE_ERROR = "__SKIP__FILE_ERROR__"
SIGNAL_SKIP_UNKNOWN_READ_ERROR = "__SKIP__UNKNOWN_READ_ERROR__"
SIGNAL_UNKNOWN_CHARA_NO_NAME = "角色名未知"
SIGNAL_UNKNOWN_CHARA_PARSE_ERROR = "角色卡解析错误"

_ILLEGAL_FILENAME_CHARS_PATTERN = re.compile(r'[\\/:*?"<>|\r\n\t]')

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

class PNGTools:
    @staticmethod
    def sanitize_filename_component(filename_part: str) -> str:
        if not filename_part: return "未命名"
        return _ILLEGAL_FILENAME_CHARS_PATTERN.sub('_', filename_part).strip('_ ')

    @staticmethod
    def _contains_chinese_char(text: str) -> bool:
        for char_code in text:
            if '\u4e00' <= char_code <= '\u9fff': return True
        return False

    @staticmethod
    def calculate_file_hash(filepath: str) -> Optional[str]:
        hasher = hashlib.sha256()
        try:
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192): hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None

    @staticmethod
    def calculate_dhash(image_path: str) -> Optional[str]:
        try:
            img = Image.open(image_path).convert('L').resize(
                (DHASH_SIZE + 1, DHASH_SIZE), Image.Resampling.LANCZOS
            )
            return "".join(['1' if img.getpixel((c, r)) > img.getpixel((c + 1, r)) else '0'
                            for r in range(DHASH_SIZE) for c in range(DHASH_SIZE)])
        except Exception:
            return None

    @staticmethod
    def compare_dhashes(hash1: Optional[str], hash2: Optional[str]) -> bool:
        if not hash1 or not hash2 or len(hash1) != len(hash2): return False
        hamming_distance = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
        return hamming_distance <= DHASH_SIMILARITY_THRESHOLD

    @staticmethod
    def _is_sd_parameter_text_content(text_content: str) -> bool:
        if not text_content: return False
        text_lower = text_content.lower()
        matches = sum(1 for kw in SD_RAW_TEXT_PARAM_KEYWORDS if kw in text_lower)
        return matches >= 2

    @staticmethod
    def _is_nai_parameter_json_content_in_comment(comment_json_str: Optional[str]) -> bool:
        if not comment_json_str: return False
        try:
            data = json.loads(comment_json_str)
            if not isinstance(data, dict): return False
            return sum(1 for key in NAI_COMMENT_JSON_EXPECTED_KEYS if key in data) >= (len(NAI_COMMENT_JSON_EXPECTED_KEYS) - 1)
        except Exception:
            return False

    @staticmethod
    def read_png_metadata_and_classify(png_file_path: str) -> Tuple[Optional[str], int, str]:
        total_text_bytes = 0
        chara_payload: Optional[str] = None
        initial_name_signal: Optional[str] = None
        sd_text: Optional[str] = None
        nai_comment: Optional[str] = None
        software_tag: Optional[str] = None
        source_tag: Optional[str] = None
        has_text_chunks = False

        try:
            with open(png_file_path, 'rb') as f:
                reader = png.Reader(file=f)
                chunks = list(reader.chunks())
                if not chunks or chunks[0][0] != b'IHDR':
                    raise png.FormatError("无效PNG格式或数据块为空")

                for chunk_type_bytes, chunk_data_bytes in chunks:
                    if chunk_type_bytes == b'tEXt':
                        has_text_chunks = True
                        total_text_bytes += len(chunk_data_bytes)
                        try:
                            key_bytes, val_bytes = chunk_data_bytes.split(b'\x00', 1)
                            key_str_lower = key_bytes.decode('utf-8', errors='ignore').lower()
                            
                            if key_str_lower == 'chara':
                                processed_val_bytes = val_bytes
                                try:
                                    processed_val_bytes = zlib.decompress(processed_val_bytes)
                                except zlib.error:
                                    pass
                                try:
                                    chara_payload = base64.b64decode(processed_val_bytes).decode('utf-8')
                                    data_root = json.loads(chara_payload)
                                    name_val = (data_root.get("data", {}).get("name") 
                                                if isinstance(data_root.get("data"), dict) else None) or \
                                               data_root.get("name") or data_root.get("displayName")
                                    initial_name_signal = PNGTools.sanitize_filename_component(name_val.strip()) \
                                        if isinstance(name_val, str) and name_val.strip() else SIGNAL_UNKNOWN_CHARA_NO_NAME
                                except Exception:
                                    initial_name_signal = SIGNAL_UNKNOWN_CHARA_PARSE_ERROR
                            elif key_str_lower == 'parameters':
                                sd_text = val_bytes.decode('utf-8', errors='ignore')
                            elif key_str_lower == 'comment':
                                nai_comment = val_bytes.decode('utf-8', errors='ignore')
                            elif key_str_lower == 'software':
                                software_tag = val_bytes.decode('utf-8', errors='ignore')
                            elif key_str_lower == 'source':
                                source_tag = val_bytes.decode('utf-8', errors='ignore')
                        except ValueError:
                            pass
            
            if not has_text_chunks:
                return None, 0, SIGNAL_PIC_NO_TEXT_PURE_IMAGE
            
            if chara_payload and initial_name_signal and \
               initial_name_signal not in [SIGNAL_UNKNOWN_CHARA_NO_NAME, SIGNAL_UNKNOWN_CHARA_PARSE_ERROR]:
                return chara_payload, total_text_bytes, initial_name_signal
            
            is_nai_by_software_and_comment = software_tag and NAI_SOFTWARE_TAG_LOWER in software_tag.lower() and \
                                     PNGTools._is_nai_parameter_json_content_in_comment(nai_comment)
            is_sd_by_parameters = sd_text and PNGTools._is_sd_parameter_text_content(sd_text)
            is_mixed_by_tags = software_tag and source_tag and NAI_SOFTWARE_TAG_LOWER in software_tag.lower() and \
                               ("stable diffusion" in source_tag.lower() or "sd" in source_tag.lower())

            if is_nai_by_software_and_comment and not is_sd_by_parameters: 
                 return None, total_text_bytes, SIGNAL_PIC_NAI_PARAMS
            
            if is_sd_by_parameters:
                 return None, total_text_bytes, SIGNAL_PIC_SD_PARAMS

            if is_nai_by_software_and_comment: 
                 return None, total_text_bytes, SIGNAL_PIC_NAI_PARAMS

            if is_mixed_by_tags:
                return None, total_text_bytes, SIGNAL_PIC_MIXED_SOURCE
            
            return None, total_text_bytes, SIGNAL_SKIP_OTHER_TEXT_NO_TYPE

        except (FileNotFoundError, png.FormatError):
            return None, 0, SIGNAL_SKIP_FILE_ERROR
        except Exception:
            return None, 0, SIGNAL_SKIP_UNKNOWN_READ_ERROR

    @staticmethod
    def extract_and_normalize_key_chara_data(chara_json_str: Optional[str]) -> Optional[DetailedCharaData]:
        if not chara_json_str: return None
        try:
            data_root = json.loads(chara_json_str)
            data_source = data_root.get("data", data_root) if isinstance(data_root.get("data", data_root), dict) else data_root
            
            details = DetailedCharaData()
            name = data_source.get("name") or data_source.get("displayName")
            details.norm_name = name.strip().lower() if isinstance(name, str) and name.strip() else None
            
            first_mes = data_source.get("first_mes") or data_source.get("description")
            details.norm_first_mes = first_mes.strip() if isinstance(first_mes, str) else ""
            
            book_data = data_source.get("character_book") or data_source.get("char_book")
            entries_texts: List[str] = []
            if isinstance(book_data, dict) and isinstance(book_data.get("entries"), list):
                for entry in book_data["entries"]:
                    if isinstance(entry, dict):
                        content = entry.get("description") or entry.get("content") or entry.get("value") or \
                                  (entry.get("keys", [""])[0] if isinstance(entry.get("keys"), list) and entry.get("keys") else "")
                        if isinstance(content, str) and content.strip():
                            entries_texts.append(content.strip().lower())
            details.book_entries_set_str = "||".join(sorted(list(set(entries_texts)))) if entries_texts else ""
            return details
        except Exception:
            return None

    @staticmethod
    def compare_detailed_chara_data(d1: Optional[DetailedCharaData], d2: Optional[DetailedCharaData]) -> bool:
        if d1 is None and d2 is None: return True
        if d1 is None or d2 is None: return False
        return (d1.norm_name == d2.norm_name and
                d1.norm_first_mes == d2.norm_first_mes and
                d1.book_entries_set_str == d2.book_entries_set_str)

    @staticmethod
    def _extract_sort_keys_from_filename(filename_basename: str, p_info: Optional[ProcessedFileInfo]) -> Tuple[int, int, str]:
        if p_info:
            return (-p_info.file_text_size_kb, -p_info.file_total_size_kb, filename_basename)

        pure_match = re.search(r'Pic-纯图片-(\d+)KB-\d+.*?\.png$', filename_basename, re.IGNORECASE)
        if pure_match:
            try: return (0, -int(pure_match.group(1)), filename_basename)
            except ValueError: pass
        
        text_match = re.search(r'-((\d+)KB&(\d+)KB|(\d+)KB)-\d+.*?\.png$', filename_basename, re.IGNORECASE)
        if text_match:
            try:
                if text_match.group(2) and text_match.group(3): 
                    return (-int(text_match.group(3)), -int(text_match.group(2)), filename_basename)
                elif text_match.group(4): 
                     return (0, -int(text_match.group(4)), filename_basename)
            except ValueError: pass
        
        return (0, 0, filename_basename)

    @staticmethod
    def _set_clipboard_text_termux(text: str):
        if not text or not text.strip(): return
        try:
            process = subprocess.Popen(['termux-clipboard-set'], stdin=subprocess.PIPE, text=True, encoding='utf-8')
            process.communicate(text)
        except FileNotFoundError:
            print("\n" + PNGFileProcessor.SEP_LINE_WARN)
            print("!!! 剪贴板功能错误 !!!")
            print("  未找到 'termux-clipboard-set' 命令。")
            print("  请确保 Termux:API 已正确安装和配置。")
            print(PNGFileProcessor.SEP_LINE_WARN)
        except Exception as e:
            print(f"\n错误: 复制到剪贴板时发生意外: {e}")

class PNGFileProcessor:
    SEP_LINE_MAJOR = "=" * 60
    SEP_LINE_MINOR = "-" * 60
    SEP_LINE_DOT = "." * 60
    SEP_LINE_WARN = "!" * 60
    SEP_LINE_CLIP = "~" * 60
    SEP_LINE_FINAL = "*" * 60

    SD_SUBDIR_NAME = "SD"
    NAI_SUBDIR_NAME = "NAI"

    def __init__(self, base_directory: str, verbose_output: bool = False):
        self.base_directory = os.path.normpath(base_directory)
        self.verbose_output = verbose_output
        self.sd_subdir = os.path.join(self.base_directory, self.SD_SUBDIR_NAME)
        self.nai_subdir = os.path.join(self.base_directory, self.NAI_SUBDIR_NAME)
        
        self.processed_file_counter = 0
        self.all_processed_file_infos: List[ProcessedFileInfo] = []
        self.tools = PNGTools()
        self.total_input_wait_time = 0.0
        self.total_png_files_scanned_phase1 = 0
        
        if self.base_directory and os.path.isdir(os.path.dirname(self.base_directory)):
            os.makedirs(self.sd_subdir, exist_ok=True)
            os.makedirs(self.nai_subdir, exist_ok=True)

    def _timed_input(self, prompt_str: str) -> str:
        start_wait = time.perf_counter()
        user_res = input(prompt_str)
        end_wait = time.perf_counter()
        self.total_input_wait_time += (end_wait - start_wait)
        return user_res

    @staticmethod
    def _check_termux_storage_permission(path: str) -> bool:
        if not os.path.isdir(path) or not os.access(path, os.R_OK | os.W_OK):
            print("\n" + PNGFileProcessor.SEP_LINE_WARN)
            print("!!! 存储权限警告 !!!")
            print(f"  无法访问或写入目录: '{path}'")
            print("  请先在 Termux 中执行 'termux-setup-storage' 并授予权限。")
            print(PNGFileProcessor.SEP_LINE_WARN)
            return False
        return True

    def _sillytavern_warning_check(self, directory: str):
        path_l = directory.lower()
        st_keywords = ["sillytavern", "tavern", "agnai", "risuai", "chub", "characterai", "janitorai", "venus"]
        data_keywords = ["characters", "cards", "chats", "personas", "worlds", "lorebooks", "public", "backgrounds"]
        
        is_potential_st_dir = any(kw in path_l for kw in st_keywords) and \
                              any(dkw in path_l for dkw in data_keywords)
        if not is_potential_st_dir and os.path.basename(path_l) in ["characters", "cards"]:
            is_potential_st_dir = True

        if is_potential_st_dir:
            print("\n" + PNGFileProcessor.SEP_LINE_WARN)
            print(f"  警告: 目标目录 '{directory}'")
            print("  可能包含 SillyTavern 等应用的角色卡或数据。")
            print("  在此目录执行批量重命名可能导致应用无法正确识别文件。")
            print(PNGFileProcessor.SEP_LINE_WARN)
            confirm_prompt = ("  为确认风险并继续，请输入 'yes': ")
            if self._timed_input(confirm_prompt).strip().lower() != 'yes':
                print("\n操作已由用户取消。程序将退出。")
                sys.exit()
            print("\n风险已确认，即将继续...")

    def _get_p_info_by_abs_path(self, abs_path: str, all_data_groups: Dict[str, List[ProcessedFileInfo]]) -> Optional[ProcessedFileInfo]:
        for group_list in all_data_groups.values():
            for p_info in group_list:
                if p_info.new_filepath == abs_path:
                    return p_info
        return None
    
    def _generate_new_filepath(self, original_filepath: str, base_name_prefix: str, file_size_kb: int, text_size_kb: int, 
                                is_param_or_chara_type: bool, target_root_dir: str, current_counter_val: int) -> str:
        core_filename_part = f"{base_name_prefix}-{file_size_kb}KB" + \
                             (f"&{text_size_kb}KB" if is_param_or_chara_type else "") + \
                             f"-{current_counter_val}"
        
        new_filename_base_no_ext = core_filename_part
        conflict_idx = 0
        new_filepath_candidate = os.path.join(target_root_dir, new_filename_base_no_ext + ".png")
        
        while os.path.exists(new_filepath_candidate) and \
              original_filepath.lower() != new_filepath_candidate.lower():
            conflict_idx += 1
            new_filename_base_no_ext = f"{core_filename_part}_{conflict_idx}"
            new_filepath_candidate = os.path.join(target_root_dir, new_filename_base_no_ext + ".png")
        return new_filepath_candidate

    def _process_single_file(self, original_filepath: str, current_root_for_file: str, 
                             current_dir_stats: Dict[str, int], 
                             cjk_pending_list: Optional[List[PureImagePendingRenameInfo]] = None) -> Optional[ProcessedFileInfo]:
        payload_str, total_text_chunk_size_bytes, name_or_type_signal = \
            self.tools.read_png_metadata_and_classify(original_filepath)

        is_chara = (name_or_type_signal not in [
            SIGNAL_PIC_NAI_PARAMS, SIGNAL_PIC_SD_PARAMS, SIGNAL_PIC_MIXED_SOURCE, 
            SIGNAL_PIC_NO_TEXT_PURE_IMAGE, SIGNAL_SKIP_OTHER_TEXT_NO_TYPE, 
            SIGNAL_SKIP_FILE_ERROR, SIGNAL_SKIP_UNKNOWN_READ_ERROR, 
            SIGNAL_UNKNOWN_CHARA_NO_NAME, SIGNAL_UNKNOWN_CHARA_PARSE_ERROR
        ] and name_or_type_signal is not None)
        is_sd = (name_or_type_signal == SIGNAL_PIC_SD_PARAMS)
        is_nai = (name_or_type_signal == SIGNAL_PIC_NAI_PARAMS)
        is_mixed = (name_or_type_signal == SIGNAL_PIC_MIXED_SOURCE)
        is_pure = (name_or_type_signal == SIGNAL_PIC_NO_TEXT_PURE_IMAGE)
        
        is_param_or_chara_for_naming = is_chara or is_sd or is_nai or is_mixed

        if name_or_type_signal.startswith("__SKIP__"):
            current_dir_stats['跳过(错误或未知类型)'] += 1
            return None
        
        try:
            file_size_kb = math.ceil(os.path.getsize(original_filepath) / 1024)
        except FileNotFoundError:
            current_dir_stats['跳过(文件丢失)'] += 1
            return None
        
        text_size_kb = math.ceil(total_text_chunk_size_bytes / 1024) if not is_pure else 0
        
        base_name_prefix = ""
        if is_chara: base_name_prefix = name_or_type_signal
        elif is_sd: base_name_prefix = "Pic-SD-" 
        elif is_nai: base_name_prefix = "Pic-NAI-"
        elif is_mixed: base_name_prefix = "Pic-Mixed-"
        elif is_pure: base_name_prefix = "Pic-纯图片-"
        else: base_name_prefix = "未知类型-"


        target_directory_for_file = current_root_for_file 
        if is_sd: target_directory_for_file = self.sd_subdir
        elif is_nai: target_directory_for_file = self.nai_subdir
        
        self.processed_file_counter += 1
        actual_new_filepath = self._generate_new_filepath(
            original_filepath, base_name_prefix.strip('-'), file_size_kb, text_size_kb, 
            is_param_or_chara_for_naming, target_directory_for_file, self.processed_file_counter
        )
        
        perform_rename_now = True
        if is_pure and cjk_pending_list is not None and self.tools._contains_chinese_char(os.path.basename(original_filepath)):
            core_part_for_cjk = f"{base_name_prefix.strip('-')}-{file_size_kb}KB-{self.processed_file_counter}"
            cjk_pending_list.append(
                PureImagePendingRenameInfo(original_filepath, core_part_for_cjk, current_root_for_file, file_size_kb)
            )
            current_dir_stats['纯图片(中文名待确认)'] +=1
            perform_rename_now = False

        operation_done = False
        if perform_rename_now:
            if original_filepath.lower() != actual_new_filepath.lower():
                try:
                    os.makedirs(os.path.dirname(actual_new_filepath), exist_ok=True)
                    os.rename(original_filepath, actual_new_filepath)
                    operation_done = True
                except OSError as e:
                    if self.verbose_output:
                        print(f"  错误: 处理 '{os.path.basename(original_filepath)}' 失败: {e}")
                    current_dir_stats['跳过(重命名/移动失败)'] += 1
                    self.processed_file_counter -=1 
                    return None
            else: 
                operation_done = True
        
        if operation_done or not perform_rename_now:
            if operation_done and self.verbose_output and original_filepath.lower() != actual_new_filepath.lower():
                print(f"  处理: '{os.path.basename(original_filepath)}' -> '{os.path.basename(actual_new_filepath)}'")

            pfi = ProcessedFileInfo(
                original_filepath=original_filepath, new_filepath=actual_new_filepath if operation_done else original_filepath,
                initial_meta_name_or_type_signal=name_or_type_signal, 
                chara_json_str=payload_str if is_chara else None,
                is_character_card=is_chara, is_sd_params_pic=is_sd, is_nai_params_pic=is_nai,
                is_mixed_source_pic=is_mixed, is_pure_image_pic=is_pure,
                file_total_size_kb=file_size_kb, file_text_size_kb=text_size_kb
            )
            
            if operation_done:
                 if is_chara: current_dir_stats['角色卡'] +=1
                 elif is_sd: current_dir_stats['SD参数图'] +=1
                 elif is_nai: current_dir_stats['NAI参数图'] +=1
                 elif is_mixed: current_dir_stats['混合来源图'] +=1
                 elif is_pure: current_dir_stats['纯图片'] +=1
            
            return pfi
        
        self.processed_file_counter -=1 
        return None

    def _phase1_scan_and_rename(self) -> List[ProcessedFileInfo]:
        self.processed_file_counter = 0
        self.all_processed_file_infos = []
        self.total_png_files_scanned_phase1 = 0
        
        initial_counts = {
            '角色卡': 0, 'SD参数图': 0, 'NAI参数图': 0,
            '混合来源图': 0, '纯图片': 0, '纯图片(中文名待确认)':0,
            '跳过(错误或未知类型)':0, '跳过(文件丢失)':0, '跳过(重命名/移动失败)':0
        }
        overall_stats = collections.defaultdict(int, initial_counts)
        
        cjk_pending_rename_list: List[PureImagePendingRenameInfo] = []

        print("\n" + PNGFileProcessor.SEP_LINE_MAJOR)
        print("[阶段 1] 文件扫描、分类与初步重命名/移动")
        print(PNGFileProcessor.SEP_LINE_MAJOR)

        if self.verbose_output:
            print(f"\n  正在扫描主目录: {self.base_directory}")

        for root, dirs, files in os.walk(self.base_directory, topdown=True):
            relative_root_path = os.path.relpath(root, self.base_directory)
            current_path_display = "根目录(.)" if relative_root_path == "." else f"目录 '{relative_root_path}'"
            current_dir_stats = collections.defaultdict(int)
            processed_in_current_dir_flag = False

            for filename in files:
                if not filename.lower().endswith(".png"): continue
                self.total_png_files_scanned_phase1 +=1
                
                original_filepath = os.path.join(root, filename)
                pfi = self._process_single_file(original_filepath, root, current_dir_stats, cjk_pending_rename_list)
                if pfi:
                    self.all_processed_file_infos.append(pfi)
                    processed_in_current_dir_flag = True
            
            for key, value in current_dir_stats.items(): overall_stats[key] += value
            
            current_dir_summary_parts = [f"{k} {v}个" for k,v in current_dir_stats.items() if v>0 and not k.startswith("跳过") and k != '纯图片(中文名待确认)']
            if current_dir_summary_parts :
                 print(f"  {current_path_display}: 处理 " + ", ".join(current_dir_summary_parts) + "。")
            elif processed_in_current_dir_flag and not current_dir_summary_parts and current_dir_stats['纯图片(中文名待确认)'] > 0: 
                 print(f"  {current_path_display}: 有 {current_dir_stats['纯图片(中文名待确认)']} 个纯图片(中文名待确认)。")


        confirmed_cjk_rename_count = 0
        if cjk_pending_rename_list:
            print("\n" + PNGFileProcessor.SEP_LINE_MINOR)
            print(f"注意: 检测到 {len(cjk_pending_rename_list)} 张纯图片的原始文件名含中文。")
            cjk_confirm_prompt = ("是否统一按标准格式重命名这些中文名纯图片? (y/n, 默认 n): ")
            if self._timed_input(cjk_confirm_prompt).strip().lower() == 'y':
                print("  正在重命名用户确认的中文名纯图片...")
                for item_to_rename in cjk_pending_rename_list:
                    pfi_to_update = next((p for p in self.all_processed_file_infos if p.original_filepath == item_to_rename.original_filepath and not p.is_character_card and not p.is_sd_params_pic and not p.is_nai_params_pic and not p.is_mixed_source_pic), None)
                    
                    self.processed_file_counter += 1 
                    final_cjk_filepath = self._generate_new_filepath(
                        item_to_rename.original_filepath, 
                        "Pic-纯图片",
                        item_to_rename.file_total_size_kb, 0, False, item_to_rename.root_path,
                        self.processed_file_counter 
                    )

                    if item_to_rename.original_filepath.lower() != final_cjk_filepath.lower():
                        try:
                            os.rename(item_to_rename.original_filepath, final_cjk_filepath)
                            if pfi_to_update: pfi_to_update.new_filepath = final_cjk_filepath
                            confirmed_cjk_rename_count +=1
                            overall_stats['纯图片'] +=1
                            overall_stats['纯图片(中文名待确认)'] -=1
                            if self.verbose_output:
                                print(f"  处理(中文纯图): '{os.path.basename(item_to_rename.original_filepath)}' -> '{os.path.basename(final_cjk_filepath)}'")
                        except OSError as e:
                            if self.verbose_output: print(f"  错误: 重命名中文纯图 '{os.path.basename(item_to_rename.original_filepath)}' 失败: {e}")
                            self.processed_file_counter -=1 
                if confirmed_cjk_rename_count > 0:
                    print(f"  已额外重命名 {confirmed_cjk_rename_count} 个中文名纯图片。")
            else:
                print("  已跳过重命名中文名纯图片。这些文件将保留原名。")
                self.processed_file_counter -= overall_stats['纯图片(中文名待确认)']


        print("\n" + PNGFileProcessor.SEP_LINE_MINOR)
        print("--- 阶段 1 摘要 ---")
        print(PNGFileProcessor.SEP_LINE_DOT)
        print(f"  总计扫描到 PNG 文件: {self.total_png_files_scanned_phase1} 个。")
        print(f"  处理的PNG文件总数 (分类并操作的): {self.processed_file_counter}")
        
        if overall_stats['角色卡'] > 0: print(f"    - 角色卡 (已处理): {overall_stats['角色卡']}")
        if overall_stats['SD参数图'] > 0: print(f"    - SD参数图 (已处理并移至 {self.SD_SUBDIR_NAME}/): {overall_stats['SD参数图']}")
        if overall_stats['NAI参数图'] > 0: print(f"    - NAI参数图 (已处理并移至 {self.NAI_SUBDIR_NAME}/): {overall_stats['NAI参数图']}")
        if overall_stats['混合来源图'] > 0: print(f"    - 混合来源图 (已处理): {overall_stats['混合来源图']}")
        if overall_stats['纯图片'] > 0: print(f"    - 纯图片 (已处理): {overall_stats['纯图片']}")
        
        total_skipped = overall_stats['跳过(错误或未知类型)'] + overall_stats['跳过(文件丢失)'] + overall_stats['跳过(重命名/移动失败)']
        if total_skipped > 0: print(f"  因各种原因跳过的文件: {total_skipped}")
        
        if overall_stats['纯图片(中文名待确认)'] > 0 and confirmed_cjk_rename_count < len(cjk_pending_rename_list) :
            print(f"    (其中 {overall_stats['纯图片(中文名待确认)']} 个中文名纯图片未按用户选择重命名，保留原名)")
        print(PNGFileProcessor.SEP_LINE_MINOR)
        
        return [p for p in self.all_processed_file_infos if p.is_character_card and os.path.exists(p.new_filepath)]

    def _phase2_identify_groups_and_compute_data(self, chara_cards_info_list: List[ProcessedFileInfo]) -> Tuple[Dict[str, List[ProcessedFileInfo]], str]:
        report_builder_lines = []
        print("\n" + PNGFileProcessor.SEP_LINE_MAJOR)
        phase2_title = "[阶段 2] 角色卡精确重复检测 (内容与视觉均相似)"
        report_builder_lines.append(phase2_title)
        print(phase2_title)
        print(PNGFileProcessor.SEP_LINE_MAJOR)
        
        grouped_by_initial_name: Dict[str, List[ProcessedFileInfo]] = collections.defaultdict(list)
        for p_info in chara_cards_info_list:
            grouped_by_initial_name[p_info.initial_meta_name_or_type_signal].append(p_info)
        
        processed_groups_filled_data: Dict[str, List[ProcessedFileInfo]] = {}
        exact_duplicates_by_name: Dict[str, List[str]] = collections.defaultdict(list)
        found_any_exact_duplicates = False

        for name_key, group_files_info_list in grouped_by_initial_name.items():
            if not group_files_info_list: continue

            files_in_group_with_data: List[ProcessedFileInfo] = []
            hashes_in_this_group: Dict[str, List[str]] = collections.defaultdict(list)
            metadata_tuples_in_this_group: Dict[Tuple[Optional[str], str, str], List[str]] = collections.defaultdict(list)

            for p_info_item in group_files_info_list:
                if not os.path.exists(p_info_item.new_filepath): continue
                
                p_info_item.file_hash = self.tools.calculate_file_hash(p_info_item.new_filepath)
                p_info_item.detailed_chara_data = self.tools.extract_and_normalize_key_chara_data(p_info_item.chara_json_str)
                p_info_item.chara_json_str = None 
                p_info_item.dhash = self.tools.calculate_dhash(p_info_item.new_filepath)
                
                files_in_group_with_data.append(p_info_item)
                
                if p_info_item.file_hash:
                    hashes_in_this_group[p_info_item.file_hash].append(p_info_item.new_filepath)
                
                if p_info_item.detailed_chara_data:
                    meta_tuple = (p_info_item.detailed_chara_data.norm_name,
                                  p_info_item.detailed_chara_data.norm_first_mes or "",
                                  p_info_item.detailed_chara_data.book_entries_set_str or "")
                    metadata_tuples_in_this_group[meta_tuple].append(p_info_item.new_filepath)
            
            processed_groups_filled_data[name_key] = files_in_group_with_data
            
            consolidated_duplicates_for_this_name_group: Set[str] = set()
            
            for paths_with_same_hash in hashes_in_this_group.values():
                if len(paths_with_same_hash) > 1:
                    potential_exact_refs = [self._get_p_info_by_abs_path(p, processed_groups_filled_data) for p in paths_with_same_hash]
                    potential_exact_refs = [p for p in potential_exact_refs if p and p.detailed_chara_data and p.dhash]
                    
                    if len(potential_exact_refs) > 1:
                        ref_p_info = potential_exact_refs[0]
                        current_exact_set = {ref_p_info.new_filepath}
                        for i in range(1, len(potential_exact_refs)):
                            comp_p_info = potential_exact_refs[i]
                            if self.tools.compare_detailed_chara_data(ref_p_info.detailed_chara_data, comp_p_info.detailed_chara_data) and \
                               self.tools.compare_dhashes(ref_p_info.dhash, comp_p_info.dhash):
                                current_exact_set.add(comp_p_info.new_filepath)
                        if len(current_exact_set) > 1:
                             consolidated_duplicates_for_this_name_group.update(current_exact_set)
            
            for paths_with_same_metadata in metadata_tuples_in_this_group.values():
                if len(paths_with_same_metadata) > 1:
                    potential_exact_refs = [self._get_p_info_by_abs_path(p, processed_groups_filled_data) for p in paths_with_same_metadata]
                    potential_exact_refs = [p for p in potential_exact_refs if p and p.file_hash and p.dhash]

                    if len(potential_exact_refs) > 1:
                        sub_groups = collections.defaultdict(list)
                        for p_info_ref in potential_exact_refs:
                            sub_groups[(p_info_ref.file_hash, p_info_ref.dhash)].append(p_info_ref.new_filepath)
                        
                        for group_key, paths_in_sub_group in sub_groups.items():
                            if len(paths_in_sub_group) > 1:
                                consolidated_duplicates_for_this_name_group.update(paths_in_sub_group)
                                
            if consolidated_duplicates_for_this_name_group:
                 exact_duplicates_by_name[name_key].extend(list(consolidated_duplicates_for_this_name_group))
                 found_any_exact_duplicates = True
                
        print("\n" + PNGFileProcessor.SEP_LINE_MINOR)
        report_builder_lines.append(f"--- {phase2_title.split('] ')[1]} ---") 
        print(report_builder_lines[-1])
        print(PNGFileProcessor.SEP_LINE_DOT)

        if not found_any_exact_duplicates:
            no_duplicates_msg = "  未检测到内容、元数据与视觉均完全相同的精确重复角色卡。"
            report_builder_lines.append(no_duplicates_msg)
            print(no_duplicates_msg)
        else:
            detection_msg = "  检测到以下标识名下存在内容、元数据与视觉均精确重复的文件:"
            report_builder_lines.append(detection_msg)
            print(detection_msg)
            for name_identifier, duplicate_paths_raw_list in sorted(exact_duplicates_by_name.items()):
                unique_abs_paths = list(set(duplicate_paths_raw_list))
                p_info_objects_for_sorting = [
                    self._get_p_info_by_abs_path(fp_abs, processed_groups_filled_data)
                    for fp_abs in unique_abs_paths
                ]
                p_info_objects_for_sorting = [p for p in p_info_objects_for_sorting if p]

                sorted_duplicate_paths_abs = sorted(
                    [p_info.new_filepath for p_info in p_info_objects_for_sorting],
                    key=lambda p_abs: self.tools._extract_sort_keys_from_filename(
                        os.path.basename(p_abs),
                        next((p_obj for p_obj in p_info_objects_for_sorting if p_obj.new_filepath == p_abs), None)
                    )
                )

                if len(sorted_duplicate_paths_abs) > 1:
                    group_header = f"\n  {name_identifier}: (以下为重复项，建议保留第一个)"
                    report_builder_lines.append(group_header)
                    print(group_header)
                    for fp_abs_path in sorted_duplicate_paths_abs:
                        relative_path_display = os.path.relpath(fp_abs_path, self.base_directory)
                        report_line = f"    - {relative_path_display}"
                        report_builder_lines.append(report_line)
                        print(report_line)
        print(PNGFileProcessor.SEP_LINE_MINOR)
        return processed_groups_filled_data, "\n".join(report_builder_lines)

    def _phase3_detailed_comparison_report(self, processed_groups_with_data: Dict[str, List[ProcessedFileInfo]]) -> Tuple[Dict[str, Set[str]], str]:
        report_builder_lines = []
        print("\n" + PNGFileProcessor.SEP_LINE_MAJOR)
        phase3_title = "[阶段 3] 视觉相似性检测 (元数据不同)"
        report_builder_lines.append(phase3_title)
        print(phase3_title)
        print(PNGFileProcessor.SEP_LINE_MAJOR)
        
        potential_similar_items_by_name: Dict[str, Set[str]] = collections.defaultdict(set)
        found_any_potential_similarity_in_phase3 = False

        for name_identifier, group_p_info_list in processed_groups_with_data.items():
            if len(group_p_info_list) < 2: continue

            for i in range(len(group_p_info_list)):
                for j in range(i + 1, len(group_p_info_list)):
                    p_info1, p_info2 = group_p_info_list[i], group_p_info_list[j]
                    
                    if not (p_info1.is_character_card and p_info2.is_character_card and \
                            p_info1.file_hash and p_info2.file_hash and \
                            p_info1.detailed_chara_data and p_info2.detailed_chara_data and \
                            p_info1.dhash and p_info2.dhash):
                        continue
                    
                    if p_info1.file_hash == p_info2.file_hash or \
                       self.tools.compare_detailed_chara_data(p_info1.detailed_chara_data, p_info2.detailed_chara_data):
                        continue 
                    
                    if self.tools.compare_dhashes(p_info1.dhash, p_info2.dhash):
                        potential_similar_items_by_name[name_identifier].add(p_info1.new_filepath)
                        potential_similar_items_by_name[name_identifier].add(p_info2.new_filepath)
                        found_any_potential_similarity_in_phase3 = True
        
        print("\n" + PNGFileProcessor.SEP_LINE_MINOR)
        report_builder_lines.append(f"--- {phase3_title.split('] ')[1]} ---")
        print(report_builder_lines[-1])
        print(PNGFileProcessor.SEP_LINE_DOT)

        if not found_any_potential_similarity_in_phase3:
            no_sim_msg = "  未检测到视觉相似 (但元数据不同) 的角色卡。"
            report_builder_lines.append(no_sim_msg)
            print(no_sim_msg)
        else:
            sim_found_msg = "  检测到以下标识名下可能存在视觉相似但元数据不同的文件:"
            report_builder_lines.append(sim_found_msg)
            print(sim_found_msg)
            for name_id, filepaths_abs_set in sorted(potential_similar_items_by_name.items()):
                if len(filepaths_abs_set) > 1 :
                    p_info_objects_for_sorting = [
                        self._get_p_info_by_abs_path(fp_abs, processed_groups_with_data)
                        for fp_abs in list(filepaths_abs_set)
                    ]
                    p_info_objects_for_sorting = [p for p in p_info_objects_for_sorting if p]

                    sorted_filepaths_abs = sorted(
                        [p_info.new_filepath for p_info in p_info_objects_for_sorting],
                         key=lambda p_abs: self.tools._extract_sort_keys_from_filename(
                            os.path.basename(p_abs),
                            next((p_obj for p_obj in p_info_objects_for_sorting if p_obj.new_filepath == p_abs), None)
                        )
                    )
                    group_header = f"\n  {name_id}: (以下文件视觉相似，但元数据不同)"
                    report_builder_lines.append(group_header)
                    print(group_header)
                    for fp_abs_path in sorted_filepaths_abs:
                        relative_path_display = os.path.relpath(fp_abs_path, self.base_directory)
                        report_line = f"    - {relative_path_display}"
                        report_builder_lines.append(report_line)
                        print(report_line)
        print(PNGFileProcessor.SEP_LINE_MINOR)
        return potential_similar_items_by_name, "\n".join(report_builder_lines)

    def _phase4_generate_fine_grained_report(
        self,
        all_processed_data_groups: Dict[str, List[ProcessedFileInfo]]
    ):
        print("\n" + PNGFileProcessor.SEP_LINE_MAJOR)
        print("[阶段 4 / 可选] 精细化相似性分类报告 (Type A/B/C)")
        print(PNGFileProcessor.SEP_LINE_MAJOR)

        all_character_p_infos: List[ProcessedFileInfo] = []
        for group_list in all_processed_data_groups.values():
            all_character_p_infos.extend([p for p in group_list if p.is_character_card and p.detailed_chara_data and p.dhash and p.file_hash])
        
        if len(all_character_p_infos) < 2:
            print("  角色卡数量不足 (<2) 或数据不完整，无法进行阶段 4 成对比较。此阶段跳过。")
            print(PNGFileProcessor.SEP_LINE_MINOR)
            return

        report_type_a: Dict[str, List[Tuple[ProcessedFileInfo, ProcessedFileInfo]]] = collections.defaultdict(list)
        report_type_b: Dict[str, List[Tuple[ProcessedFileInfo, ProcessedFileInfo]]] = collections.defaultdict(list)
        report_type_c: Dict[str, List[Tuple[ProcessedFileInfo, ProcessedFileInfo]]] = collections.defaultdict(list)
        
        processed_pairs_for_phase4: Set[Tuple[str, str]] = set()

        for i in range(len(all_character_p_infos)):
            for j in range(i + 1, len(all_character_p_infos)):
                p_info1, p_info2 = all_character_p_infos[i], all_character_p_infos[j]

                if p_info1.file_hash == p_info2.file_hash:
                    continue

                pair_key_abs_sorted = tuple(sorted((p_info1.new_filepath, p_info2.new_filepath)))
                if pair_key_abs_sorted in processed_pairs_for_phase4: continue
                processed_pairs_for_phase4.add(pair_key_abs_sorted)

                meta_similar = self.tools.compare_detailed_chara_data(p_info1.detailed_chara_data, p_info2.detailed_chara_data)
                visual_similar = self.tools.compare_dhashes(p_info1.dhash, p_info2.dhash)
                
                sort_key1 = self.tools._extract_sort_keys_from_filename(os.path.basename(p_info1.new_filepath), p_info1)
                sort_key2 = self.tools._extract_sort_keys_from_filename(os.path.basename(p_info2.new_filepath), p_info2)
                ordered_pair_objects = (p_info1, p_info2) if sort_key1 <= sort_key2 else (p_info2, p_info1)
                
                grouping_name = ordered_pair_objects[0].initial_meta_name_or_type_signal 

                if meta_similar and visual_similar:
                    report_type_a[grouping_name].append(ordered_pair_objects)
                elif meta_similar and not visual_similar:
                    report_type_b[grouping_name].append(ordered_pair_objects)
                elif not meta_similar and visual_similar:
                    report_type_c[grouping_name].append(ordered_pair_objects)

        if not any([report_type_a, report_type_b, report_type_c]):
            print("  未找到符合阶段 4 Type A/B/C 分类标准的相似对。")
        else:
            def output_sorted_pairs_type(
                report_dict: Dict[str, List[Tuple[ProcessedFileInfo, ProcessedFileInfo]]],
                type_name_str: str, type_description: str
            ):
                if not report_dict:
                    return
                
                print("\n" + PNGFileProcessor.SEP_LINE_MINOR)
                print(f"--- 类型 {type_name_str}: {type_description} ---")
                print(PNGFileProcessor.SEP_LINE_DOT)
                
                found_in_type = False
                for name_id, pairs_list_obj in sorted(report_dict.items()): 
                    if not pairs_list_obj: continue
                    found_in_type = True
                    sorted_pairs_list_obj = sorted(
                        pairs_list_obj,
                        key=lambda p_tuple: self.tools._extract_sort_keys_from_filename(
                            os.path.basename(p_tuple[0].new_filepath), p_tuple[0]
                        )
                    )
                    print(f"  {name_id}:") 
                    for p_obj1, p_obj2 in sorted_pairs_list_obj:
                        p1_rel = os.path.relpath(p_obj1.new_filepath, self.base_directory)
                        p2_rel = os.path.relpath(p_obj2.new_filepath, self.base_directory)
                        print(f"    - {p1_rel}")
                        print(f"    - {p2_rel}")
                        print("      " + "-"*20)
                if not found_in_type:
                     print("    此类型下未找到符合项。")

            output_sorted_pairs_type(report_type_a, "A", "元数据与视觉均相似")
            output_sorted_pairs_type(report_type_b, "B", "仅元数据相似, 视觉不同")
            output_sorted_pairs_type(report_type_c, "C", "仅视觉相似, 元数据不同")
            
        print("\n" + PNGFileProcessor.SEP_LINE_MAJOR)
        print("--- 阶段 4 精细化报告结束 ---")
        print(PNGFileProcessor.SEP_LINE_MAJOR)

    def run(self):
        method_overall_start_time = time.perf_counter()
        self.total_input_wait_time = 0.0

        print("\n" + PNGFileProcessor.SEP_LINE_MAJOR)
        print(f"--- 开始处理目录: {self.base_directory} ---")
        print(PNGFileProcessor.SEP_LINE_MAJOR)

        if not PNGFileProcessor._check_termux_storage_permission(self.base_directory):
            sys.exit("错误: 存储权限不足，无法继续。")
        self._sillytavern_warning_check(self.base_directory) 

        chara_p1_results = self._phase1_scan_and_rename() 
        
        if self.total_png_files_scanned_phase1 == 0 :
            print("\n" + PNGFileProcessor.SEP_LINE_FINAL)
            print("操作结束：未扫描到任何 PNG 文件。")
            print(PNGFileProcessor.SEP_LINE_FINAL)
            self._print_timing_info(method_overall_start_time)
            return

        if not self.all_processed_file_infos and self.processed_file_counter == 0 and self.total_png_files_scanned_phase1 > 0:
            print("\n" + PNGFileProcessor.SEP_LINE_FINAL)
            print(f"操作结束：扫描到 {self.total_png_files_scanned_phase1} 个PNG文件，但无文件被处理或分类。")
            print(PNGFileProcessor.SEP_LINE_FINAL)
            self._print_timing_info(method_overall_start_time)
            return
        
        chara_for_analysis = [pfi for pfi in self.all_processed_file_infos if pfi.is_character_card and os.path.exists(pfi.new_filepath)]
        if not chara_for_analysis:
            print("\n" + PNGFileProcessor.SEP_LINE_FINAL)
            print("操作部分完成：阶段 1 执行完毕，但无有效角色卡可供后续分析。")
            print(PNGFileProcessor.SEP_LINE_FINAL)
            self._print_timing_info(method_overall_start_time)
            return

        data_p2_results, report_p2_text = self._phase2_identify_groups_and_compute_data(chara_for_analysis)
        similars_p3_map, report_p3_text = self._phase3_detailed_comparison_report(data_p2_results)

        clipboard_content_parts = []
        if "未检测到内容、元数据与视觉均完全相同的精确重复角色卡。" not in report_p2_text and \
           any(line.strip().startswith("-") or (line.strip().startswith("  ") and ":" in line) for line in report_p2_text.splitlines()):
            clipboard_content_parts.append(report_p2_text)
        
        if "未检测到视觉相似 (但元数据不同) 的角色卡。" not in report_p3_text and \
            any(line.strip().startswith("-") or (line.strip().startswith("  ") and ":" in line) for line in report_p3_text.splitlines()):
             clipboard_content_parts.append(report_p3_text)

        final_clipboard_output_text = "\n\n".join(clipboard_content_parts).strip()
        
        print("\n" + PNGFileProcessor.SEP_LINE_CLIP)
        print("剪贴板提示:")
        if final_clipboard_output_text:
            self.tools._set_clipboard_text_termux(final_clipboard_output_text)
            print("  阶段 2 和 3 的相关报告摘要已尝试复制到剪贴板。")
        else:
            print("  阶段 2 和 3 未发现需报告的精确重复或视觉相似项，剪贴板无内容。")
        print(PNGFileProcessor.SEP_LINE_CLIP)

        print(f"\n--- 主要阶段 (1, 2, 3) 处理完成 ---")
        
        can_run_phase4 = len(chara_for_analysis) >=2

        if can_run_phase4:
            phase4_prompt = ("\n是否生成阶段 4 的精细化相似性分类报告 (Type A/B/C)?\n (y/n, 默认 n): ")
            if self._timed_input(phase4_prompt).strip().lower() == 'y':
                self._phase4_generate_fine_grained_report(data_p2_results)
            else:
                print("  已跳过阶段 4 精细化报告。")
        else:
            print("  角色卡数量不足或数据不完整，已自动跳过阶段 4。")
        
        print("\n" + PNGFileProcessor.SEP_LINE_FINAL)
        print("所有批量处理操作已执行完毕！")
        print(f"  总共扫描PNG文件 (阶段1): {self.total_png_files_scanned_phase1}")
        print(f"  总共处理的PNG文件 (分类并操作的): {self.processed_file_counter}")
        self._print_timing_info(method_overall_start_time)
        print(PNGFileProcessor.SEP_LINE_FINAL)

    def _print_timing_info(self, method_overall_start_time: float):
        total_method_duration = time.perf_counter() - method_overall_start_time
        pure_processing_time = total_method_duration - self.total_input_wait_time
        print(f"  脚本核心处理耗时: {pure_processing_time:.2f} 秒")
        print(f"  脚本总运行时间  {total_method_duration:.2f} 秒")

def main_processor():
    print(PNGFileProcessor.SEP_LINE_MAJOR)
    print("PNG 文件批量处理与分析工具 (Termux)")
    print(PNGFileProcessor.SEP_LINE_DOT)
    
    sd_subdir_name_display = PNGFileProcessor.SD_SUBDIR_NAME
    nai_subdir_name_display = PNGFileProcessor.NAI_SUBDIR_NAME
    default_target_dir_display = "~/storage/shared/Download"

    print(f"  默认处理目录: '{default_target_dir_display}'")
    print(f"  SD参数图将移至其下的 '{sd_subdir_name_display}/' 子目录")
    print(f"  NAI参数图将移至其下的 '{nai_subdir_name_display}/' 子目录")
    print(f"  角色卡、纯图片、混合来源图将原地重命名。")
    print(PNGFileProcessor.SEP_LINE_MINOR)

    if not os.environ.get("TERMUX_VERSION"):
        print("提示: 本脚本为Termux优化。非Termux环境剪贴板等功能可能受限。")
        print(PNGFileProcessor.SEP_LINE_MINOR)
    
    target_dir_default = os.path.expanduser(default_target_dir_display)
    
    verbose_prompt = ("\n是否输出详细的阶段1文件操作日志 ? (y/n, 默认 n): ")
    verbose_flag_input = input(verbose_prompt).strip().lower() == 'y'
    
    processor_instance = PNGFileProcessor(target_dir_default, verbose_flag_input)
    processor_instance.run()

if __name__ == "__main__":
    main_processor()
