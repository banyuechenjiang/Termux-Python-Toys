# 版本号: v_NewDesign_Wikitext_Unified{Part-2-角色_获取并深度处理Wikitext_refined_clean.py}
import requests
from bs4 import BeautifulSoup
import json
import logging
from fake_useragent import UserAgent
import requests_cache # 用于一级缓存
from time import sleep
import os
import sqlite3 # 用于二级缓存
from datetime import datetime # timedelta 用于一级缓存的过期策略（虽然此处会主动删除）
import re
import html

# --- 核心配置与常量 ---
LOG_FILE_NAME = "character_processor_refined.log" # 日志文件名
OUTPUT_JSON_FILE = "character_details_final_refined.json" # 最终输出文件名
INPUT_JSON_FILE = "character_data.json" # 输入文件名 (来自Part-1)

BASE_URL = "https://wiki.biligame.com" # B站Wiki基础URL

# 一级缓存: 存储原始编辑页Response对象 (每次运行前会清空)
RAW_EDIT_PAGES_CACHE_NAME = "raw_character_edit_cache" # 一级缓存名称
FIRST_LEVEL_CACHE_FILE = f"{RAW_EDIT_PAGES_CACHE_NAME}.sqlite" # 一级缓存文件名

# 二级持久化: 存储处理后的、已清理的纯Wikitext字符串 (不清空)
PROCESSED_WIKITEXT_DB_NAME = "processed_character_wikitext_store" # 二级缓存数据库名
SECOND_LEVEL_CACHE_FILE = f"{PROCESSED_WIKITEXT_DB_NAME}.sqlite" # 二级缓存文件名
WIKITEXT_TABLE_NAME = "wikitext_data" # 二级缓存中的表名

# Wikitext模板名常量
TPL_CHAR_ATTR_DATA = "角色/属性数据"
TPL_CHAR_CONSTELLATION = "角色/命之座"
TPL_TALENT_SKILL = "天赋技能"
TPL_CHAR_SKILL_BLOCK_START = "角色技能|开始"
TPL_CHAR_SKILL_BLOCK_END = "角色技能|结束"
TPL_CHAR_SKILL_HEADER_PATTERN = r"角色技能/([1-4])"


# --- 日志模块 ---
def setup_logger(log_file_path):
    """配置日志记录器"""
    if os.path.exists(log_file_path):
        try: os.remove(log_file_path)
        except OSError as e: print(f"删除旧日志文件 {log_file_path} 时出错: {e}")

    logger_instance = logging.getLogger(__name__)
    logger_instance.handlers = []
    logger_instance.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s")

    file_h = logging.FileHandler(log_file_path, encoding="utf-8")
    file_h.setFormatter(formatter)
    logger_instance.addHandler(file_h)

    stream_h = logging.StreamHandler()
    stream_h.setFormatter(formatter)
    logger_instance.addHandler(stream_h)
    return logger_instance

logger = setup_logger(LOG_FILE_NAME)


# --- HTML与Wikitext通用处理模块 ---
def _remove_html_comments(text_content):
    """移除文本中的HTML注释 (<!-- ... -->)"""
    if text_content is None: return ""
    return re.sub(r'<!--.*?-->', '', text_content, flags=re.DOTALL)

