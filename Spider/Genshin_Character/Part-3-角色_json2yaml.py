# 版本号: v_NewDesign_Wikitext_Unified{Part-3-角色_json2yaml_final_logging.py}
import json
import logging
import os
import re
import html
import yaml

# --- 配置与常量 ---
INPUT_JSON_FILE = "character_details_final_refined.json" # 输入的JSON文件名 (来自Part-2的输出)
BASE_OUTPUT_DIR = "./角色资料" # 生成YAML文件的基础输出目录
LOG_FILE_NAME = "part3_character_json2yaml.log" # 日志文件名

# Wikitext模板名称常量
TPL_CHARACTER_BASE = "角色" # 角色基本信息模板
TPL_CHARACTER_INFO = "角色/信息" # 角色补充信息模板
TPL_CHARACTER_STORY = "角色/故事" # 角色故事模板
TPL_CHARACTER_CONSTELLATION = "角色/命之座" # 角色命之座模板
TPL_CHARACTER_ASCENSION = "角色/突破简" # 角色突破材料简化模板
TPL_CHARACTER_SKILL_UPGRADE = "角色/技能升级材料简" # 角色技能升级材料简化模板

# YAML生成时需要预先移除的字段和区域列表
FIELDS_TO_REMOVE_FROM_YAML = [
    "TAG", # 标签字段
    "实装日期", # 实装日期字段
    "实装版本", # 实装版本字段
    "中文CV", # 中文配音演员字段
    "日文CV", # 日文配音演员字段
    "韩文CV", # 韩文配音演员字段
    "英文CV", # 英文配音演员字段
]
SECTIONS_TO_REMOVE_FROM_YAML = [
    "突破材料", # 整个突破材料区域
    "天赋升级材料", # 整个天赋升级材料区域
]


# --- 日志模块 ---
def setup_logger_p3(log_file_path):
    """配置日志记录器 (Part-3专用)"""
    if os.path.exists(log_file_path): # 如果旧日志文件存在
        try: os.remove(log_file_path) # 尝试删除
        except OSError as e: print(f"删除旧日志文件 {log_file_path} 时出错: {e}")

    logger_instance = logging.getLogger(__name__ + "_p3_logger") # 创建或获取logger实例，避免与全局logger冲突
    logger_instance.handlers = [] # 清空已有的处理器，防止重复日志
    logger_instance.setLevel(logging.INFO) # 设置日志级别
    # 定义日志格式
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s")

    # 文件处理器
    file_h = logging.FileHandler(log_file_path, encoding="utf-8")
    file_h.setFormatter(formatter)
    logger_instance.addHandler(file_h)

    # 控制台流处理器
    stream_h = logging.StreamHandler()
    stream_h.setFormatter(formatter)
    logger_instance.addHandler(stream_h)
    return logger_instance

logger = setup_logger_p3(LOG_FILE_NAME) # 初始化日志记录器

# --- Wikitext 解析与清理辅助函数 (Part-3专用，完整定义) ---
def _remove_html_comments_p3(text_content):
    """移除文本中的HTML注释 (<!-- ... -->)"""
    if text_content is None: return "" # 如果输入为None，返回空字符串
    return re.sub(r'<!--.*?-->', '', text_content, flags=re.DOTALL) # 使用正则替换

