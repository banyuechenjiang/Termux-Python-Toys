# 版本号: v_NewDesign_Wikitext_Unified{Part-3-json2yaml.py}
import json
import logging
import os
import re
import html
import yaml # 需要安装 PyYAML: pip install PyYAML

# --- 配置与常量 ---
INPUT_JSON_FILE = "food_details_with_wikitext.json"
BASE_OUTPUT_DIR = "./提瓦特美食"
LOG_FILE = "part3_json2yaml.log"

# Wikitext模板和字段名
FOOD_TEMPLATE_NAME = "食物图鉴新"
KEY_NAME_WIKI = "名称"
KEY_CATEGORY_WIKI = "分类" # 注意: B站Wiki模板中为“分类”，非“类别”
KEY_TYPE_WIKI = "类型"
KEY_OBTAIN_WIKI = "获取方式"
KEY_DESC_WIKI = "介绍"
KEY_DESC_PERFECT_WIKI = "完美介绍"
KEY_DESC_FAIL_WIKI = "失败介绍"
KEY_DESC_STRANGE_WIKI = "奇怪料理介绍" # 别名
KEY_DESC_DELICIOUS_WIKI = "美味料理介绍" # 别名
KEY_RECIPE_OBTAIN_WIKI = "食谱获取方式"
KEY_SPECIAL_CHAR_WIKI = "特殊料理对应角色"

# 食物分类常量
CATEGORY_CHAR_SPECIAL = "角色特殊料理"
CATEGORY_STORE_BOUGHT = "商店购买品"
CATEGORY_RECIPE_COOKED = "菜谱料理"
CATEGORY_OTHER = "其他料理"

# --- 日志配置 ---
if os.path.exists(LOG_FILE):
    try:
        os.remove(LOG_FILE)
    except OSError as e:
        print(f"删除旧日志文件 {LOG_FILE} 时出错: {e}")

logger = logging.getLogger(__name__)
logger.handlers = []
logger.setLevel(logging.INFO)
log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s")

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

# --- Wikitext 解析与清理辅助函数 ---

def find_template_content(wikitext, template_name):
    """
    从wikitext中找到指定模板的完整内容块，并返回其内部参数字符串。
    能处理模板名后直接跟参数或换行后跟参数的情况。
    例如 {{template_name | param1=value1 ... }}
    返回 " | param1=value1 ... "
    """
    if not wikitext or not template_name:
        return None
    
    # 正则表达式查找模板开始标签，忽略大小写
    # \s* 匹配模板名和第一个管道符之间的任何空白字符，包括换行符
    start_tag_regex = r"\{\{\s*" + re.escape(template_name) + r"\s*"
    match = re.search(start_tag_regex, wikitext, re.IGNORECASE)
    
    if not match:
        # logger.debug(f"模板 '{template_name}' 未在wikitext中找到起始标签。")
        return None

    # 模板内容的实际开始位置是匹配结束后
    content_start_pos = match.end()
    
    level = 1  # 我们已经匹配了 {{template_name，所以层级从1开始计算模板自身的 }}
    search_pos = content_start_pos
    
    # 寻找与模板起始 {{ 匹配的结束 }}
    # 需要正确处理嵌套的 {{ 和 }}
    # 注意：这里的实现假设模板内容从 content_start_pos 开始，直到匹配的 }}
    
    # 修正：level应该从 {{template_name 匹配到的 {{ 开始算起
    # 假设 start_tag_regex 匹配了 {{template_name，那么我们从这里开始计数
    # 实际上，我们应该从模板名之后开始扫描，并寻找对应的闭合 }}
    
    # 重新定位到模板的起始 {{
    template_block_start_index = -1
    # 我们需要找到 {{template_name 整体的起始位置，以便正确计算嵌套
    # re.search(r"\{\{\s*" + re.escape(template_name), wikitext, re.IGNORECASE) 已经帮我们定位了
    # match.start() 是 {{ 的位置

    open_brace_index = match.start() # 这是 {{ 的开始
    
    # 从模板名之后开始扫描，寻找参数部分的结束
    # 我们需要找到 {{template_name ... }} 中的 ... 部分
    
    brace_level = 0 
    # brace_level for {{ and }} within the parameters string
    # The main {{ of the template itself is handled by finding its corresponding }}

    # Let's find the end of the template block by counting braces from its beginning
    # The true start of the template block is match.start()
    
    idx = match.start() # Start of "{{"
    
    # Find the content start (after template name)
    # The content we want to parse for params is *inside* the main template braces
    # e.g. for {{TPL |k=v}}, we want "|k=v"
    
    # First, find the end of the entire {{TemplateName ... }} block
    block_scan_start = idx + 2 # After the first "{{"
    current_level = 1 
    block_end_pos = -1

    for i in range(block_scan_start, len(wikitext) -1):
        if wikitext[i:i+2] == '{{':
            current_level += 1
            i += 1 # Skip next char
        elif wikitext[i:i+2] == '}}':
            current_level -= 1
            if current_level == 0:
                block_end_pos = i # Position of the first '}' of the closing '}}'
                break
            i += 1 # Skip next char
    
    if block_end_pos == -1:
        logger.warning(f"无法找到模板 '{template_name}' 的匹配结束 '}}'。")
        return None

    # The content for parameter parsing is between template_name and block_end_pos
    # Example: {{ TPLNAME | p1=v1 }}
    # match.end() is after TPLNAME (and any space)
    # block_end_pos is at the first '}' of the final '}}'
    
    # The string containing parameters is from where template name ends to where '}}' begins
    params_str = wikitext[match.end():block_end_pos]
    return params_str.strip()