def _find_template_block_indices(wikitext, template_name_pattern, char_name_for_log=""):
    """查找Wikitext中指定模板的起始和结束索引。返回 (start_idx, content_start_idx, content_end_idx, template_block_end_idx, match_obj)"""
    if not wikitext or not template_name_pattern: return None
    
    if isinstance(template_name_pattern, str) and not any(c in template_name_pattern for c in r".*+?^$()[]{}|\\"):
        start_tag_regex_str = r"\{\{\s*" + re.escape(template_name_pattern) + r"\s*(?=\||\}\})"
    else:
        start_tag_regex_str = r"\{\{\s*" + template_name_pattern + r"\s*(?=\||\}\})"

    match = re.search(start_tag_regex_str, wikitext, re.IGNORECASE | re.DOTALL)
    if not match: return None

    template_start_index = match.start()
    content_start_index = match.end()
    
    level = 1
    current_pos = content_start_index
    template_end_index = -1

    while current_pos < len(wikitext) - 1:
        if wikitext[current_pos:current_pos+2] == '{{':
            level += 1; current_pos += 1
        elif wikitext[current_pos:current_pos+2] == '}}':
            level -= 1
            if level == 0:
                template_end_index = current_pos + 2
                break
            current_pos += 1
        current_pos += 1
        
    if template_end_index == -1:
        logger.debug(f"[{char_name_for_log}] 模板 '{template_name_pattern}' (始于索引 {template_start_index}) 未找到匹配的 '}}'。")
        return None
    
    return template_start_index, content_start_index, template_end_index - 2, template_end_index, match

def _parse_params_from_str(params_str, char_name_for_log=""):
    params = {}
    if not params_str: return params
    
    param_matches = re.finditer(r"\|\s*([^=]+?)\s*=\s*(.*?)(?=\s*\|\s*[^=]+?=|\Z)", params_str, re.DOTALL | re.UNICODE)
    for p_match in param_matches:
        key = p_match.group(1).strip()
        value = p_match.group(2).strip()
        params[key] = value
    
    if not params and params_str.strip() and not params_str.strip().startswith("|") and "=" not in params_str:
        params["1"] = params_str.strip()
    elif not params and params_str.strip().startswith("|"):
        parts = params_str.split('|')[1:]
        for i, part_val in enumerate(parts):
            if "=" not in part_val:
                params[str(i+1)] = part_val.strip()
    return params

def get_template_params(wikitext, template_name, char_name_for_log=""):
    indices = _find_template_block_indices(wikitext, template_name, char_name_for_log)
    if not indices: return None
    _t_start, c_start, c_end, _t_end, _match = indices
    return _parse_params_from_str(wikitext[c_start:c_end].strip(), char_name_for_log)

def remove_template_block(wikitext, template_name_pattern, char_name_for_log=""):
    new_wikitext = wikitext
    while True:
        indices = _find_template_block_indices(new_wikitext, template_name_pattern, char_name_for_log)
        if not indices: break
        t_start, _c_start, _c_end, t_end, _match = indices
        new_wikitext = new_wikitext[:t_start] + new_wikitext[t_end:]
    return new_wikitext.strip()