def _find_template_block_indices_p3(wikitext, template_name_pattern, char_name_for_log=""):
    """
    查找Wikitext中指定模板的起始和结束索引。
    返回元组: (模板起始索引, 参数部分起始索引, 参数部分结束索引, 模板块结束索引, 正则匹配对象)
    如果未找到模板，返回None。
    """
    if not wikitext or not template_name_pattern: return None # 输入校验

    # 构建模板起始标签的正则表达式
    # 如果template_name_pattern是简单字符串（不含正则特殊字符），则进行转义
    if isinstance(template_name_pattern, str) and not any(c in template_name_pattern for c in r".*+?^$()[]{}|\\"):
        start_tag_regex_str = r"\{\{\s*" + re.escape(template_name_pattern) + r"\s*(?=\||\}\})" # 匹配 {{模板名 后跟 | 或 }}
    else: # 如果已经是正则表达式模式
        start_tag_regex_str = r"\{\{\s*" + template_name_pattern + r"\s*(?=\||\}\})"

    match = re.search(start_tag_regex_str, wikitext, re.IGNORECASE | re.DOTALL) # 忽略大小写，点号匹配换行
    if not match: return None # 未找到起始标签

    template_start_index = match.start() # 模板 {{ 的起始位置
    params_part_start_index = match.end() # 模板名之后，参数部分开始的位置
    
    # 通过计算括号层级来确定模板的结束位置，以处理嵌套模板
    scan_start_pos_for_braces = template_start_index + 2 # 从 {{ 之后开始扫描
    current_level_for_block = 1 # 初始层级为1 (因为已经匹配了外层的 {{ )
    template_block_end_idx = -1 # 模板块的结束索引 (}} 之后的位置)

    # 遍历文本，寻找匹配的结束 }}
    for i in range(scan_start_pos_for_braces, len(wikitext) -1):
        if wikitext[i:i+2] == '{{': #遇到嵌套的 {{
            current_level_for_block += 1; i += 1 # 跳过一个字符，因为检查的是两个字符
        elif wikitext[i:i+2] == '}}': # 遇到 }}
            current_level_for_block -= 1
            if current_level_for_block == 0: # 如果层级归零，说明找到了最外层模板的结束
                template_block_end_idx = i + 2 # 记录 }} 之后的位置
                break
            i += 1 # 跳过一个字符
    
    if template_block_end_idx == -1: # 如果没有找到匹配的结束 }}
        logger.debug(f"[{char_name_for_log}] 模板 '{template_name_pattern}' (始于索引 {template_start_index}) 未找到匹配的 '}}'。")
        return None
    
    params_part_end_index = template_block_end_idx - 2 # 参数部分的结束索引 (在 }} 之前)
    return template_start_index, params_part_start_index, params_part_end_index, template_block_end_idx, match

def _parse_params_from_str_p3(params_str, char_name_for_log=""):
    """从模板参数字符串中解析键值对。例如："|名称=苹果|介绍=一种水果" """
    params = {} # 初始化参数字典
    if not params_str: return params # 如果参数字符串为空，直接返回

    # 正则匹配 "|键=值" 的模式，值可以跨越多行，直到下一个 "|键=" 或字符串末尾
    param_matches = re.finditer(r"\|\s*([^=]+?)\s*=\s*(.*?)(?=\s*\|\s*[^=]+?=|\Z)", params_str, re.DOTALL | re.UNICODE)
    for p_match in param_matches:
        key = p_match.group(1).strip() # 提取并清理键名
        value = p_match.group(2).strip() # 提取并清理值
        params[key] = value
        
    # 处理无名参数或整个字符串作为第一个参数的情况
    if not params and params_str.strip(): # 如果没有解析出命名参数，且参数字符串不为空
        if not params_str.strip().startswith("|") and "=" not in params_str : # 如果不以 | 开头且不含 =，则视为模板的第一个匿名参数
             params["1"] = params_str.strip()
        elif params_str.strip().startswith("|"): # 如果以 | 开头，尝试解析为纯匿名参数列表
            parts = params_str.split('|')[1:] # 按 | 分割，并去掉第一个空元素
            all_unnamed = all("=" not in part_val for part_val in parts) # 检查是否所有部分都不含 =
            if all_unnamed: # 如果都是匿名参数
                for i, part_val in enumerate(parts): params[str(i+1)] = part_val.strip() # 按顺序编号
    return params

def get_template_params_p3(wikitext, template_name, char_name_for_log=""):
    """获取指定模板的参数字典"""
    indices = _find_template_block_indices_p3(wikitext, template_name, char_name_for_log) # 查找模板位置
    if not indices: return None # 未找到模板
    _t_start, p_start, p_end, _t_end, _match = indices # 解包索引
    return _parse_params_from_str_p3(wikitext[p_start:p_end].strip(), char_name_for_log) # 解析参数字符串