def parse_template_params(params_str):
    """
    从模板参数字符串中解析键值对。
    例如："|名称=苹果|介绍=一种水果"
    返回：{'名称': '苹果', '介绍': '一种水果'}
    """
    params = {}
    if not params_str:
        return params

    # 正则表达式匹配 "| key = value" 对
    # value 可以包含换行和各种字符，直到下一个 "| key =" 或字符串末尾
    # (?=\s*\|[^=]+=|\Z) ensures that the value capture stops before the next parameter or end of string.
    # [^=]+? non-greedy match for key
    # (?:.|\n)*? or .*? with re.DOTALL for value
    matches = re.finditer(r"\|\s*([^=]+?)\s*=\s*(.*?)(?=\s*\|\s*[^=]+=|\Z)", params_str, re.DOTALL | re.UNICODE)
    for match in matches:
        key = match.group(1).strip()
        value = match.group(2).strip()
        params[key] = value
    return params

def clean_wikitext_value(text, permissive=False):
    """清理wikitext值，移除标记、模板、处理HTML实体等。"""
    if text is None:
        return "" # Return empty string for None to avoid issues later

    text = str(text) # Ensure text is a string

    # 1. HTML实体解码 (尽早处理，避免影响正则)
    text = html.unescape(text)

    if permissive:
        return text.strip()

    # 2. 移除HTML注释 (Part2已做，但以防万一)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    # 3. 处理特定Wiki模板
    # {{Ruby|基础字|注音}} -> 基础字
    text = re.sub(r"\{\{Ruby\|([^|]+?)\|[^}]+?\}\}", r"\1", text, flags=re.IGNORECASE)
    # {{Color|颜色|文本}} -> 文本
    text = re.sub(r"\{\{Color\|[^|]+?\|([^}]+?)\}\}", r"\1", text, flags=re.IGNORECASE)
    # {{黑幕|文本}} -> 文本 (或其他类似简单包裹模板)
    text = re.sub(r"\{\{黑幕\|([^}]+?)\}\}", r"\1", text, flags=re.IGNORECASE)
    # 移除 {{tl|模板名}} -> 模板名 (或其他类似显示模板名的模板)
    text = re.sub(r"\{\{tl\|([^}]+?)\}\}", r"\1", text, flags=re.IGNORECASE)
    # 移除文件/图片链接: [[File:...]], [[Image:...]], [[文件:...]], [[图片:...]]
    text = re.sub(r"\[\[(?:File|Image|文件|图片):[^\]]+\]\]", "", text, flags=re.IGNORECASE)

    # 4. 处理Wiki链接
    # [[目标页面|显示文本]] -> 显示文本
    text = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+?)\]\]", r"\1", text)

    # 5. 处理HTML标签
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE) # <br> 转为换行符
    text = re.sub(r"<[^>]+>", "", text) # 移除其他所有HTML标签

    # 6. 规范化空白字符
    text = re.sub(r"[ \t]+", " ", text)  #多个空格/制表符变单个空格
    text = re.sub(r"\s*\n\s*", "\n", text) #移除换行符周围的空格
    text = re.sub(r"\n{2,}", "\n", text) #多个换行符变单个

    return text.strip()