def clean_value(text, remove_links=True, remove_formatting_tags=True):
    """
    深度清理Wikitext/HTML混合值：
    1. 移除HTML注释。
    2. HTML实体解码。
    3. 处理特定Wikitext模板（黑幕、颜色、Ruby等），保留其核心文本。
       - {{黑幕| xxx }} -> xxx (如果xxx strip后为空，则结果为空字符串)
    4. 处理Wiki链接。
    5. 将 <br> 标签规范化为换行符 \n。
    6. 使用 BeautifulSoup 剥离所有剩余HTML标签（如 <font>, <span>, <p>, <div>），保留文本。
    7. 再次HTML实体解码（以防万一）。
    8. 移除Wiki格式化标记 (如 ''', '')。
    9. 规范化所有空白字符（空格、制表符、换行符）。
    """
    if text is None: return ""
    text = str(text)

    # 步骤 1: 移除HTML注释
    text = _remove_html_comments(text)
    if text is None: return "" # Defensive, _remove_html_comments should return "" for None input

    # 步骤 2: 初步HTML实体解码
    # 这有助于后续的正则匹配Wikitext模板时内容是可读的
    text = html.unescape(text)

    # 步骤 3: 处理Wikitext模板
    # {{黑幕|文本}} -> 文本 (如果文本部分 strip 后为空，则整个结果为空)
    def replace_heimu_content(match_obj):
        content = match_obj.group(1).strip() # 获取捕获组1（模板内容）并去除首尾空白
        return content # 如果内容为空白，strip后就是空字符串，符合要求
    text = re.sub(r"\{\{黑幕\|(.*?)\}\}", replace_heimu_content, text, flags=re.IGNORECASE | re.DOTALL)

    # {{Color|颜色|文本}} 或 {{Clr|颜色|文本}} -> 文本
    text = re.sub(r"\{\{(?:Color|Clr)\|[^|]*?\|([^}]*?)\}\}", r"\1", text, flags=re.IGNORECASE | re.DOTALL)
    
    # {{Ruby|基础字|注音}} -> 基础字
    text = re.sub(r"\{\{Ruby\|([^|]+?)\|[^}]+?\}\}", r"\1", text, flags=re.IGNORECASE)
    # 可以根据需要添加更多Wikitext模板的清理规则

    # 步骤 4: 处理Wiki链接 (如果需要)
    if remove_links:
        text = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+?)\]\]", r"\1", text)

    # 步骤 5: 将 <br> 标签规范化为换行符 \n (在BeautifulSoup处理之前)
    # 这有助于BeautifulSoup的get_text()能更好地反映前端换行效果
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    # 步骤 6: 使用 BeautifulSoup 剥离所有剩余 HTML 标签
    # 这会处理 <font>, <span>, <p>, <div>, <b>, <i> 等等
    try:
        # 仅当文本中确实存在HTML标签时才调用BeautifulSoup，避免不必要的开销和潜在错误
        if '<' in text and '>' in text:
            soup = BeautifulSoup(text, "lxml")
            # get_text(separator=" ", strip=True)
            # separator=" ": 用空格连接不同内联元素或文本块，避免粘连。
            # strip=True: 移除每个提取出的文本节点自身的前后空白，并且对最终结果也做strip。
            text = soup.get_text(separator=" ", strip=True)
        # else:
            # logger.debug(f"文本不包含HTML标签，跳过BeautifulSoup处理: '{text[:50]}...'")
    except Exception as e:
        logger.debug(f"BeautifulSoup在clean_value中解析失败 (文本可能已非标准HTML，或过于复杂): {e}. 文本片段: '{text[:100]}...'")
        # 回退策略：如果BeautifulSoup解析失败，使用更激进的正则移除所有HTML标签
        # 这可能不如BS精确，但可以作为一种保障
        text = re.sub(r"<[^>]+>", "", text)

    # 步骤 7: 再次进行HTML实体解码 (确保所有实体都被处理)
    text = html.unescape(text)

    # 步骤 8: 移除特定的Wiki格式化标记 (如果适用且未被BS清除)
    if remove_formatting_tags:
        text = re.sub(r"'''(.*?)'''", r"\1", text) # Wiki粗体 '''text''' -> text
        text = re.sub(r"''(.*?)''", r"\1", text)   # Wiki斜体 ''text'' -> text

    # 步骤 9: 规范化所有空白字符
    text = re.sub(r"[ \t]+", " ", text)         # 将多个空格或制表符替换为单个空格
    text = re.sub(r"\s*\n\s*", "\n", text)      # 清除换行符周围的空白字符
    text = re.sub(r"\n{2,}", "\n", text)        # 将两个或多个连续的换行符替换为单个换行符
    
    return text.strip() # 最后确保结果没有首尾空白


