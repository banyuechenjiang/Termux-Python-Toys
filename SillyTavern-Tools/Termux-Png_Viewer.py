import base64
import zlib
import png
import json
import os
import sys
import re
from typing import Tuple, Optional, List, Dict, Any

BASE_DOWNLOAD_DIR = os.path.expanduser("~/storage/shared/Download")
SD_PARAMS_DIR = os.path.join(BASE_DOWNLOAD_DIR, "SD")
NAI_PARAMS_DIR = os.path.join(BASE_DOWNLOAD_DIR, "NAI")

SEP_LINE_MAJOR = "=" * 60
SEP_LINE_MINOR = "-" * 50
SEP_LINE_DOT = "." * 50
SEP_LINE_WARN = "!" * 50

FILES_PER_PAGE = 30
FILE_TYPE_NAME_CHARA = "角色卡"

CHARA_FILE_EXCLUSION_PREFIXES = (
    "Pic-SD-", 
    "Pic-NAI-", 
    "Pic-纯图片-", 
    "Pic-Mixed-"
)

MAX_STR_VAL_LEN = 80 
STR_PREVIEW_HEAD = 35
STR_PREVIEW_TAIL = 35 
LIST_ITEM_PREVIEW_COUNT = 3

CRITICAL_CONTEXT_KEYWORDS = ['parameters', 'comment', 'software', 'source', 'title', 'description']


def _ensure_dir_exists(directory: str, create_if_missing: bool = False) -> bool:
    if os.path.isdir(directory):
        return True
    if create_if_missing:
        try:
            os.makedirs(directory, exist_ok=True)
            return True
        except OSError:
            return False
    else:
        return False

def _is_potential_character_card_by_name(filename: str) -> bool:
    for prefix in CHARA_FILE_EXCLUSION_PREFIXES:
        if filename.startswith(prefix):
            return False
    return True

def _has_chara_metadata(filepath: str) -> bool:
    try:
        with open(filepath, 'rb') as f:
            reader = png.Reader(file=f)
            for chunk_type_bytes, chunk_data_bytes in reader.chunks():
                if chunk_type_bytes == b'tEXt':
                    try:
                        key_bytes, _ = chunk_data_bytes.split(b'\x00', 1)
                        if key_bytes.decode('utf-8', errors='ignore').lower() == 'chara':
                            return True
                    except (ValueError, UnicodeDecodeError):
                        continue 
    except (FileNotFoundError, png.FormatError, png.ChunkError):
        return False
    return False

def _clean_and_truncate_str_for_chara_value(text: str) -> str:
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]+', ' ', text).replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ').strip()
    if len(cleaned) > MAX_STR_VAL_LEN:
        return f"{cleaned[:STR_PREVIEW_HEAD]}...{cleaned[-STR_PREVIEW_TAIL:]}"
    return cleaned