def clean_value_p3(text, remove_links=True, remove_formatting_tags=True):
    """深度清理Wikitext/HTML混合值，返回纯文本"""
    if text is None: return "" # 空值处理
    text = str(text) # 确保是字符串
    text = _remove_html_comments_p3(text) # 移除HTML注释
    if text is None: return "" # 防御性检查
    text = html.unescape(text) # HTML实体解码

    # 处理 {{黑幕|内容}} -> 内容 (如果内容为空白则结果为空)
    def replace_heimu(match): return match.group(1).strip() # 回调函数用于处理黑幕内容
    text = re.sub(r"\{\{黑幕\|(.*?)\}\}", replace_heimu, text, flags=re.IGNORECASE | re.DOTALL)
    # 处理 {{颜色|...|文本}} -> 文本
    text = re.sub(r"\{\{(?:Color|Clr)\|[^|]*?\|([^}]*?)\}\}", r"\1", text, flags=re.IGNORECASE | re.DOTALL)
    # 处理 {{Ruby|基础字|注音}} -> 基础字
    text = re.sub(r"\{\{Ruby\|([^|]+?)\|[^}]+?\}\}", r"\1", text, flags=re.IGNORECASE)

    if remove_links: # 如果需要移除Wiki链接
        text = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+?)\]\]", r"\1", text) # [[链接|文本]] -> 文本, [[链接]] -> 链接
    
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE) # <br> 替换为换行符

    # 使用BeautifulSoup剥离HTML标签，保留文本
    try:
        if '<' in text and '>' in text: # 初步判断是否包含HTML标签
            soup = BeautifulSoup(text, "lxml")
            text = soup.get_text(separator=" ", strip=True) # 获取纯文本，用空格分隔，并去除首尾空白
    except Exception: # 如果BS解析失败
        text = re.sub(r"<[^>]+>", "", text) # 使用正则粗略移除所有HTML标签

    text = html.unescape(text) # 再次HTML实体解码，以防万一
    if remove_formatting_tags: # 如果需要移除Wiki格式化标记
        text = re.sub(r"'''(.*?)'''", r"\1", text) # 粗体 '''text''' -> text
        text = re.sub(r"''(.*?)''", r"\1", text)   # 斜体 ''text'' -> text

    # 规范化空白字符
    text = re.sub(r"[ \t]+", " ", text)         # 多个空格/制表符变单个空格
    text = re.sub(r"\s*\n\s*", "\n", text)      # 移除换行符周围的空白
    text = re.sub(r"\n{2,}", "\n", text)        # 多个换行符变单个
    return text.strip() # 返回最终清理并去除首尾空白的文本

# --- 数据提取函数 (用于Part-3，提取逻辑不变，空值处理交由后续deep_clean) ---
def extract_character_base_info_p3(wikitext, char_name):
    """从 {{角色}} 模板提取基本信息"""
    params = get_template_params_p3(wikitext, TPL_CHARACTER_BASE, char_name)
    data = {}
    if not params: return data
    # 定义需要提取的基础字段
    all_base_fields = ["名称", "称号", "全名", "英文名称", "稀有度", "所属", "种族", "介绍", 
                       "元素属性", "武器类型", "命之座", "特殊料理", "性别", "TAG", "实装日期", "实装版本"]
    for f_name in all_base_fields:
        if f_name in FIELDS_TO_REMOVE_FROM_YAML: continue # 如果字段在预移除列表，则跳过
        val = params.get(f_name)
        if val is not None: # 如果模板中有此字段
            # 介绍字段保留链接，其他字段移除链接
            cleaned_val = clean_value_p3(val, remove_links=(f_name != "介绍"))
            if f_name == "TAG": # TAG字段特殊处理，分割为列表
                data[f_name] = [t.strip() for t in cleaned_val.split('、') if t.strip()] # 保留非空TAG
            else:
                data[f_name] = cleaned_val # 直接赋值，空字符串由后续deep_clean处理
    return data

def extract_character_additional_info_p3(wikitext, char_name):
    """从 {{角色/信息}} 模板提取补充信息"""
    params = get_template_params_p3(wikitext, TPL_CHARACTER_INFO, char_name)
    data = {}
    if not params: return data
    # 定义需要提取的补充字段
    all_additional_fields = ["昵称/外号", "中文CV", "日文CV", "韩文CV", "英文CV", "生日", "体型", 
                             "个人任务", "衣装名称", "归属", "职业", "名片名称", "名片描述"]
    for f_name in all_additional_fields:
        if f_name in FIELDS_TO_REMOVE_FROM_YAML: continue # 如果字段在预移除列表，则跳过
        val = params.get(f_name)
        if val is not None:
            cleaned_val = clean_value_p3(val)
            # CV和昵称字段，如果包含分隔符，则处理为列表
            if f_name in ["中文CV", "日文CV", "韩文CV", "英文CV", "昵称/外号"]:
                split_values = [s.strip() for s in re.split(r'[&、,，]', cleaned_val) if s.strip()] # 按多种分隔符分割
                data[f_name] = split_values[0] if len(split_values) == 1 else split_values # 单个值直接存，多个值存列表
            else:
                data[f_name] = cleaned_val
    return data