# --- 角色Wikitext特定信息提取模块 (与上一版类似，但调用新的clean_value) ---
def _extract_skills_info(wikitext_content, char_name_for_log=""):
    skills_data = {"active": [], "passive": []}
    if not wikitext_content: return skills_data

    skill_block_indices = _find_template_block_indices(wikitext_content, TPL_CHAR_SKILL_BLOCK_START, char_name_for_log)
    if not skill_block_indices: return skills_data
    
    _s_start, s_content_start, _s_content_end, s_block_end, _s_match = skill_block_indices
    end_block_match = re.search(r"\{\{\s*" + re.escape(TPL_CHAR_SKILL_BLOCK_END) + r"\s*\}\}", wikitext_content[s_content_start:], re.IGNORECASE | re.DOTALL)
    if not end_block_match: return skills_data
        
    skill_block_inner_content = wikitext_content[s_content_start : s_content_start + end_block_match.start()]

    skill_headers_matches = list(re.finditer(r"\{\{\s*(" + TPL_CHAR_SKILL_HEADER_PATTERN + r")\s*\|\s*([^}]+?)\s*\}\}", skill_block_inner_content, re.IGNORECASE | re.DOTALL))

    for i, header_match in enumerate(skill_headers_matches):
        skill_type_num = header_match.group(2)
        skill_name_raw = header_match.group(3).strip()
        skill_name_cleaned = clean_value(skill_name_raw) # 使用新的clean_value
        
        current_skill_content_start_idx = header_match.end()
        next_skill_content_end_idx = len(skill_block_inner_content)
        if i + 1 < len(skill_headers_matches):
            next_skill_content_end_idx = skill_headers_matches[i+1].start()
        
        this_skill_wikitext_segment = skill_block_inner_content[current_skill_content_start_idx:next_skill_content_end_idx]
        
        talent_params = get_template_params(this_skill_wikitext_segment, TPL_TALENT_SKILL, char_name_for_log)
        description = ""
        if talent_params:
            desc_raw = talent_params.get("描述", talent_params.get("效果"))
            # 对于技能描述，通常希望保留链接和一些基本格式，但移除复杂HTML。
            # remove_links=False 意味着 [[链接]] 会保留为 "链接"
            # remove_formatting_tags=True 会移除 '''bold''' 等
            description = clean_value(desc_raw, remove_links=False, remove_formatting_tags=True) # 使用新的clean_value
        
        skill_entry = {"name": skill_name_cleaned, "description": description}
        if skill_type_num in ['1', '2', '3']: skills_data["active"].append(skill_entry)
        elif skill_type_num == '4': skills_data["passive"].append(skill_entry)
            
    return skills_data

def _extract_constellations_info(wikitext_content, char_name_for_log=""):
    constellation_names = []
    const_params = get_template_params(wikitext_content, TPL_CHAR_CONSTELLATION, char_name_for_log)
    if const_params:
        for i in range(1, 7):
            name_raw = const_params.get(f"命之座{i}")
            if name_raw:
                name_cleaned = clean_value(name_raw) # 使用新的clean_value
                if name_cleaned: constellation_names.append(name_cleaned)
    return constellation_names

# --- Wikitext深度处理与数据提取主流程 ---
def process_character_wikitext(raw_wikitext, char_name_for_log=""):
    if not raw_wikitext: return "", {}

    processed_text = _remove_html_comments(raw_wikitext) # 初始HTML注释清理
    if processed_text is None: processed_text = raw_wikitext

    # 移除特定不需要的整个块
    processed_text = re.sub(r"<bstyle>.*?</bstyle>", "", processed_text, flags=re.DOTALL | re.IGNORECASE)
    processed_text = re.sub(r"<div\s+class\s*=\s*([\"'])poke-bg\1[^>]*>.*?</div>", "", processed_text, flags=re.DOTALL | re.IGNORECASE)
    
    # 移除角色属性数据模板块 ({{角色/属性数据 ... }})
    processed_text = remove_template_block(processed_text, TPL_CHAR_ATTR_DATA, char_name_for_log)

    # 提取结构化信息 (技能、命座) - 从当前已部分清理的文本中提取
    extracted_data = {}
    extracted_data["skills"] = _extract_skills_info(processed_text, char_name_for_log)
    extracted_data["constellation_names"] = _extract_constellations_info(processed_text, char_name_for_log)

    # 移除已提取信息的模板块 (如天赋技能模板, 命之座模板)
    # 注意: {{天赋技能}} 模板通常在 {{角色技能|开始}} 块内部，其内容（描述）已被提取并清理。
    # 这里主要移除外层的、独立的、或不再需要的模板结构。
    processed_text = remove_template_block(processed_text, TPL_TALENT_SKILL, char_name_for_log)
    processed_text = remove_template_block(processed_text, TPL_CHAR_CONSTELLATION, char_name_for_log)
    # processed_text = remove_template_block(processed_text, TPL_CHAR_SKILL_BLOCK_START, char_name_for_log) # 如果要移除整个技能块

    # 针对整个剩余文本进行一次最终的深度清理，使用新的 clean_value
    # 这会处理所有残留的Wikitext和HTML标记
    final_cleaned_text = clean_value(processed_text, remove_links=True, remove_formatting_tags=True)

    return final_cleaned_text, extracted_data