def _format_chara_dict_value_for_display(data_obj: Any, indent_level: int) -> str:
    current_indent_str = "  " * indent_level
    next_indent_str = "  " * (indent_level + 1)
    output_parts: List[str] = []

    if isinstance(data_obj, dict):
        if not data_obj: return "{}"
        output_parts.append("{\n")
        items = list(data_obj.items())
        for i, (key, value) in enumerate(items):
            key_str = f'"{str(key)}": '
            value_str = _format_chara_dict_value_for_display(value, indent_level + 1)
            output_parts.append(f"{next_indent_str}{key_str}{value_str}")
            if i < len(items) - 1:
                output_parts.append(",")
            output_parts.append("\n")
        output_parts.append(current_indent_str + "}")
        return "".join(output_parts)

    elif isinstance(data_obj, list):
        if not data_obj: return "[]"
        output_parts.append("[\n")
        if len(data_obj) > (2 * LIST_ITEM_PREVIEW_COUNT) and len(data_obj) > 5 : # Show preview if significantly long
            for i in range(LIST_ITEM_PREVIEW_COUNT):
                output_parts.append(next_indent_str + _format_chara_dict_value_for_display(data_obj[i], indent_level + 1))
                output_parts.append(",\n")
            output_parts.append(f"{next_indent_str}  ... ({len(data_obj) - 2 * LIST_ITEM_PREVIEW_COUNT} more items) ...,\n")
            for i in range(len(data_obj) - LIST_ITEM_PREVIEW_COUNT, len(data_obj)):
                output_parts.append(next_indent_str + _format_chara_dict_value_for_display(data_obj[i], indent_level + 1))
                if i < len(data_obj) - 1:
                    output_parts.append(",")
                output_parts.append("\n")
        else:
            for i, item in enumerate(data_obj):
                output_parts.append(next_indent_str + _format_chara_dict_value_for_display(item, indent_level + 1))
                if i < len(data_obj) - 1:
                    output_parts.append(",")
                output_parts.append("\n")
        output_parts.append(current_indent_str + "]")
        return "".join(output_parts)
            
    elif isinstance(data_obj, str):
        return f'"{_clean_and_truncate_str_for_chara_value(data_obj)}"'
    elif isinstance(data_obj, bool):
        return str(data_obj).lower()
    elif data_obj is None:
        return "null"
    else: 
        return str(data_obj)

def _decode_text_chunk_data(keyword_bytes: bytes, data_bytes: bytes) -> Tuple[Any, str]:
    keyword_str_display = keyword_bytes.decode('utf-8', errors='replace')
    keyword_str_lower = keyword_str_display.lower()
    
    content_result: Any
    type_desc: str

    FAIL_ZLIB_DECOMPRESS = "Zlib解压失败"
    FAIL_BASE64_DECODE = "Base64解码失败"
    FAIL_UTF8_DECODE_AFTER_BASE64 = "Base64成功,但UTF-8解码失败"
    FAIL_JSON_PARSE = "JSON解析失败"
    FAIL_UTF8_DECODE_GENERAL = "UTF-8解码失败"

    if keyword_str_lower == 'chara':
        type_desc_base = "角色卡数据"
        processed_data = data_bytes
        try:
            decompressed_data = zlib.decompress(processed_data)
            processed_data = decompressed_data
        except zlib.error:
            pass
        
        try:
            base64_decoded_bytes = base64.b64decode(processed_data)
            try:
                utf8_decoded_str = base64_decoded_bytes.decode('utf-8')
                try:
                    parsed_json_dict = json.loads(utf8_decoded_str)
                    content_result = parsed_json_dict
                    type_desc = "角色卡数据 (已解析为Python字典)"
                    return content_result, type_desc
                except json.JSONDecodeError:
                    content_result = f"{FAIL_JSON_PARSE}. 原始UTF-8文本 (部分):\n{utf8_decoded_str[:1000]}"
                    type_desc = f"{type_desc_base} ({FAIL_JSON_PARSE})"
            except UnicodeDecodeError:
                content_result = FAIL_UTF8_DECODE_AFTER_BASE64
                type_desc = f"{type_desc_base} ({FAIL_UTF8_DECODE_AFTER_BASE64})"
        except base64.binascii.Error: 
            content_result = FAIL_BASE64_DECODE
            try: temp_str_attempt = data_bytes.decode('utf-8', errors='replace')
            except: temp_str_attempt = ""
            if temp_str_attempt: content_result += f"\n原始数据文本尝试 (部分):\n{temp_str_attempt[:1000]}"
            type_desc = f"{type_desc_base} ({FAIL_BASE64_DECODE})"
        return content_result, type_desc

    elif keyword_str_lower == 'comment':
        type_desc = "评论/参数"
        try:
            text_content = data_bytes.decode('utf-8')
            try:
                json_parsed_content = json.loads(text_content)
                content_result = json.dumps(json_parsed_content, indent=2, ensure_ascii=False)
                type_desc += " (JSON格式化)"
            except json.JSONDecodeError:
                content_result = text_content 
                type_desc += " (UTF-8纯文本)"
        except UnicodeDecodeError:
            content_result = FAIL_UTF8_DECODE_GENERAL
            type_desc += f" ({FAIL_UTF8_DECODE_GENERAL})"
        return content_result, type_desc

    elif keyword_str_lower == 'parameters':
        type_desc = "SD参数"
        try:
            content_result = data_bytes.decode('utf-8')
            type_desc += " (UTF-8纯文本)"
        except UnicodeDecodeError:
            content_result = FAIL_UTF8_DECODE_GENERAL
            type_desc += f" ({FAIL_UTF8_DECODE_GENERAL})"
        return content_result, type_desc
        
    elif keyword_str_lower in CRITICAL_CONTEXT_KEYWORDS:
        type_desc = f"{keyword_str_display} (UTF-8纯文本)"
        try:
            content_result = data_bytes.decode('utf-8')
        except UnicodeDecodeError:
            content_result = FAIL_UTF8_DECODE_GENERAL
            type_desc = f"{keyword_str_display} ({FAIL_UTF8_DECODE_GENERAL})"
        return content_result, type_desc
    else: 
        type_desc = f"通用块 ('{keyword_str_display}')"
        try:
            content_result = data_bytes.decode('utf-8', errors='strict')
            type_desc += " (UTF-8文本)"
        except UnicodeDecodeError:
            try:
                content_result = data_bytes.decode('latin-1', errors='strict')
                type_desc += " (Latin-1文本)"
            except UnicodeDecodeError:
                content_result = data_bytes 
                type_desc += " (原始字节)"
        return content_result, type_desc