def get_param_value(params, primary_key, aliases=None, permissive_clean=False):
    """从解析的参数中获取值，并进行清理，支持别名。"""
    val = params.get(primary_key)
    if val is None and aliases:
        for alias in aliases:
            val = params.get(alias)
            if val is not None:
                break
    return clean_wikitext_value(val, permissive=permissive_clean)

# --- 分类与数据构建函数 ---

def categorize_food(params, food_item_json_name):
    """根据Wikitext参数和JSON信息对食物进行分类。"""
    # 优先判断是否为食物 (是否有食物图鉴模板在主逻辑中处理)
    
    # 1. 角色特殊料理
    # Wikitext |类型= 含 "角色特殊料理" 或 "角色技能获取"。
    # Wikitext |获取方式= 指向角色天赋。
    # Wikitext |特殊料理对应角色= 有值
    char_name = params.get(KEY_SPECIAL_CHAR_WIKI, "").strip()
    food_type = params.get(KEY_TYPE_WIKI, "").strip()
    obtain_method = params.get(KEY_OBTAIN_WIKI, "").strip()

    if char_name: # 有特殊料理对应角色字段，基本确定是角色特殊料理
        logger.debug(f"食物 '{food_item_json_name}' 通过 KEY_SPECIAL_CHAR_WIKI ('{char_name}') 分类为: {CATEGORY_CHAR_SPECIAL}")
        return CATEGORY_CHAR_SPECIAL
    if "角色特殊料理" in food_type or "角色技能获取" in food_type:
        logger.debug(f"食物 '{food_item_json_name}' 通过 TYPE_WIKI ('{food_type}') 分类为: {CATEGORY_CHAR_SPECIAL}")
        return CATEGORY_CHAR_SPECIAL
    # 获取方式可能包含角色名，如 "[[角色名]]固有天赋"
    if ("天赋" in obtain_method or "固有能力" in obtain_method) and \
       ("角色" in food_type or "特殊" in food_type or re.search(r"\[\[.*?\]\]", obtain_method)): # 包含角色链接
        logger.debug(f"食物 '{food_item_json_name}' 通过 OBTAIN_WIKI ('{obtain_method}') 和 TYPE_WIKI ('{food_type}') 分类为: {CATEGORY_CHAR_SPECIAL}")
        return CATEGORY_CHAR_SPECIAL

    # 2. 商店购买品
    # Wikitext |分类= (注意是“分类”不是“类别”) 字段包含 "不可制作"。
    # 辅助: |获取方式= 通常为NPC购买；|类型= 通常非 "正常料理"。
    category_field = params.get(KEY_CATEGORY_WIKI, "").strip() # B站Wiki模板用的是“分类”
    if "不可制作" in category_field:
        logger.debug(f"食物 '{food_item_json_name}' 通过 CATEGORY_WIKI ('{category_field}') 分类为: {CATEGORY_STORE_BOUGHT}")
        return CATEGORY_STORE_BOUGHT
    if "购买" in obtain_method and not any(s in obtain_method for s in ["烹饪", "合成", "制作"]):
        # 进一步确认不是活动商店兑换等可制作物品
        if "商店" in obtain_method or "杂货铺" in obtain_method or "餐馆" in obtain_method:
             logger.debug(f"食物 '{food_item_json_name}' 通过 OBTAIN_WIKI ('{obtain_method}') 分类为: {CATEGORY_STORE_BOUGHT}")
             return CATEGORY_STORE_BOUGHT


    # 3. 菜谱料理
    # Wikitext |类型= 为 "正常料理"。
    # Wikitext |获取方式= 为 "烹饪获得" 或 "合成获得"。
    # Wikitext |分类= 不应含 "不可制作" (此条件已被商店购买品优先处理)。
    if "正常料理" in food_type and \
       ("烹饪获得" in obtain_method or "合成获得" in obtain_method or "制作获得" in obtain_method or \
        KEY_RECIPE_OBTAIN_WIKI in params and params[KEY_RECIPE_OBTAIN_WIKI].strip()): # 有食谱获取方式也算
        logger.debug(f"食物 '{food_item_json_name}' 通过 TYPE_WIKI 和 OBTAIN_WIKI/RECIPE_OBTAIN_WIKI 分类为: {CATEGORY_RECIPE_COOKED}")
        return CATEGORY_RECIPE_COOKED
    
    # 4. 其他料理
    logger.debug(f"食物 '{food_item_json_name}' 未匹配特定分类，归为: {CATEGORY_OTHER}")
    return CATEGORY_OTHER