# --- SQLite 二级缓存模块 (与上一版相同) ---

# --- SQLite Datetime Adapters (to address DeprecationWarning) ---
def adapt_datetime_iso(val):
    """Adapt datetime.datetime to ISO 8601 string."""
    return val.isoformat()

def convert_datetime_from_iso(val_bytes):
    """Convert ISO 8601 string from database back to datetime.datetime."""
    # SQLite stores DATETIME as TEXT, so val_bytes will be a byte string.
    return datetime.fromisoformat(val_bytes.decode())

sqlite3.register_adapter(datetime, adapt_datetime_iso)
# The type name "DATETIME" must match how you defined the column in CREATE TABLE.
sqlite3.register_converter("DATETIME", convert_datetime_from_iso)


def _init_secondary_cache_db():
    conn = sqlite3.connect(SECOND_LEVEL_CACHE_FILE)
    cursor = conn.cursor()
    cursor.execute(f"CREATE TABLE IF NOT EXISTS {WIKITEXT_TABLE_NAME} (url_key TEXT PRIMARY KEY, processed_wikitext TEXT, timestamp DATETIME)")
    conn.commit()
    conn.close()
    logger.info(f"二级缓存数据库 {SECOND_LEVEL_CACHE_FILE} (表: {WIKITEXT_TABLE_NAME}) 初始化/已存在。")

def _get_from_secondary_cache(url_key):
    if not url_key: return None
    conn = sqlite3.connect(SECOND_LEVEL_CACHE_FILE); cursor = conn.cursor()
    cursor.execute(f"SELECT processed_wikitext FROM {WIKITEXT_TABLE_NAME} WHERE url_key = ?", (url_key,))
    row = cursor.fetchone(); conn.close()
    return row[0] if row else None

def _save_to_secondary_cache(url_key, processed_wikitext):
    if not url_key: logger.error("尝试使用空的url_key保存到二级缓存，已跳过。"); return False
    conn = sqlite3.connect(SECOND_LEVEL_CACHE_FILE); cursor = conn.cursor()
    try:
        text_to_save = processed_wikitext if processed_wikitext is not None else ""
        cursor.execute(f"INSERT OR REPLACE INTO {WIKITEXT_TABLE_NAME} (url_key, processed_wikitext, timestamp) VALUES (?, ?, ?)", (url_key, text_to_save, datetime.now()))
        conn.commit(); return True
    except sqlite3.Error as e: logger.error(f"保存到二级缓存数据库时出错 for key {url_key}: {e}"); return False
    finally: conn.close()


# --- 网络请求与原始Wikitext提取模块 (与上一版相同) ---
def _fetch_edit_page_response(url, session, item_name_for_log=""):
    ua = UserAgent(); headers = {"User-Agent": ua.random}
    log_prefix = f"[{item_name_for_log}] " if item_name_for_log else ""
    try:
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        if not response.from_cache: logger.info(f"{log_prefix}数据来自服务器 (URL: {url})"); sleep(1.2)
        else: logger.debug(f"{log_prefix}数据来自一级缓存 (URL: {url})")
        return response
    except requests.exceptions.Timeout: logger.error(f"{log_prefix}获取编辑页超时: {url}")
    except requests.exceptions.HTTPError as e: logger.error(f"{log_prefix}获取编辑页HTTP错误 {e.response.status_code}: {url}")
    except requests.exceptions.RequestException as e: logger.error(f"{log_prefix}获取编辑页请求错误: {e} (URL: {url})")
    return None