def view_png_text_chunks(filepath: str):
    print(SEP_LINE_MINOR)
    print(f"分析文件: {os.path.basename(filepath)}")
    print(f"完整路径: {filepath}")
    print(SEP_LINE_MINOR)

    if not os.path.isfile(filepath):
        print(f"{SEP_LINE_WARN}\n错误: 文件未找到或无效。\n路径: {filepath}\n{SEP_LINE_WARN}")
        return

    chara_block_successfully_parsed_as_dict = False
    try:
        with open(filepath, 'rb') as f:
            try:
                reader = png.Reader(file=f)
                chunks_data = list(reader.chunks())
            except png.ChunkError as e:
                print(f"{SEP_LINE_WARN}\n错误: 读取PNG数据块出错。\n详情: {e}\n{SEP_LINE_WARN}")
                return
            except png.FormatError as e:
                 print(f"{SEP_LINE_WARN}\n错误: 文件非PNG格式或已损坏。\n详情: {e}\n{SEP_LINE_WARN}")
                 return

            text_chunks_found = 0
            for i, (chunk_type_bytes, chunk_data_bytes) in enumerate(chunks_data):
                if chunk_type_bytes == b'tEXt':
                    text_chunks_found += 1
                    print(f"\n--- tEXt 数据块 #{text_chunks_found} ---")
                    try:
                        keyword_bytes, data_bytes_for_decode = chunk_data_bytes.split(b'\x00', 1)
                        
                        content_obj, type_desc = _decode_text_chunk_data(keyword_bytes, data_bytes_for_decode)
                        keyword_display = keyword_bytes.decode('utf-8', errors='replace')
                        
                        print(f"关键词: {keyword_display}")
                        print(f"类型/状态: {type_desc}")
                        print("内容:")

                        display_string_for_content: str
                        if isinstance(content_obj, dict) and keyword_display.lower() == 'chara':
                            display_string_for_content = _format_chara_dict_value_for_display(content_obj, 0)
                            chara_block_successfully_parsed_as_dict = True
                        else:
                            if chara_block_successfully_parsed_as_dict and \
                               keyword_display.lower() != 'chara' and \
                               keyword_display.lower() not in CRITICAL_CONTEXT_KEYWORDS:
                                display_string_for_content = "  (此数据块内容未作详细显示)"
                            else:
                                if isinstance(content_obj, str):
                                    lines = content_obj.splitlines()
                                    formatted_lines = [f"  {line}" for line in lines]
                                    
                                    temp_display_str = "\n".join(formatted_lines)
                                    if len(temp_display_str) > 3000 and keyword_display.lower() != 'chara':
                                        display_string_for_content = temp_display_str[:1500] + \
                                                                     "\n  ... (内容过长，已截断) ...\n" + \
                                                                     temp_display_str[-1500:]
                                    else:
                                        display_string_for_content = temp_display_str
                                elif isinstance(content_obj, bytes):
                                    hex_representation = content_obj.hex()
                                    if len(hex_representation) > 200:
                                        display_string_for_content = f"  (原始字节数据): {hex_representation[:100]}...{hex_representation[-100:]}"
                                    else:
                                        display_string_for_content = f"  (原始字节数据): {hex_representation}"
                                else: 
                                    display_string_for_content = f"  {str(content_obj)}"
                        print(display_string_for_content)
                    except ValueError:
                        print(f"{SEP_LINE_WARN}\n错误: tEXt块格式无效。\n原始数据: {chunk_data_bytes[:64]}\n{SEP_LINE_WARN}")
            
            if text_chunks_found == 0:
                print("未在此文件中找到 tEXt 数据块。")
    except FileNotFoundError:
        print(f"{SEP_LINE_WARN}\n错误: 文件 '{os.path.basename(filepath)}' 未找到。\n{SEP_LINE_WARN}")
    except Exception as e:
        print(f"{SEP_LINE_WARN}\n读取或处理PNG时发生未知错误: {e}\n{SEP_LINE_WARN}")
    finally:
        print(SEP_LINE_MINOR)