def extract_character_stories_p3(wikitext, char_name):
    """从 {{角色/故事}} 模板提取故事信息"""
    params = get_template_params_p3(wikitext, TPL_CHARACTER_STORY, char_name)
    stories = {}
    if not params: return stories
    # 遍历所有参数，提取故事相关的字段
    for key, val in params.items():
        if key.startswith("角色故事") or key in ["角色详细", "神之眼", "冒险笔记名称", "冒险笔记", "冒险笔记1"]:
            cleaned_val = clean_value_p3(val, remove_links=False) # 故事内容保留链接
            stories[key] = cleaned_val
    return stories

def extract_character_constellation_details_p3(wikitext, char_name, existing_names_from_part2):
    """从 {{角色/命之座}} 模板提取命之座详情 (名称和效果)"""
    params = get_template_params_p3(wikitext, TPL_CHARACTER_CONSTELLATION, char_name)
    constellations = [] # 存储命之座对象的列表
    if not params: return constellations
    for i in range(1, 7): # 遍历1到6命
        name_raw = params.get(f"命之座{i}") # 获取原始名称
        effect_raw = params.get(f"命之座{i}效果") # 获取原始效果描述
        
        name_cleaned = clean_value_p3(name_raw) if name_raw else "" # 清理名称
        # 如果Part-3解析的名称为空，但Part-2提取到了，则使用Part-2的
        if not name_cleaned and i-1 < len(existing_names_from_part2):
            name_cleaned = existing_names_from_part2[i-1]
            
        effect_cleaned = clean_value_p3(effect_raw, remove_links=False) if effect_raw else "" # 清理效果，保留链接
        
        const_item = {"名称": name_cleaned, "效果": effect_cleaned} # 构建命之座对象
        constellations.append(const_item)
    return constellations

def extract_materials_p3(wikitext, template_name, char_name):
    """从指定材料模板 (如 {{角色/突破简}}) 提取材料信息"""
    params = get_template_params_p3(wikitext, template_name, char_name)
    materials = {}
    if not params: return materials
    for key, val in params.items():
        cleaned_val = clean_value_p3(val)
        # 如果键名包含"序列"且值包含顿号，则分割为列表
        if "序列" in key and '、' in cleaned_val:
            materials[key] = [m.strip() for m in cleaned_val.split('、') if m.strip()]
        else:
            materials[key] = cleaned_val
    return materials

# --- 深度清理空字符串值的函数 ---
def deep_clean_empty_strings(data_structure):
    """
    递归地移除数据结构（字典或列表）中值为单个空字符串('')的项。
    如果字典或列表在清理后变为空，则返回None，以便上层移除该结构。
    """
    if isinstance(data_structure, dict): # 如果是字典
        cleaned_dict = {} # 创建新字典存储清理结果
        for k, v in data_structure.items():
            if isinstance(v, str) and v == '': # 如果值是空字符串，则跳过此键值对
                continue
            
            cleaned_v = deep_clean_empty_strings(v) # 递归清理值
            
            # 如果清理后的值不是None (None表示原结构变空)
            if cleaned_v is not None:
                 if isinstance(cleaned_v, str) and cleaned_v == '': # 再次检查，理论上不会发生
                     pass
                 else:
                     cleaned_dict[k] = cleaned_v # 添加到新字典
        
        return cleaned_dict if cleaned_dict else None # 如果新字典为空，返回None

    elif isinstance(data_structure, list): # 如果是列表
        cleaned_list = [] # 创建新列表存储清理结果
        for item in data_structure:
            cleaned_item = deep_clean_empty_strings(item) # 递归清理列表项
            if cleaned_item is not None : # 如果清理后的项不是None
                if isinstance(cleaned_item, str) and cleaned_item == '': # 不添加独立的空字符串到列表
                    pass
                else:
                    cleaned_list.append(cleaned_item) # 添加到新列表
        
        return cleaned_list if cleaned_list else None # 如果新列表为空，返回None
    
    return data_structure # 其他类型 (如数字、非空字符串、布尔值) 直接返回