def _extract_raw_wikitext_from_html(html_content, item_name_for_log=""):
    log_prefix = f"[{item_name_for_log}] " if item_name_for_log else ""
    if not html_content: logger.warning(f"{log_prefix}HTML内容为空，无法提取原始Wikitext。"); return None
    soup = BeautifulSoup(html_content, 'lxml')
    textarea_tag = soup.find('textarea', id='wpTextbox1')
    if not textarea_tag: logger.warning(f"{log_prefix}未在HTML中找到 <textarea id='wpTextbox1'>。"); return None
    return textarea_tag.get_text(strip=False)

def _get_edit_page_url(detail_url, item_name_for_log=""):
    log_prefix = f"[{item_name_for_log}] " if item_name_for_log else ""
    if not detail_url: logger.warning(f"{log_prefix}详情页URL为空。"); return None
    base_detail_url = detail_url.split('?')[0].split('#')[0]
    expected_prefix = BASE_URL + "/ys/"
    if not base_detail_url.startswith(expected_prefix): 
        logger.error(f"{log_prefix}详情页URL '{base_detail_url}' 格式不符预期。"); return None
    page_title_part = base_detail_url[len(expected_prefix):]
    if not page_title_part: 
        logger.error(f"{log_prefix}从详情页URL '{base_detail_url}' 提取页面标题失败。"); return None
    return f"{BASE_URL}/ys/index.php?title={page_title_part}&action=edit"


# --- 单个角色条目处理主流程 (与上一版相同，但调用新的 process_character_wikitext) ---
def _process_single_character(character_item, first_level_session):
    name = character_item.get("name", "未知角色")
    detail_url = character_item.get("detail_url")
    log_prefix = f"[{name}] "

    edit_page_url = _get_edit_page_url(detail_url, name)
    if not edit_page_url:
        return None, None, f"无法为角色'{name}'构建编辑页URL (详情URL: {detail_url})"

    cached_processed_text = _get_from_secondary_cache(edit_page_url)
    if cached_processed_text is not None:
        logger.debug(f"{log_prefix}处理后的Wikitext已在二级缓存中。")
        _re_cleaned_text, extracted_data_from_cache = process_character_wikitext(cached_processed_text, name) # 重新提取结构化数据
        return cached_processed_text, extracted_data_from_cache, None

    logger.info(f"{log_prefix}处理后Wikitext不在二级缓存，尝试获取原始数据。")
    response = _fetch_edit_page_response(edit_page_url, first_level_session, name)
    if not response: return None, None, f"获取原始编辑页失败: {edit_page_url}"

    try:
        encoding_to_try = response.encoding or response.apparent_encoding or 'utf-8'
        html_text = response.content.decode(encoding_to_try, errors='replace')
    except Exception as e: return None, None, f"HTML解码错误: {str(e)}"

    raw_wikitext = _extract_raw_wikitext_from_html(html_text, name)
    if raw_wikitext is None: return None, None, "未能从HTML提取原始Wikitext"

    final_processed_wikitext, extracted_data = process_character_wikitext(raw_wikitext, name)

    if _save_to_secondary_cache(edit_page_url, final_processed_wikitext):
        logger.info(f"{log_prefix}已处理Wikitext并存入二级缓存。新文本长度: {len(final_processed_wikitext)}")
    else:
        return final_processed_wikitext, extracted_data, "二级缓存保存失败" 
        
    return final_processed_wikitext, extracted_data, None