def _select_file_from_dir(directory: str, file_type_name: str, recursive: bool = False) -> Optional[str]:
    if not _ensure_dir_exists(directory):
        return None

    all_png_abs_paths: List[str] = []
    
    if recursive:
        for root, dirs, files_in_root in os.walk(directory, topdown=True):
            if file_type_name == FILE_TYPE_NAME_CHARA and directory == BASE_DOWNLOAD_DIR:
                dirs[:] = [d for d in dirs if os.path.normpath(os.path.join(root, d)) != os.path.normpath(SD_PARAMS_DIR) and \
                                            os.path.normpath(os.path.join(root, d)) != os.path.normpath(NAI_PARAMS_DIR)]
            for filename in files_in_root:
                if not filename.lower().endswith(".png"): continue
                full_path = os.path.join(root, filename)
                if not os.path.isfile(full_path): continue
                if file_type_name == FILE_TYPE_NAME_CHARA:
                    if not _is_potential_character_card_by_name(filename):
                        continue
                    if not _has_chara_metadata(full_path):
                        continue
                all_png_abs_paths.append(full_path)
    else:
        try:
            files_in_root = os.listdir(directory)
            for filename in files_in_root:
                if filename.lower().endswith(".png"):
                    full_path = os.path.join(directory, filename)
                    if os.path.isfile(full_path):
                         all_png_abs_paths.append(full_path)
        except OSError:
            return None

    all_png_abs_paths.sort(key=lambda x: os.path.basename(x).lower())

    if not all_png_abs_paths:
        return None

    total_files = len(all_png_abs_paths)
    total_pages = (total_files + FILES_PER_PAGE - 1) // FILES_PER_PAGE
    if total_pages == 0: total_pages = 1
    current_page = 1

    while True:
        print(f"\n--- {file_type_name} PNG 文件列表 (第 {current_page}/{total_pages} 页, 共 {total_files} 文件) ---")
        start_index = (current_page - 1) * FILES_PER_PAGE
        end_index = min(start_index + FILES_PER_PAGE, total_files)
        current_page_options: Dict[int, str] = {}
        
        for i, abs_path_idx in enumerate(range(start_index, end_index)):
            abs_path = all_png_abs_paths[abs_path_idx]
            display_number = i + 1
            display_filename = os.path.basename(abs_path)
            print(f"  {display_number:2d}. {display_filename}")
            current_page_options[display_number] = abs_path
        
        print(SEP_LINE_DOT)
        prompt = "请选择文件编号"
        nav_options: List[str] = []
        if total_pages > 1:
            if current_page > 1: nav_options.append("'p'上一页")
            if current_page < total_pages: nav_options.append("'n'下一页")
            nav_options.append("'g<页码>'跳转")
        nav_options.append("'0'返回菜单")
        prompt += f" ({', '.join(nav_options)}): "
        user_input = input(prompt).strip().lower()

        if user_input == '0': return None
        elif user_input == 'n' and current_page < total_pages: current_page += 1
        elif user_input == 'p' and current_page > 1: current_page -= 1
        elif user_input.startswith('g') and total_pages > 1:
            try:
                page_to_go_str = user_input[1:].strip()
                if not page_to_go_str: continue
                page_to_go = int(page_to_go_str)
                if 1 <= page_to_go <= total_pages: current_page = page_to_go
            except ValueError: pass
        else:
            try:
                choice_num = int(user_input)
                if choice_num in current_page_options: return current_page_options[choice_num]
            except ValueError: pass

