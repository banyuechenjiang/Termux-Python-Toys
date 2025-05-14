# 版本号: v_NewDesign_Wikitext_Unified{Part-2-Url-Complete-获取列表完整信息.py}
import requests
from bs4 import BeautifulSoup, Comment
import json
import logging
from fake_useragent import UserAgent
import requests_cache
from time import sleep
import os
import sqlite3
from datetime import datetime
import re

# --- 配置与常量 ---
LOG_FILE = "food_crawler_unified.log"
OUTPUT_JSON_FILE = "food_details_with_wikitext.json" # 通用文件名

BASE_URL = "https://wiki.biligame.com"

# 一级缓存: 存储原始编辑页Response对象 (由requests-cache管理)
RAW_EDIT_PAGES_CACHE_NAME = "raw_edit_pages_cache.sqlite" # 通用名

# 二级持久化: 存储处理后的、已清理注释的纯Wikitext字符串
PROCESSED_WIKITEXT_DB_FILE = "processed_wikitext_storage.sqlite" # 通用名

#Part-1-Food_url列表获取.py生成所需文件
INPUT_JSON_FILE = "food_data_simplified.json"



# --- 日志配置 ---
if os.path.exists(LOG_FILE):
    try:
        os.remove(LOG_FILE)
        print(f"已删除旧日志文件: {LOG_FILE}")
    except OSError as e:
        print(f"删除旧日志文件 {LOG_FILE} 时出错: {e}")

logger = logging.getLogger()
logger.handlers = [] # 清除已有处理器，避免重复日志
logger.setLevel(logging.INFO)
log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