# --- 主程序 (与上一版类似) ---
def main():
    _init_secondary_cache_db() 
    character_data_list = []
    try:
        with open(INPUT_JSON_FILE, "r", encoding="utf-8") as f: character_data_list = json.load(f)
        logger.info(f"从 {INPUT_JSON_FILE} 加载了 {len(character_data_list)} 条角色数据。")
    except FileNotFoundError: logger.error(f"输入文件 {INPUT_JSON_FILE} 未找到。"); return
    except json.JSONDecodeError: logger.error(f"输入文件 {INPUT_JSON_FILE} JSON格式无效。"); return
    except Exception as e: logger.error(f"加载 {INPUT_JSON_FILE} 时发生未知错误: {e}。"); return
    if not character_data_list: logger.warning("输入数据为空。"); return

    if os.path.exists(FIRST_LEVEL_CACHE_FILE):
        try: os.remove(FIRST_LEVEL_CACHE_FILE); logger.info(f"已删除旧一级缓存: {FIRST_LEVEL_CACHE_FILE}。")
        except OSError as e: logger.error(f"删除旧一级缓存失败: {e}。")
    
    with requests_cache.CachedSession(RAW_EDIT_PAGES_CACHE_NAME, backend="sqlite") as first_level_session:
        logger.info(f"一级缓存配置: {os.path.abspath(FIRST_LEVEL_CACHE_FILE)}")
        total_items = len(character_data_list)
        newly_processed_count = 0
        all_output_data = []

        for index, character_item in enumerate(character_data_list):
            current_item_num = index + 1; char_name = character_item.get("name", f"未知_{current_item_num}")
            progress_bar_width = 35
            filled_len = int(progress_bar_width * current_item_num // total_items)
            bar = '█' * filled_len + '-' * (progress_bar_width - filled_len)
            print(f"\r处理: |{bar}| {current_item_num}/{total_items} ({char_name})", end="")

            edit_url_for_check = _get_edit_page_url(character_item.get('detail_url'), char_name)
            is_new_to_cache = True
            if edit_url_for_check: is_new_to_cache = (_get_from_secondary_cache(edit_url_for_check) is None)
            
            processed_text, extracted_info, error_msg = _process_single_character(character_item, first_level_session)
            
            output_item = {**character_item, "wikitext": processed_text}
            if extracted_info: output_item.update(extracted_info) 
            if error_msg: 
                output_item["processing_error_info"] = error_msg
                if current_item_num == 1 or is_new_to_cache : print() 
                logger.warning(f"[{char_name}] 处理时备注/错误: {error_msg}")
            
            if processed_text is None and not error_msg:
                 output_item["processing_error_info"] = "Wikitext处理后为None但无明确错误"
                 if current_item_num == 1 or is_new_to_cache : print()
                 logger.error(f"[{char_name}] Wikitext处理后为None但无明确错误。")

            if is_new_to_cache and processed_text is not None and not error_msg: newly_processed_count += 1
            all_output_data.append(output_item)
        
        print()
        logger.info(f"所有角色处理完毕。总数: {total_items}。本次新处理并存入二级缓存: {newly_processed_count}")
        
        conn_s_cache = sqlite3.connect(SECOND_LEVEL_CACHE_FILE); cursor_s_cache = conn_s_cache.cursor()
        try:
            cursor_s_cache.execute(f"SELECT COUNT(*) FROM {WIKITEXT_TABLE_NAME}")
            logger.info(f"二级缓存 {SECOND_LEVEL_CACHE_FILE} 总条目数: {cursor_s_cache.fetchone()[0]}")
        except sqlite3.Error as e: logger.error(f"查询二级缓存总数时出错: {e}")
        finally: conn_s_cache.close()

        if all_output_data:
            with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(all_output_data, f, ensure_ascii=False, indent=4)
            logger.info(f"已保存 {len(all_output_data)} 条数据到 {OUTPUT_JSON_FILE}")
        else: logger.warning("无数据输出。")

    try: pass
    except Exception as e: logger.exception(f"主函数发生严重异常: {e}")
    finally: logger.info("脚本执行结束。")

if __name__ == "__main__":
    main()
