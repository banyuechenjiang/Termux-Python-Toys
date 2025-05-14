#Part-1-Food_url列表获取.py
import requests
from bs4 import BeautifulSoup
import json
import logging
from fake_useragent import UserAgent
import requests_cache

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("food_crawler_simplified.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# 使用 requests-cache 创建持久化缓存
requests_cache.install_cache('food_cache_simplified', backend='sqlite')

BASE_URL = "https://wiki.biligame.com"
FOOD_LIST_URL = "https://wiki.biligame.com/ys/%E9%A3%9F%E7%89%A9%E4%B8%80%E8%A7%88"

def fetch_page(url, session):
    """获取页面内容（带缓存和伪装）"""
    ua = UserAgent()
    headers = {"User-Agent": ua.random}
    try:
        response = session.get(url, headers=headers)
        response.raise_for_status()
        if response.from_cache:
            logging.info(f"从缓存中加载: {url}")
        else:
            logging.info(f"从服务器获取: {url}")
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"获取页面 {url} 时出错: {e}")
        return None

def extract_food_data(html):
    """从食品列表页面提取食品数据"""
    soup = BeautifulSoup(html, "lxml")
    food_data = []

    # 找到所有的食物条目行（排除表头）
    for row in soup.select('tr[data-param1]'):
        try:
            # 名称和详情页 URL
            name_link = row.select_one('td:nth-of-type(2) > a')
            name = name_link.get('title').strip() if name_link else None
            detail_url = BASE_URL + name_link.get('href').strip() if name_link else None

            # 地区（在食材前面一个 td）
            region_td = row.select_one('td:nth-last-of-type(2)')
            region = region_td.text.strip() if region_td else None

            # 食材
            ingredients = []
            for ingredient_div in row.select('td:last-of-type > div.cailiaoxiao'):
                ingredient_link = ingredient_div.select_one('a')
                ingredient_count_div = ingredient_div.select_one('div')

                if ingredient_link and ingredient_count_div:
                    ingredient_name = ingredient_link.get('title').strip()
                    count = ingredient_count_div.text.strip()
                    ingredients.append(f"{ingredient_name}*{count}")

            if name and detail_url:
                food_item = {
                    "name": name,
                    "detail_url": detail_url,
                    "region": region,
                    "ingredients": ingredients,
                }
                food_data.append(food_item)
                logging.debug(f"已提取: {name}")
            else:
                logging.warning(f"食品名称或详情页 URL 缺失，跳过此条目")

        except (AttributeError, KeyError) as e:
            logging.error(f"解析食品信息时出错: {e}")
            logging.error(f"出错的行: {row}")
            continue

    return food_data

def main():
    try:
        with requests_cache.CachedSession('food_cache_simplified') as session:
            logging.info(f"缓存数据库路径: {session.cache.db_path}")
            food_list_html = fetch_page(FOOD_LIST_URL, session)

            if food_list_html:
                all_food_data = extract_food_data(food_list_html)

                if not all_food_data:
                    logging.warning("all_food_data 为空，没有数据可写入")
                else:
                    with open("food_data_simplified.json", "w", encoding="utf-8") as f:
                        json.dump(all_food_data, f, ensure_ascii=False, indent=4)
                    logging.info(f"已保存 {len(all_food_data)} 条食品数据到 food_data_simplified.json")

    except Exception as e:
        logging.exception(f"主函数发生异常: {e}")

if __name__ == "__main__":
    main()