# --- YAML 生成辅助 ---
def sanitize_filename_p3(name):
    """清理文件名中的非法字符"""
    name = re.sub(r'[\\/*?:"<>|]', "_", name) # 替换Windows非法字符
    name = re.sub(r"[\x00-\x1f\x7f]", "", name) # 移除控制字符
    name = re.sub(r"__+", "_", name) # 多个下划线变单个
    return name.strip() # 去除首尾空白

def represent_multiline_str_p3(dumper, data):
    """自定义PyYAML的字符串表示方式，使多行字符串使用'|'风格"""
    if '\n' in data: # 如果字符串包含换行符
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|') # 使用'|'风格
    return dumper.represent_scalar('tag:yaml.org,2002:str', data) # 否则使用默认风格

yaml.add_representer(str, represent_multiline_str_p3, Dumper=yaml.SafeDumper) # 应用自定义表示

# --- 主处理逻辑 ---
def main():
    """脚本主函数"""
    if not os.path.exists(BASE_OUTPUT_DIR): # 如果输出目录不存在
        os.makedirs(BASE_OUTPUT_DIR); logger.info(f"已创建输出目录: {BASE_OUTPUT_DIR}")

    try: # 尝试加载输入的JSON文件
        with open(INPUT_JSON_FILE, "r", encoding="utf-8") as f: all_char_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"错误: 输入文件 {INPUT_JSON_FILE} 未找到。程序终止。")
        return
    except json.JSONDecodeError as e:
        logger.error(f"错误: 解析输入文件 {INPUT_JSON_FILE} JSON失败: {e}。程序终止。")
        return
    except Exception as e:
        logger.error(f"错误: 加载 {INPUT_JSON_FILE} 时发生未知错误: {e}。程序终止。")
        return
    
    if not all_char_data:
        logger.warning("警告: 输入JSON文件数据为空，没有可处理的角色。")
        return

    processed_count, skipped_count = 0, 0 # 成功处理和跳过的计数器
    skipped_or_failed_names = [] # 用于记录跳过或失败的角色名列表

    for char_item in all_char_data: # 遍历每个角色数据
        json_name_from_input = char_item.get("name", "未知角色") # 从输入JSON获取名称
        raw_wikitext_from_input = char_item.get("wikitext") # 从输入JSON获取原始wikitext

        current_processing_name = json_name_from_input # 当前处理的角色名，用于日志

        if not raw_wikitext_from_input: # 如果wikitext为空
            logger.warning(f"角色 '{current_processing_name}' 的wikitext为空, 跳过处理.")
            skipped_count += 1
            skipped_or_failed_names.append(f"{current_processing_name} (Wikitext为空)")
            continue
        
        logger.info(f"开始处理角色: {current_processing_name}")
        character_yaml_payload = {} # 初始化当前角色的YAML数据载体
        
        # 1. 提取各类信息
        base_info = extract_character_base_info_p3(raw_wikitext_from_input, current_processing_name)
        # 使用 {{角色}} 模板中的 "名称" 字段作为权威名称 (如果存在)
        authoritative_name = base_info.get("名称", current_processing_name).strip()
        if not authoritative_name: authoritative_name = current_processing_name # Fallback if cleaned name is empty
        current_processing_name = authoritative_name # 更新日志中使用的名称

        additional_info = extract_character_additional_info_p3(raw_wikitext_from_input, current_processing_name)
        stories_info = extract_character_stories_p3(raw_wikitext_from_input, current_processing_name)
        ascension_materials = extract_materials_p3(raw_wikitext_from_input, TPL_CHARACTER_ASCENSION, current_processing_name)
        skill_upgrade_materials = extract_materials_p3(raw_wikitext_from_input, TPL_CHARACTER_SKILL_UPGRADE, current_processing_name)
        
        # 从Part-2的输出中获取已提取的命之座名称和技能信息
        constellation_names_from_part2 = char_item.get("constellation_names", [])
        constellation_details = extract_character_constellation_details_p3(raw_wikitext_from_input, current_processing_name, constellation_names_from_part2)
        skills_from_part2 = char_item.get("skills") # 这是已经结构化的技能数据
        page_pure_text_from_part2 = char_item.get("final_wikitext", "").strip() # Part-2处理后的纯文本

        # 2. 组装YAML数据载体
        if base_info: character_yaml_payload["基本信息"] = base_info
        if additional_info: character_yaml_payload["补充信息"] = additional_info
        if stories_info: character_yaml_payload["角色故事"] = stories_info
        
        # 根据配置决定是否添加突破和天赋材料区域
        if ascension_materials and "突破材料" not in SECTIONS_TO_REMOVE_FROM_YAML:
            character_yaml_payload["突破材料"] = ascension_materials
        if skill_upgrade_materials and "天赋升级材料" not in SECTIONS_TO_REMOVE_FROM_YAML:
            character_yaml_payload["天赋升级材料"] = skill_upgrade_materials
            
        if constellation_details: character_yaml_payload["命之座"] = constellation_details
        
        if skills_from_part2: # 处理Part-2传递过来的技能信息
            structured_skills = {}
            if skills_from_part2.get("active"): structured_skills["主动技能"] = skills_from_part2["active"]
            if skills_from_part2.get("passive"): structured_skills["被动技能"] = skills_from_part2["passive"]
            if structured_skills: character_yaml_payload["天赋技能"] = structured_skills
            
        if page_pure_text_from_part2: character_yaml_payload["页面纯文本内容"] = page_pure_text_from_part2

        # 3. 初步过滤 (移除配置中指定的顶级区域，以及内容为空的顶级区域)
        intermediate_payload = {}
        for k_section, v_section_payload in character_yaml_payload.items():
            if k_section in SECTIONS_TO_REMOVE_FROM_YAML: # 如果区域在预移除列表
                logger.debug(f"[{current_processing_name}] 预移除顶级区域 (配置指定): {k_section}")
                continue
            if v_section_payload: # 只保留有内容的顶级区域
                intermediate_payload[k_section] = v_section_payload
            else:
                logger.debug(f"[{current_processing_name}] 预移除顶级区域 (因内容为空): {k_section}")
        
        if not intermediate_payload: # 如果初步过滤后整个payload为空
            logger.warning(f"角色 '{current_processing_name}' 的YAML内容在初步过滤后为空, 跳过生成文件.")
            skipped_count += 1
            skipped_or_failed_names.append(f"{current_processing_name} (初步过滤后内容为空)")
            continue

        # 4. 深度清理空字符串值
        final_cleaned_payload = deep_clean_empty_strings(intermediate_payload)

        if not final_cleaned_payload: # 如果深度清理后整个payload变为空 (None)
            logger.warning(f"角色 '{current_processing_name}' 的YAML内容在深度清理空字符串后变为空, 跳过生成文件.")
            skipped_count += 1
            skipped_or_failed_names.append(f"{current_processing_name} (深度清理后内容为空)")
            continue
            
        # 5. 准备输出YAML
        yaml_output_structure = {current_processing_name: final_cleaned_payload} # 最终YAML结构，顶层键为角色名
        yaml_filename = sanitize_filename_p3(current_processing_name) + ".yaml" # 清理文件名
        yaml_filepath = os.path.join(BASE_OUTPUT_DIR, yaml_filename) # 构建完整文件路径

        try: # 尝试写入YAML文件
            with open(yaml_filepath, "w", encoding="utf-8") as yf:
                yaml.dump(yaml_output_structure, yf, allow_unicode=True, sort_keys=False, Dumper=yaml.SafeDumper, indent=2)
            logger.info(f"已保存 [{current_processing_name}] 的YAML数据到: {yaml_filepath}")
            processed_count += 1
        except Exception as e: # 如果写入失败
            logger.error(f"写入YAML文件 {yaml_filepath} 失败: {e}")
            skipped_count += 1
            skipped_or_failed_names.append(f"{current_processing_name} (YAML写入失败: {e})")

    # --- 脚本结束，打印总结信息 ---
    logger.info(f"--- Part-3 (最终日志版) 处理完成 ---")
    logger.info(f"总共处理JSON条目数: {len(all_char_data)}")
    logger.info(f"成功生成YAML文件数: {processed_count}")
    logger.info(f"跳过或生成失败的角色数: {skipped_count}")
    if skipped_or_failed_names: # 如果有跳过或失败的角色
        logger.info("以下角色被跳过或处理失败:")
        for name_reason in skipped_or_failed_names:
            logger.info(f"  - {name_reason}")
    else:
        logger.info("所有角色均成功处理或无跳过项。")

if __name__ == "__main__":
    main()