def build_food_description_yaml(params, category, food_name_for_log):
    """构建料理介绍部分的YAML结构。"""
    # 商店购买品和部分其他料理可能使用宽松清理的单描述
    use_permissive_clean_for_main_desc = category == CATEGORY_STORE_BOUGHT or \
                                         (category == CATEGORY_OTHER and not params.get(KEY_DESC_PERFECT_WIKI) and not params.get(KEY_DESC_FAIL_WIKI))


    # 尝试获取所有品质的描述
    desc_strange = get_param_value(params, KEY_DESC_FAIL_WIKI, [KEY_DESC_STRANGE_WIKI])
    # 普通描述：商店购买品和部分其他料理可能需要宽松清理
    desc_normal = get_param_value(params, KEY_DESC_WIKI, permissive_clean=use_permissive_clean_for_main_desc)
    desc_delicious = get_param_value(params, KEY_DESC_PERFECT_WIKI, [KEY_DESC_DELICIOUS_WIKI])

    is_multi_quality = bool(desc_strange or desc_delicious) # 如果有差或美味，则认为是多品质

    if category == CATEGORY_RECIPE_COOKED or is_multi_quality: # 菜谱料理总是多品质结构，其他类型若有差/美味也按多品质
        # 多品质 (菜谱料理或明确有多种品质描述的)
        # 即使某个品质描述为空，也保留键（如果用户需求是这样）。但题目要求空值键删除。
        # 所以，我们只添加有内容的描述。
        multi_desc_data = {}
        if desc_strange:
            multi_desc_data["差"] = desc_strange
        if desc_normal: # 普通描述始终要有，除非它本身为空
            multi_desc_data["普通"] = desc_normal
        else: # 如果普通描述为空，但又是多品质，则显式置为空字符串或按需处理
            if is_multi_quality: # 确保在多品质结构中，即使普通描述为空，也考虑是否要有个占位
                 pass # 当前逻辑：如果普通描述清理后为空，就不加入multi_desc_data

        if desc_delicious:
            multi_desc_data["美味"] = desc_delicious
        
        if multi_desc_data: # 只有当至少有一个品质的描述时才返回字典
            return multi_desc_data
        elif desc_normal: # 如果多品质描述都为空，但普通描述存在（非多品质场景），则返回普通描述
             return desc_normal
        else:
            return None # 所有描述都为空

    elif desc_normal: # 单描述 (特殊料理/商店购买品/其他)
        return desc_normal
    else: # 没有提取到任何描述
        logger.debug(f"食物 '{food_name_for_log}' 未能提取到任何料理介绍。")
        return None

def sanitize_filename(name):
    """清理文件名中的非法字符。"""
    # 移除路径分隔符和Windows文件名禁用字符
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    # 移除控制字符
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    # 替换连续下划线
    name = re.sub(r"__+", "_", name)
    # 确保文件名不会太长 (可选)
    # max_len = 100 
    # if len(name) > max_len: name = name[:max_len]
    return name.strip()

