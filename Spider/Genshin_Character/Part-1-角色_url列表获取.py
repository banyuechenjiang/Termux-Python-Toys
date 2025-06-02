# 版本号: v_NewDesign_Wikitext_Unified{Part-1-角色_url列表获取_NoCache.py}
import requests
from bs4 import BeautifulSoup
import json
import logging
from fake_useragent import UserAgent
import os

# --- 配置与常量 ---
LOG_FILE = "character_crawler_nocache.log" # 日志文件名更新
OUTPUT_JSON_FILE = "character_data.json" # 输出JSON文件名保持不变

BASE_URL = "https://wiki.biligame.com" # 基础URL
CHARACTER_LIST_URL = "https://wiki.biligame.com/ys/%E8%A7%92%E8%89%B2" # 角色列表URL

# --- 日志配置 ---
if os.path.exists(LOG_FILE):
    try:
        os.remove(LOG_FILE)
    except OSError as e:
        print(f"删除旧日志文件 {LOG_FILE} 时出错: {e}")

logger = logging.getLogger(__name__)
logger.handlers = []
logger.setLevel(logging.INFO)
log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)


# --- 请求函数 (移除了session缓存) ---
def fetch_page(url, session): # session 参数仍然保留，以便使用requests.Session()管理cookies等
    """获取页面内容（无持久化缓存，使用会话管理）"""
    ua = UserAgent()
    headers = {"User-Agent": ua.random}
    try:
        response = session.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        logger.info(f"从服务器获取: {url}") # 因为没有缓存，总是从服务器获取
        return response.text
    except requests.exceptions.Timeout:
        logger.error(f"获取页面 {url} 时超时。")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"获取页面 {url} 时发生HTTP错误: {e.response.status_code} - {e.response.reason}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"获取页面 {url} 时发生请求错误: {e}")
        return None

# --- 数据提取函数 (与之前版本相同) ---
def extract_character_data(html_content):
    """从角色列表页面HTML内容中提取角色数据"""
    if not html_content:
        logger.warning("HTML内容为空，无法提取角色数据。")
        return []
        
    soup = BeautifulSoup(html_content, "lxml")
    character_data = []
    
    character_blocks = soup.select('div.divsort')
    logger.info(f"找到 {len(character_blocks)} 个潜在的角色信息块。")
    
    for idx, block in enumerate(character_blocks):
        links_with_title = block.select('a[title]')
        
        found_character_link_in_block = False
        for link_tag in links_with_title:
            href_value = link_tag.get('href', '').strip()
            title_attr = link_tag.get('title', '').strip()
            tag_classes = link_tag.get('class', [])

            if not href_value or not title_attr:
                continue
            if 'image' in tag_classes:
                continue
            if '/文件:' in href_value or '/File:' in href_value:
                continue
            
            img_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
            if href_value.lower().endswith(img_extensions):
                continue

            name = title_attr
            detail_url = ""
            
            if href_value.startswith('http'):
                detail_url = href_value
            elif href_value.startswith('/'):
                detail_url = BASE_URL + href_value
            else:
                logger.warning(f"角色 '{name}' 的URL '{href_value}' 格式不标准，跳过。")
                continue
            
            character_item = {
                "name": name,
                "detail_url": detail_url
            }
            
            if character_item not in character_data:
                 character_data.append(character_item)
                 logger.debug(f"提取成功: 角色='{name}', URL='{detail_url}'")
            
            found_character_link_in_block = True
            break 
            
        if not found_character_link_in_block:
            block_name_guess_tag = block.select_one('div.L')
            block_name_for_log = block_name_guess_tag.text.strip() if block_name_guess_tag else f"块索引 {idx}"
            logger.debug(f"在角色块 '{block_name_for_log}' 中未找到符合所有条件的角色链接。")

    if not character_data:
        logger.warning("最终未能从页面提取到任何角色数据。")
    else:
        logger.info(f"成功提取 {len(character_data)} 条角色数据。")
        
    return character_data

# --- 主函数 (移除了requests-cache的初始化) ---
def main():
    try:
        # 使用普通的 requests.Session()
        with requests.Session() as session:
            logger.info(f"使用 requests.Session() 进行网络请求，无持久化缓存。")
            
            character_list_html = fetch_page(CHARACTER_LIST_URL, session)

            if character_list_html:
                all_character_data = extract_character_data(character_list_html)

                if not all_character_data:
                    logger.warning(f"{OUTPUT_JSON_FILE} 将为空，因为没有提取到角色数据。")
                    with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
                        json.dump([], f, ensure_ascii=False, indent=4)
                    logger.info(f"已创建空的 {OUTPUT_JSON_FILE}。")
                else:
                    with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
                        json.dump(all_character_data, f, ensure_ascii=False, indent=4)
                    logger.info(f"已保存 {len(all_character_data)} 条角色数据到 {OUTPUT_JSON_FILE}")
            else:
                logger.error(f"未能获取角色列表页面内容 ({CHARACTER_LIST_URL})，无法继续处理。")

    except Exception as e:
        logger.exception(f"主函数执行过程中发生未处理的异常: {e}")

if __name__ == "__main__":
    main()