# --- SQLite Wikitext存储辅助函数 ---
def init_wikitext_db():
    conn = sqlite3.connect(PROCESSED_WIKITEXT_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wikitext_cache (
        url_key TEXT PRIMARY KEY,
        wikitext TEXT,
        timestamp DATETIME
    )
    """)
    conn.commit()
    conn.close()
    logger.info(f"Wikitext存储数据库 {PROCESSED_WIKITEXT_DB_FILE} 初始化/已存在。")

def get_wikitext_from_db(url_key):
    conn = sqlite3.connect(PROCESSED_WIKITEXT_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT wikitext FROM wikitext_cache WHERE url_key = ?", (url_key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def save_wikitext_to_db(url_key, wikitext):
    conn = sqlite3.connect(PROCESSED_WIKITEXT_DB_FILE)
    cursor = conn.cursor()
    try:
        # 确保wikitext是字符串，即使是None也转换为空字符串存入，或根据需求处理
        wikitext_to_save = wikitext if wikitext is not None else ""
        cursor.execute("""
        INSERT OR REPLACE INTO wikitext_cache (url_key, wikitext, timestamp)
        VALUES (?, ?, ?)
        """, (url_key, wikitext_to_save, datetime.now()))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"保存Wikitext到数据库时出错 for key {url_key}: {e}")
        return False
    finally:
        conn.close()

# --- HTML处理与Wikitext提取辅助函数 ---
def fetch_original_edit_page(url, session, item_name_for_log=""):
    ua = UserAgent()
    headers = {"User-Agent": ua.random}
    log_prefix = f"[{item_name_for_log}] " if item_name_for_log else ""
    try:
        response = session.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        if not response.from_cache:
            logger.info(f"{log_prefix}OK (服务器下载)")
            sleep(1.2) # 只在实际下载时休眠
        return response
    except requests.exceptions.RequestException as e:
        logger.error(f"{log_prefix}获取原始编辑页时出错: {e}")
        return None

def remove_html_comments(text_content):
    """从任何文本内容中移除 <!-- ... --> 风格的注释。"""
    if text_content is None:
        return None
    return re.sub(r'<!--.*?-->', '', text_content, flags=re.DOTALL)

def extract_and_clean_wikitext_from_html(html_content, item_name_for_log=""):
    log_prefix = f"[{item_name_for_log}] " if item_name_for_log else ""
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, 'lxml')
    textarea_tag = soup.find('textarea', id='wpTextbox1')

    if not textarea_tag:
        logger.warning(f"{log_prefix}未在HTML中找到 <textarea id='wpTextbox1'>。")
        return None

    raw_wikitext = textarea_tag.get_text(strip=False)
    
    # 在提取后立即清理HTML注释
    cleaned_wikitext = remove_html_comments(raw_wikitext)
    
    if raw_wikitext and cleaned_wikitext is None: # Defensive check
        logger.error(f"{log_prefix}原始Wikitext存在，但注释清理后结果为None，这不应该发生。")
        return raw_wikitext # Fallback to raw if cleaning fails unexpectedly

    if raw_wikitext and len(cleaned_wikitext) < len(raw_wikitext):
        logger.info(f"{log_prefix}已提取Wikitext并清理了HTML注释。")
    elif raw_wikitext and '<!--' in raw_wikitext : # 如果有注释但没清理掉
         logger.warning(f"{log_prefix}Wikitext中检测到注释，但清理后长度未变。请检查remove_html_comments逻辑。")
    else:
        logger.debug(f"{log_prefix}已提取Wikitext，未发现HTML注释。")
        
    return cleaned_wikitext


# --- 主处理逻辑 ---
def process_single_food_item(food_item, raw_page_session):
    name = food_item.get("name", "未知食物")
    detail_url = food_item.get("detail_url")
    log_prefix = f"[{name}] "

    if not detail_url:
        logger.warning(f"{log_prefix}条目缺少 detail_url。")
        return None, "Missing detail_url"

    try:
        page_title = detail_url.split("/")[-1]
        if not page_title: page_title = detail_url.split("/")[-2]
        edit_page_url = f"{BASE_URL}/ys/index.php?title={page_title}&action=edit"
    except IndexError:
        logger.error(f"{log_prefix}从 detail_url ({detail_url}) 提取页面标题失败。")
        return None, "Failed to parse detail_url for edit page URL"

    # 1. 检查二级Wikitext缓存
    cached_wikitext = get_wikitext_from_db(edit_page_url)
    if cached_wikitext is not None:
        # logger.info(f"{log_prefix}Wikitext已在二级缓存中。") # 减少日志的冗余
        return cached_wikitext, None

    # 2. 如果未缓存，获取原始编辑页（通过一级缓存）
    original_response = fetch_original_edit_page(edit_page_url, raw_page_session, item_name_for_log=name)
    if not original_response:
        return None, f"Failed to fetch original edit page: {edit_page_url}"

    try:
        # 优先使用 headers 中的 encoding，其次是 apparent_encoding，最后是 utf-8
        encoding_to_try = original_response.encoding or original_response.apparent_encoding or 'utf-8'
        html_text = original_response.content.decode(encoding_to_try, errors='replace')
    except Exception as e:
        logger.error(f"{log_prefix}解码原始编辑页HTML时出错: {e}")
        return None, f"Decoding error for original HTML: {str(e)}"

    # 3. 提取并清理Wikitext
    wikitext = extract_and_clean_wikitext_from_html(html_text, item_name_for_log=name)

    if wikitext is None: # 这包含了提取失败和清理后变None（理论上不应发生）的情况
        logger.warning(f"{log_prefix}未能从页面提取或清理Wikitext。")
        return None, "Failed to extract or clean wikitext from HTML"

    # 4. 将Wikitext存入二级缓存
    if save_wikitext_to_db(edit_page_url, wikitext): # wikitext 已经是清理过的
        # logger.info(f"{log_prefix}已提取、清理Wikitext并存入二级缓存。长度: {len(wikitext)}") # 移到进度条后打印
        pass
    else:
        logger.warning(f"{log_prefix}提取、清理Wikitext后，存入二级缓存失败。")
        # 即使存储失败，也返回提取到的wikitext
    return wikitext, None


def main():
    init_wikitext_db()

    food_data_list = []
    try:
        with open(INPUT_JSON_FILE, "r", encoding="utf-8") as f:
            food_data_list = json.load(f)
    except FileNotFoundError:
        logger.error(f"错误: 输入文件 {INPUT_JSON_FILE} 未找到。")
        return
    except json.JSONDecodeError:
        logger.error(f"错误: 输入文件 {INPUT_JSON_FILE} JSON格式无效。")
        return

    try:
        total_items = len(food_data_list)
        logger.info(f"需要处理的总食物条目数量: {total_items}")
        newly_processed_wikitext_count = 0
        all_output_data = []

        with requests_cache.CachedSession(RAW_EDIT_PAGES_CACHE_NAME, backend="sqlite") as raw_page_session:
            logger.info(f"原始编辑页缓存数据库 (一级缓存): {raw_page_session.cache.db_path}")

            for index, food_item in enumerate(food_data_list):
                current_index = index + 1
                name = food_item.get("name", f"未知条目ID_{index}")
                log_prefix_main = f"[{name}] "
                
                progress_bar_width = 30
                filled_len = int(progress_bar_width * current_index // total_items)
                bar = '█' * filled_len + '-' * (progress_bar_width - filled_len)
                # 确保进度条和后续可能的日志在同一行开始或正确换行
                print(f"\r处理进度: |{bar}| {current_index}/{total_items} ({name})", end="")

                is_newly_processed_flag = get_wikitext_from_db(
                     f"{BASE_URL}/ys/index.php?title={food_item.get('detail_url','').split('/')[-1]}&action=edit"
                ) is None

                wikitext, error_message = process_single_food_item(food_item, raw_page_session)
                
                output_item = {**food_item}

                if wikitext is not None:
                    output_item["wikitext"] = wikitext
                    if is_newly_processed_flag:
                        newly_processed_wikitext_count += 1
                        # 只有新处理的才打印成功信息，避免重复日志刷屏
                        print() # 换行以便清晰显示下面的日志
                        logger.info(f"{log_prefix_main}已成功提取、清理Wikitext并存入二级缓存。长度: {len(wikitext)}")

                    if error_message:
                        if not is_newly_processed_flag: print() # 确保错误信息不覆盖进度条
                        logger.warning(f"{log_prefix_main}(Wikitext获取成功但有备注): {error_message}")
                else:
                    output_item["wikitext"] = None
                    output_item["error"] = error_message or "Unknown error during processing"
                    if not is_newly_processed_flag or current_index == 1 or (current_index > 1 and filled_len > int(progress_bar_width * (current_index -1) // total_items)):
                         print() # 换行以显示错误日志
                    logger.error(f"{log_prefix_main}处理失败: {error_message or 'Unknown error'}")
                
                all_output_data.append(output_item)
            
            print() # 结束进度条后换行

            logger.info(f"所有食物条目处理循环完毕。")
            logger.info(f"总计条目: {total_items}")
            logger.info(f"本次运行从原始页面新提取/处理的Wikitext数量: {newly_processed_wikitext_count}")
            
            conn_count = sqlite3.connect(PROCESSED_WIKITEXT_DB_FILE)
            cursor_count = conn_count.cursor()
            cursor_count.execute("SELECT COUNT(*) FROM wikitext_cache")
            total_in_wikitext_db = cursor_count.fetchone()[0]
            conn_count.close()
            logger.info(f"Wikitext存储数据库 {PROCESSED_WIKITEXT_DB_FILE} 中总条目数: {total_in_wikitext_db}")

            if all_output_data:
                with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as f:
                    json.dump(all_output_data, f, ensure_ascii=False, indent=4)
                logger.info(f"已保存 {len(all_output_data)} 条数据到 {OUTPUT_JSON_FILE}")
            else:
                logger.warning("没有数据可供输出，未生成JSON文件。")

    except Exception as e:
        logger.exception(f"主函数发生严重异常: {e}")
    finally:
        logger.info("脚本执行完毕。")

if __name__ == "__main__":
    main()