def main_viewer():
    _ensure_dir_exists(SD_PARAMS_DIR, create_if_missing=True)
    _ensure_dir_exists(NAI_PARAMS_DIR, create_if_missing=True)
    
    while True:
        print("\n" + SEP_LINE_MAJOR)
        print("PNG 元数据查看器 (Termux)")
        print(SEP_LINE_DOT)
        print(f"  1. 查看{FILE_TYPE_NAME_CHARA} (扫描Download, 有过滤)")
        sd_rel_path = os.path.relpath(SD_PARAMS_DIR, BASE_DOWNLOAD_DIR) if SD_PARAMS_DIR.startswith(BASE_DOWNLOAD_DIR) else SD_PARAMS_DIR
        nai_rel_path = os.path.relpath(NAI_PARAMS_DIR, BASE_DOWNLOAD_DIR) if NAI_PARAMS_DIR.startswith(BASE_DOWNLOAD_DIR) else NAI_PARAMS_DIR
        print(f"  2. 查看SD参数图 (来自 Download/{sd_rel_path} 目录)")
        print(f"  3. 查看NAI参数图 (来自 Download/{nai_rel_path} 目录)")
        print("  4. 手动输入PNG文件路径")
        print("  0. 退出")
        print(SEP_LINE_DOT)
        choice = input("请输入选项 (0-4): ").strip()
        selected_filepath: Optional[str] = None

        if choice == '1':
            selected_filepath = _select_file_from_dir(BASE_DOWNLOAD_DIR, FILE_TYPE_NAME_CHARA, recursive=True)
        elif choice == '2':
            selected_filepath = _select_file_from_dir(SD_PARAMS_DIR, "SD参数图", recursive=False)
        elif choice == '3':
            selected_filepath = _select_file_from_dir(NAI_PARAMS_DIR, "NAI参数图", recursive=False)
        elif choice == '4':
            manual_path_input = input("请输入PNG文件的完整路径: ").strip().strip('\'"')
            expanded_path = os.path.expanduser(manual_path_input)
            if os.path.isfile(expanded_path) and expanded_path.lower().endswith(".png"):
                selected_filepath = expanded_path
        elif choice == '0': break
        
        if selected_filepath:
            view_png_text_chunks(selected_filepath)
            input("\n按回车键返回主菜单...")

if __name__ == "__main__":
    main_viewer()