# --- 主处理逻辑 ---
def main():
    if not os.path.exists(BASE_OUTPUT_DIR):
        os.makedirs(BASE_OUTPUT_DIR)
        logger.info(f"已创建基础输出目录: {BASE_OUTPUT_DIR}")

    try:
        with open(INPUT_JSON_FILE, "r", encoding="utf-8") as f:
            all_food_data = json.load(f)
    except FileNotFoundError:
        logger.error(f"输入文件 {INPUT_JSON_FILE} 未找到。")
        return
    except json.JSONDecodeError as e:
        logger.error(f"解析输入文件 {INPUT_JSON_FILE} JSON失败: {e}")
        return

    processed_count = 0
    skipped_non_food = 0
    category_counts = {
        CATEGORY_CHAR_SPECIAL: 0,
        CATEGORY_STORE_BOUGHT: 0,
        CATEGORY_RECIPE_COOKED: 0,
        CATEGORY_OTHER: 0,
    }

    for food_item in all_food_data:
        food_name = food_item.get("name", "未知食物")
        wikitext = food_item.get("wikitext")

        if not wikitext:
            logger.warning(f"食物 '{food_name}' 的wikitext为空，跳过处理。")
            skipped_non_food +=1
            continue

        template_content_str = find_template_content(wikitext, FOOD_TEMPLATE_NAME)

        if not template_content_str:
            logger.warning(f"食物 '{food_name}' 未找到 '{FOOD_TEMPLATE_NAME}' 模板，可能非标准食物条目，跳过。")
            skipped_non_food += 1
            continue
        
        params = parse_template_params(template_content_str)
        if not params:
            logger.warning(f"食物 '{food_name}' 的 '{FOOD_TEMPLATE_NAME}' 模板参数解析为空，跳过。")
            skipped_non_food += 1
            continue

        # 从Wikitext的 |名称= 字段获取名称，如果不存在，则用JSON中的name
        wikitext_food_name = clean_wikitext_value(params.get(KEY_NAME_WIKI, food_name)).strip()
        if not wikitext_food_name: # 如果清理后为空，还是用JSON的
             wikitext_food_name = food_name
        
        # 更新日志中使用的食物名称为wikitext中的名称（如果可用）
        current_food_name_for_log = wikitext_food_name if wikitext_food_name else food_name


        # 分类
        category = categorize_food(params, current_food_name_for_log)
        category_counts[category] += 1

        # 构建YAML数据
        yaml_data_payload = {} # 这是实际写入YAML文件的数据，不包含顶层食物名键

        # 食材
        ingredients = food_item.get("ingredients")
        if ingredients: # 确保食材列表不为空
            yaml_data_payload["食材"] = ingredients
        
        # 料理介绍
        description_yaml_obj = build_food_description_yaml(params, category, current_food_name_for_log)
        if description_yaml_obj: # 确保介绍不为空 (None, empty str, empty dict)
            if isinstance(description_yaml_obj, dict) and not description_yaml_obj: # 空字典
                pass
            elif isinstance(description_yaml_obj, str) and not description_yaml_obj.strip(): # 空字符串
                pass
            else:
                yaml_data_payload["料理介绍"] = description_yaml_obj
        
        # 如果没有任何可输出的内容（除了食物名称本身），可以选择是否生成文件
        # 当前逻辑：即使payload为空，也会生成以食物名为key的空YAML内容
        # FoodName: {}

        # 准备输出
        category_dir = os.path.join(BASE_OUTPUT_DIR, category)
        if not os.path.exists(category_dir):
            os.makedirs(category_dir)
            logger.info(f"已创建分类目录: {category_dir}")

        # YAML文件名使用清理后的wikitext食物名称
        yaml_filename = sanitize_filename(wikitext_food_name) + ".yaml"
        yaml_filepath = os.path.join(category_dir, yaml_filename)

        # 最终YAML结构：顶层键是食物名
        final_yaml_output = {wikitext_food_name: yaml_data_payload}

        try:
            with open(yaml_filepath, "w", encoding="utf-8") as yf:
                yaml.dump(final_yaml_output, yf, allow_unicode=True, sort_keys=False, Dumper=yaml.SafeDumper, indent=2)
            logger.info(f"已保存 [{category}] {wikitext_food_name} 到 {yaml_filepath}")
            processed_count += 1
        except Exception as e:
            logger.error(f"写入YAML文件 {yaml_filepath} 失败: {e}")

    logger.info("--- 处理完成 ---")
    logger.info(f"总共处理食物条目数 (来自JSON): {len(all_food_data)}")
    logger.info(f"成功生成YAML文件数: {processed_count}")
    logger.info(f"因无Wikitext或食物模板跳过数: {skipped_non_food}")
    logger.info("各分类统计:")
    for cat, count in category_counts.items():
        logger.info(f"  {cat}: {count}")

if __name__ == "__main__":
    main()
