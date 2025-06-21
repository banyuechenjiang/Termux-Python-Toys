import time
import random
import re
import sys
from urllib.parse import urlencode
from datetime import timedelta
import requests
import yaml
import hashlib
import math
import json

CONFIG_YAML_CONTENT = """
User_Cookie:
  - "你的B站cookie"
  
Priority_Ups:
  - id: "476491780"
    name: "SechiAnimation"
  - id: "3493265644980448"
    name: "碧蓝档案"
  - id: "3494361637587456"
    name: "麻雀糖-BA同人短漫"
Appoint_Up:
  - id: "210232"
    name: "瑶山百灵"
  - id: "87031209"
    name: "r–note&槐南茶馆"
  - id: "165906284"
    name: "森羅万象【shinra-bansho】"
  - id: "3493078251866300"
    name: "AliceInCradle官方"
PlayMode_Settings:
  up_selection_strategy: "random_subset"
  num_ups_for_random_subset: 3
  videos_per_up_play_mode: 3
  max_play_duration_local_wait: 120
Manga_Task:
  Enabled: true
  Read_Target:
    comic_id: "27355"
    ep_id: "381662"
    title: "堀与宫村"
Watch_Task_Settings:
  Wait_Time_Min: 3
  Wait_Time_Max: 28
Coin_Task_Settings:
  min_coin_for_putting: 200
"""

class GlobalConstants:
    # BILI_API_BASE_URL - B站API基础URL
    BABU = "https://api.bilibili.com/x/"
    # MANGA_API_BASE_URL_TWIRP - B站漫画Twirp API基础URL
    MABUT = "https://manga.bilibili.com/twirp/"
    # DEFAULT_USER_AGENT  - 默认用户代理
    DUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    # DEFAULT_HEADERS- 默认请求头
    DH = {"Referer": "https://www.bilibili.com/", "Accept-Language": "zh-CN,zh;q=0.9"}
    # MANGA_HEADERS- 漫画API请求头
    MH = {
        "User-Agent": DUA,
        "Origin": "https://manga.bilibili.com", "Referer": "https://manga.bilibili.com/",
        "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }

class WbiManager:
    MIXIN_KEY_ENC_TAB = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
        33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
        61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
        36, 20, 34, 44, 52
    ]
    def __init__(self):
        self.img_key = None; self.sub_key = None
        self.html_session_for_wbi = requests.Session()
        self.html_session_for_wbi.headers.update({"User-Agent": GlobalConstants.DUA, **GlobalConstants.DH})
    def _get_wbi_keys_internal(self, cookies_for_nav_api):
        nav_url = f"{GlobalConstants.BABU}web-interface/nav"
        try:
            resp = self.html_session_for_wbi.get(nav_url, cookies=cookies_for_nav_api, timeout=10)
            resp.raise_for_status(); json_data = resp.json()
            if json_data.get("code") == 0:
                wbi_img = json_data.get("data", {}).get("wbi_img", {})
                img_url, sub_url = wbi_img.get("img_url", ""), wbi_img.get("sub_url", "")
                if img_url and sub_url:
                    self.img_key = img_url.split('/')[-1].split('.')[0]
                    self.sub_key = sub_url.split('/')[-1].split('.')[0]; return True
        except: pass
        print("WBI密钥获取失败.")
        return False
    def _refresh_wbi_keys_internal(self, cookies_for_nav_api): return self._get_wbi_keys_internal(cookies_for_nav_api)
    def get_mixin_key(self, orig_key: str): return ''.join([orig_key[i] for i in self.MIXIN_KEY_ENC_TAB])[:32]
    def encode_wbi_params(self, params: dict, cookies_for_nav_api: dict):
        if not self.img_key or not self.sub_key:
            if not self._refresh_wbi_keys_internal(cookies_for_nav_api): print("WBI密钥不可用,无法签名."); return params
        mixin_key = self.get_mixin_key(self.img_key + self.sub_key)
        curr_time = round(time.time())
        signed_params = params.copy(); signed_params['wts'] = curr_time
        signed_params = dict(sorted(signed_params.items()))
        query = urlencode(signed_params)
        hl = hashlib.md5(); hl.update(f"{query}{mixin_key}".encode('utf-8'))
        signed_params['w_rid'] = hl.hexdigest()
        return signed_params

class ConfigManager:
    def __init__(self, yaml_content_str):
        self.raw_config_data = self._parse_config_from_string(yaml_content_str)
        self.user_config = self._process_user_config(self.raw_config_data)
    def _parse_config_from_string(self, content_str):
        try:
            config_data = yaml.safe_load(content_str)
            if not config_data or "User_Cookie" not in config_data or \
               not isinstance(config_data["User_Cookie"], list) or \
               not config_data["User_Cookie"] or not config_data["User_Cookie"][0]:
                print("配置User_Cookie无效或缺失."); sys.exit(1)
            return config_data
        except Exception as e: print(f"配置解析错误: {e}"); sys.exit(1)
    def _handle_single_cookie_str(self, cookie_str: str) -> dict:
        if not cookie_str or not isinstance(cookie_str, str): return {}
        return {p.split("=", 1)[0].strip(): p.split("=", 1)[1].strip() for p in cookie_str.split(";") if "=" in p}
    def _parse_up_list(self, raw_list: list) -> list:
        if not isinstance(raw_list, list): return []
        return [{'id': str(item['id']).strip(), 'name': item.get('name', '').strip()}
                for item in raw_list if isinstance(item, dict) and 'id' in item and str(item['id']).strip().isdigit()]
    def _process_user_config(self, raw_config_data: dict) -> dict:
        user_conf = {}
        parsed_cookie = self._handle_single_cookie_str(raw_config_data["User_Cookie"][0])
        if not parsed_cookie: print("Cookie解析失败."); sys.exit(1)
        user_conf['Cookie'] = parsed_cookie
        user_conf['Appoint_Up'] = self._parse_up_list(raw_config_data.get('Appoint_Up', []))
        raw_manga_config = raw_config_data.get('Manga_Task', {})
        processed_manga_config = {'Enabled': raw_manga_config.get('Enabled', False) == True, 'Read_Target': {}}
        if isinstance(raw_manga_config.get('Read_Target'), dict):
            rt_conf = raw_manga_config['Read_Target']
            comic_id, ep_id = str(rt_conf.get('comic_id', '')).strip(), str(rt_conf.get('ep_id', '')).strip()
            title = str(rt_conf.get('title', '')).strip()
            if comic_id.isdigit() and ep_id.isdigit():
                processed_manga_config['Read_Target'] = {'comic_id': comic_id, 'ep_id': ep_id, 'title': title or f"漫画ID {comic_id}"}
        user_conf['Manga_Task'] = processed_manga_config
        raw_play_mode_settings = raw_config_data.get('PlayMode_Settings', {})
        user_conf['PlayMode_Settings'] = {
            'up_selection_strategy': raw_play_mode_settings.get('up_selection_strategy', 'all'),
            'num_ups_for_random_subset': int(raw_play_mode_settings.get('num_ups_for_random_subset', 3)),
            'videos_per_up_play_mode': int(raw_play_mode_settings.get('videos_per_up_play_mode', 3)),
            'max_play_duration_local_wait': int(raw_play_mode_settings.get('max_play_duration_local_wait', 120))
        }
        raw_watch_task_settings = raw_config_data.get('Watch_Task_Settings', {})
        user_conf['Watch_Task_Settings'] = {
            'Wait_Time_Min': int(raw_watch_task_settings.get('Wait_Time_Min', 3)),
            'Wait_Time_Max': int(raw_watch_task_settings.get('Wait_Time_Max', 28))
        }
        raw_coin_task_settings = raw_config_data.get('Coin_Task_Settings', {})
        user_conf['Coin_Task_Settings'] = {
            'min_coin_for_putting': int(raw_coin_task_settings.get('min_coin_for_putting', 200)),
            'Priority_Ups': self._parse_up_list(raw_config_data.get('Priority_Ups', []))
        }
        return user_conf
    def get_config(self): return self.user_config

class BiliRequest:
    def __init__(self):
        self.html_session = requests.Session()
        self.default_headers = {"User-Agent": GlobalConstants.DUA, **GlobalConstants.DH}
        self.wbi_manager = WbiManager()
    def get(self, url: str, cookies: dict, params:dict=None, needs_wbi:bool=False, **kwargs) -> requests.Response | None:
        headers_to_use = {**self.default_headers, **kwargs.pop('headers', {})}
        current_params = params.copy() if params else {}
        if needs_wbi:
            current_params = self.wbi_manager.encode_wbi_params(current_params, cookies)
            if 'w_rid' not in current_params: return None
        full_url = f"{url}?{urlencode(current_params)}" if current_params else url
        try:
            res = self.html_session.get(url=full_url, headers=headers_to_use, cookies=cookies, timeout=10, **kwargs)
            res.raise_for_status(); return res
        except requests.exceptions.RequestException as e: print(f"GET失败 {url}: {e}"); return None
    def post(self, url: str, cookies: dict, params: dict = None, post_data: dict = None, needs_wbi: bool = False, **kwargs) -> requests.Response | None:
        headers_to_use = {**self.default_headers, **kwargs.pop('headers', {})}
        current_params = params.copy() if params else {}
        if needs_wbi:
            current_params = self.wbi_manager.encode_wbi_params(current_params, cookies)
            if 'w_rid' not in current_params: return None
        final_url = f"{url}?{urlencode(current_params)}" if current_params else url
        try:
            res = self.html_session.post(url=final_url, headers=headers_to_use, cookies=cookies, data=post_data, timeout=15, **kwargs)
            res.raise_for_status(); return res
        except requests.exceptions.RequestException as e: print(f"POST失败 {url}: {e}"); return None

class UserHandler:
    def __init__(self, request_handler: BiliRequest):
        self.request_handler = request_handler
        self.urls = {
            "UUD": f"{GlobalConstants.BABU}space/myinfo",
            "UDRS": f"{GlobalConstants.BABU}member/web/exp/reward"
        }
    def get_user_data(self, cookie: dict) -> tuple[str, int, int, int, int, bool, bool, int]:
        default_return = ("未知", 0, 0, 0, 0, True, False, 0)
        if not cookie: print("Cookie为空."); return default_return
        response = self.request_handler.get(self.urls['UUD'], cookie)
        if not response: return default_return
        try:
            res_json = response.json()
            if res_json.get('code') == -101: print("Cookie错误或失效"); return default_return
            if res_json.get('code') != 0: print(f"用户信息API失败: {res_json.get('message')}"); return default_return
            d = res_json.get('data', {})
            name=d.get('name','未知用户'); mid=d.get('mid',0); level=d.get('level',0)
            coins_raw=d.get('coins',0); coins=int(float(coins_raw)) if str(coins_raw).replace('.','',1).isdigit() else 0
            exp=d.get('level_exp',{}).get('current_exp',0); is_lv6 = level >= 6
            next_exp_val = d.get('level_exp',{}).get('next_exp', -1)
            exp_needed = max(0, int(next_exp_val) - exp) if next_exp_val != -1 and not is_lv6 else 0
            return name, mid, level, exp, coins, is_lv6, True, exp_needed
        except Exception as e: print(f"用户信息响应错误: {e}"); return default_return
    def print_user_data_nicely(self, name, mid, level, exp, coins, is_lv6, exp_needed):
        print(f"用户名: {name}\nUID: {mid}\n当前等级: LV {level}\n当前硬币: {coins} 个\n当前经验: {exp}")
        if not is_lv6:
            next_exp_numeric = exp + exp_needed
            if next_exp_numeric > exp :
                 print(f"下级所需: {next_exp_numeric}\n仍需经验: {exp_needed}")
        elif level >=6 : print("用户已达最高等级 (LV6+).")
    def get_daily_reward_status(self, cookie: dict) -> dict:
        default_status = {'login':False,'watch':False,'share':False,'coins_exp':0,'total_exp_today':0}
        if not cookie: return default_status
        response = self.request_handler.get(self.urls['UDRS'], cookie)
        if response and response.json().get('code') == 0:
            data = response.json().get('data', {})
            status = {k:data.get(k,False) for k in ['login','watch','share']}
            status['coins_exp'] = data.get('coins',0)
            status['total_exp_today'] = sum(5 for k in ['login','watch','share'] if status[k]) + status['coins_exp']
            return status
        print(f"每日奖励状态获取失败: {response.json().get('message','无API消息') if response else '请求错误'}")
        return default_status
    def print_daily_reward_status_nicely(self, reward_status: dict):
        print(f"登录: {'是' if reward_status.get('login') else '否'} (+5 Exp)")
        print(f"观看: {'是' if reward_status.get('watch') else '否'} (+5 Exp)")
        print(f"分享: {'是' if reward_status.get('share') else '否'} (+5 Exp)")
        print(f"投币Exp: {reward_status.get('coins_exp',0)}/50 Exp")
        print(f"总任务Exp: {reward_status.get('total_exp_today',0)}/65 Exp")

class DailyTasksHandler:
    def __init__(self, request_handler: BiliRequest):
        self.request_handler = request_handler
        self.urls = {
            "USV": f"{GlobalConstants.BABU}web-interface/share/add",
            "UWV": f"{GlobalConstants.BABU}click-interface/web/heartbeat",
            "UPC": f"{GlobalConstants.BABU}web-interface/coin/add",
            "UAR": f"{GlobalConstants.BABU}web-interface/archive/relation",
            "USAS": f"{GlobalConstants.BABU}space/wbi/arc/search",
            "USAI": f"{GlobalConstants.BABU}space/acc/info",
            "UVVI": f"{GlobalConstants.BABU}web-interface/view"
        }
        self._up_name_cache = {}
    def _get_up_name_by_mid(self, mid: str, cookie: dict) -> str | None:
        if mid in self._up_name_cache: return self._up_name_cache[mid]
        resp = self.request_handler.get(self.urls['USAI'], cookie, params={'mid': mid})
        if resp and resp.json().get('code') == 0: self._up_name_cache[mid] = resp.json()['data']['name']; return self._up_name_cache[mid]
        return None
    def _check_video_coin_status(self, cookie: dict, aid: str) -> int:
        resp = self.request_handler.get(self.urls['UAR'], cookie, params={'aid': aid})
        return resp.json()['data'].get('coin', 0) if resp and resp.json().get('code') == 0 else -1
    def get_video_details_from_view_api(self, aid_or_bvid: str, cookie: dict, id_type:str = "aid") -> dict | None:
        params = {id_type: aid_or_bvid}
        response = self.request_handler.get(self.urls['UVVI'], cookie, params=params)
        if response and response.json().get('code') == 0:
            data = response.json().get('data', {})
            return {'title': data.get('title', '未知标题'), 'duration': data.get('duration', 0),
                    'desc': data.get('desc', ''), 'pic_url': data.get('pic', ''),
                    'aid': str(data.get('aid')), 'bvid': data.get('bvid','')}
        return None
    def get_videos_from_up_list(self, cookie: dict, up_list_to_fetch_from: list, for_coin_task: bool = False, videos_per_up_target: int = 3, needed_for_coin_task: int = 5) -> list:
        if not up_list_to_fetch_from:
            if not for_coin_task: print("UP主列表为空.")
            return []
        if not self.request_handler.wbi_manager.img_key or not self.request_handler.wbi_manager.sub_key:
             self.request_handler.wbi_manager._refresh_wbi_keys_internal(cookie)
        collected_videos_for_current_up = []
        up_conf = up_list_to_fetch_from[0]
        mid = up_conf.get('id')
        if not mid: return []
        name = up_conf.get('name') or self._get_up_name_by_mid(mid, cookie) or f"MID:{mid}"
        if for_coin_task:
            pages_to_try = [2, 1]
            max_videos_per_page = 50
            for page_num in pages_to_try:
                if len(collected_videos_for_current_up) >= needed_for_coin_task: break
                params_search = {'mid': mid, 'pn': page_num, 'ps': max_videos_per_page, 'order':'pubdate','dm_img_list':'[]','dm_cover_img_str':'V2ViRmlsRTMyNw=='}
                resp = self.request_handler.get(self.urls['USAS'], cookie, params=params_search, needs_wbi=True)
                if not resp or resp.json().get('code') != 0:
                    if page_num == 2 and pages_to_try == [2,1]: continue
                    break
                vlist = resp.json().get('data',{}).get('list',{}).get('vlist',[])
                if not vlist:
                    if page_num == 1: break
                    else: continue
                for v_data in vlist:
                    if len(collected_videos_for_current_up) >= needed_for_coin_task: break
                    if 'aid' in v_data and self._check_video_coin_status(cookie, str(v_data['aid'])) == 0:
                        video_entry = {'aid': str(v_data['aid']), 'title': v_data.get('title', '?'), 'mid': mid, 'pubdate': v_data.get('created', 0)}
                        if video_entry['aid'] not in {v['aid'] for v in collected_videos_for_current_up}:
                            collected_videos_for_current_up.append(video_entry)
                if page_num != pages_to_try[-1] and len(collected_videos_for_current_up) < needed_for_coin_task:
                    time.sleep(random.uniform(0.3, 0.8))
        else:
            params_search = {'mid': mid, 'pn': 1, 'ps': videos_per_up_target, 'order':'pubdate','dm_img_list':'[]','dm_cover_img_str':'V2ViRmlsRTMyNw=='}
            resp = self.request_handler.get(self.urls['USAS'], cookie, params=params_search, needs_wbi=True)
            if resp and resp.json().get('code') == 0:
                vlist = resp.json().get('data',{}).get('list',{}).get('vlist',[])
                for v_data in vlist:
                    if 'aid' in v_data: collected_videos_for_current_up.append({'aid': str(v_data['aid']), 'title': v_data.get('title', '?'), 'mid': mid, 'pubdate': v_data.get('created', 0)})
        return collected_videos_for_current_up
    def share_video(self, cookie: dict, video_list: list) -> bool:
        print("\n#视频分享任务#")
        if not video_list: print("无视频可分享."); return True
        v = random.choice(video_list); aid, title, csrf = v['aid'], v['title'], cookie.get('bili_jct', '')
        if not csrf: print("分享失败:缺bili_jct"); return False
        print(f"分享视频 '{title}' (AID:{aid})")
        resp = self.request_handler.post(self.urls['USV'], cookie, post_data={"aid": aid, "csrf": csrf})
        if resp and resp.json().get('code') == 0: print(f"分享 '{title}' 完成 🥳"); time.sleep(random.randint(3,7)); return True
        elif resp and resp.json().get('code') == 71000: print(f"'{title}' 今日已分享过 😫"); return True
        else: print(f"分享失败 '{title}': {resp.json().get('message', '无API消息') if resp else '请求错误'}"); return False
    def watch_video(self, cookie: dict, video_list: list, min_wait: int, max_wait: int) -> bool:
        print("\n#观看视频任务#")
        if not video_list: print("无视频可观看."); return True
        v_raw = random.choice(video_list); aid, title_raw = v_raw['aid'], v_raw['title']
        v_details = self.get_video_details_from_view_api(aid, cookie)
        title = title_raw; actual_duration_sec = 0
        if v_details: title = v_details['title']; actual_duration_sec = v_details['duration']
        local_wait_time = random.randint(min_wait, max_wait); report_time = local_wait_time
        if actual_duration_sec > 0: report_time = min(local_wait_time, actual_duration_sec)
        print(f"观看: '{title}' (AID:{aid}), 上报/等待时长:{report_time}s")
        time.sleep(report_time)
        data = {"aid": aid, "played_time": report_time, "csrf": cookie.get('bili_jct', '')}
        resp = self.request_handler.post(self.urls['UWV'], cookie, post_data=data)
        if resp and resp.json().get('code') == 0: print(f"上报成功: '{title}' 🥳"); time.sleep(random.randint(3,7)); return True
        else: print(f"上报失败 '{title}': {resp.json().get('message', '无API消息') if resp else '请求错误'}"); return False
    def coin_videos(self, cookie: dict, appoint_up_list: list, coins_bal: int, coins_exp: int, coin_task_settings: dict) -> bool:
        print("\n#视频投币任务#")
        min_coin_for_putting = coin_task_settings.get('min_coin_for_putting', 200)
        if coins_bal < min_coin_for_putting: print(f"硬币({coins_bal})不足{min_coin_for_putting}."); return True
        if coins_exp >= 50: print("投币经验已满(50)."); return True
        csrf = cookie.get('bili_jct', '')
        ops_needed = min(math.ceil((50 - coins_exp) / 10), 5, int(coins_bal))
        if not csrf or ops_needed <= 0: print("无需投币或缺bili_jct."); return True
        print(f"目标投币次数: {ops_needed} (当前投币Exp:{coins_exp}/50)")
        thrown_count = 0
        video_candidate_pool = []
        up_source_pools = [
            (random.sample(coin_task_settings.get('Priority_Ups', []), len(coin_task_settings.get('Priority_Ups', []))), "优先UP"),
            (random.sample(appoint_up_list, len(appoint_up_list)), "指定UP")
        ]
        for up_pool_config, source_name in up_source_pools:
            if thrown_count >= ops_needed: break
            current_up_pool = list(up_pool_config)
            while current_up_pool:
                if thrown_count >= ops_needed: break
                up_to_fetch = current_up_pool.pop(0)
                needed_now = ops_needed - thrown_count + 1
                print(f"\n尝试从`{source_name}` '{up_to_fetch.get('name', up_to_fetch.get('id'))}' 获取最多 {needed_now} 个可投币视频...")
                new_videos = self.get_videos_from_up_list(cookie, [up_to_fetch], for_coin_task=True, needed_for_coin_task=needed_now)
                if new_videos:
                    new_videos.sort(key=lambda v: v.get('pubdate', float('inf')))
                    for vid_entry in new_videos:
                        if vid_entry['aid'] not in {v['aid'] for v in video_candidate_pool}:
                            video_candidate_pool.append(vid_entry)
                    print(f"  从 '{up_to_fetch.get('name')}' 获取到 {len(new_videos)} 个新视频，当前总候选池 {len(video_candidate_pool)} 个。")
                while video_candidate_pool and thrown_count < ops_needed and coins_bal >=1:
                    v = video_candidate_pool.pop(0)
                    aid, title = v['aid'], v['title']
                    print(f"向 '{title}' (av{aid}) 投1币并点赞...")
                    resp = self.request_handler.post(self.urls['UPC'], cookie, post_data={'aid':aid,'multiply':1,'select_like':1,'cross_domain':'true','csrf':csrf})
                    if resp and resp.json().get('code') == 0:
                        print(f"投币成功: '{title}' 💿"); thrown_count+=1; coins_bal-=1
                        time.sleep(random.randint(7,15))
                    else:
                        msg = resp.json().get('message', '无API消息') if resp else '请求错误'
                        print(f"投币异常 '{title}': {msg}")
        if thrown_count < ops_needed and not video_candidate_pool:
            print("\n所有配置的UP主均已检查完毕，未能完成所有目标投币。")
        print(f"\n本轮投币任务结束，共投出 {thrown_count} 枚硬币。")
        return True

class MangaTaskHandler:
    def __init__(self, request_handler: BiliRequest, manga_config: dict):
        self.urls={
            "UMCI": f"{GlobalConstants.MABUT}activity.v1.Activity/ClockIn",
            "UMAH": f"{GlobalConstants.MABUT}bookshelf.v1.Bookshelf/AddHistory"
        }
    def _handle_manga_post(self, url: str, cookie: dict, post_data: dict, task_name: str, title: str) -> bool:
        csrf_token = cookie.get('bili_jct')
        if not csrf_token:
            print(f"漫画{task_name}失败: 缺少bili_jct (csrf_token)"); return False
        data_with_csrf = {**post_data, "csrf": csrf_token, "platform":"android"}
        resp = self.request_handler.post(url, cookie, post_data=data_with_csrf, headers=GlobalConstants.MH)
        if not resp:
            print(f"漫画{task_name}请求失败: 无响应对象."); return False
        try:
            res_json=resp.json(); code=res_json.get('code')
            if code == 0:
                print(f"漫画{task_name} '{title}' 成功 🥳"); return True
            msg = res_json.get('msg', res_json.get('message', 'N/A')).lower()
            if task_name == "签到" and ("cannot clockin repeatedly" in msg or "已签到" in msg or "不能重复签到" in msg or code == 1):
                print(f"漫画今日已签到过 😊 (API Code: {code}, Msg: \"{res_json.get('msg')}\")"); return True
            print(f"漫画{task_name}失败 '{title}': Code {code}, Msg: \"{res_json.get('message', res_json.get('msg'))}\""); return False
        except requests.exceptions.JSONDecodeError: print(f"漫画{task_name}响应错误: 无法解析JSON - {resp.text[:100]}"); return False
        except Exception as e: print(f"漫画{task_name}响应处理异常: {e}"); return False
    def perform_clock_in(self, cookie: dict) -> bool:
        print("\n#漫画签到#")
        if not self.manga_config.get("Enabled",False): print("漫画任务未启用."); return True
        return self._handle_manga_post(self.urls['UMCI'], cookie, {}, "签到", "每日签到")
    def perform_manga_read(self, cookie: dict) -> bool:
        print("\n#漫画阅读#")
        if not self.manga_config.get("Enabled",False): print("漫画任务未启用."); return True
        rt=self.manga_config.get("Read_Target")
        if not rt or not rt.get('comic_id') or not rt.get('ep_id'):
            print("漫画阅读目标配置不完整."); return True
        comic_id, ep_id, title = rt['comic_id'], rt['ep_id'], rt['title']
        print(f"阅读漫画 '{title}' (Comic ID: {comic_id}, Episode ID: {ep_id})")
        return self._handle_manga_post(self.urls['UMAH'], cookie, {'comic_id':comic_id,'ep_id':ep_id}, "阅读", title)

class AutomatedTasksExecutor:
    def __init__(self, config_all: dict, user_handler: UserHandler, daily_tasks_handler: DailyTasksHandler, manga_task_handler: MangaTaskHandler):
        self.config = config_all
        self.user_cookie = self.config['Cookie']
        self.appoint_up_list = self.config.get('Appoint_Up',[])
        self.play_mode_settings = self.config.get('PlayMode_Settings', {})
        self.watch_task_settings = self.config.get('Watch_Task_Settings', {})
        self.coin_task_settings = self.config.get('Coin_Task_Settings', {})
        self.user_handler = user_handler
        self.daily_tasks_handler = daily_tasks_handler
        self.manga_task_handler = manga_task_handler
    def execute_tasks(self, current_user_data_dict: dict, initial_reward_status: dict) -> dict:
        reward_status_current = initial_reward_status.copy()
        is_lv6 = current_user_data_dict.get('is_lv6', True)
        user_coins = current_user_data_dict.get('coins', 0)
        print("\n--- 开始执行日常任务 (自动化模式) ---")
        if is_lv6:
            print("用户已满级LV6, 无需执行经验任务."); return reward_status_current
        print("\n#漫画任务处理#")
        if reward_status_current.get('total_exp_today', 0) < 65:
            if self.manga_task_handler.manga_config.get("Enabled", False):
                self.manga_task_handler.perform_clock_in(self.user_cookie)
                self.manga_task_handler.perform_manga_read(self.user_cookie)
                reward_status_current = self.user_handler.get_daily_reward_status(self.user_cookie)
            else: print("漫画任务未在配置中启用。")
        else:
            print("每日总经验已达上限(65), 跳过漫画任务.")
        if reward_status_current.get('total_exp_today', 0) >= 65:
            print("每日总经验已达上限(65)，后续视频经验任务将不再执行。")
        else:
            videos_for_watch_share = []
            if not reward_status_current.get('watch', False) or not reward_status_current.get('share', False):
                combined_up_list_raw = self.appoint_up_list + self.coin_task_settings.get('Priority_Ups', [])
                up_pool_for_tasks = list({up['id']: up for up in combined_up_list_raw}.values())
                if up_pool_for_tasks:
                    random_up_for_tasks = random.choice(up_pool_for_tasks)
                    videos_to_get = self.play_mode_settings.get('videos_per_up_play_mode', 1)
                    print(f"\n为观看/分享任务，从UP '{random_up_for_tasks.get('name', random_up_for_tasks.get('id'))}' 获取 {videos_to_get} 个视频...")
                    videos_for_watch_share = self.daily_tasks_handler.get_videos_from_up_list(self.user_cookie, [random_up_for_tasks], for_coin_task=False, videos_per_up_target=videos_to_get)
                    if not videos_for_watch_share: print("未能获取到用于观看/分享的视频。")
                else: print("无配置的UP主用于获取观看/分享视频。")
            if not reward_status_current.get('watch', False):
                if videos_for_watch_share:
                    min_w, max_w = self.watch_task_settings.get('Wait_Time_Min', 3), self.watch_task_settings.get('Wait_Time_Max', 28)
                    if self.daily_tasks_handler.watch_video(self.user_cookie, videos_for_watch_share, min_w, max_w):
                        reward_status_current = self.user_handler.get_daily_reward_status(self.user_cookie)
                else: print("\n#观看视频任务#\n无视频可观看，跳过。")
            if reward_status_current.get('total_exp_today', 0) < 65 and not reward_status_current.get('share', False):
                if videos_for_watch_share:
                    if self.daily_tasks_handler.share_video(self.user_cookie, videos_for_watch_share):
                        reward_status_current = self.user_handler.get_daily_reward_status(self.user_cookie)
                else: print("\n#视频分享任务#\n无视频可分享，跳过。")
            if reward_status_current.get('total_exp_today', 0) < 65 and reward_status_current.get('coins_exp', 0) < 50 :
                self.daily_tasks_handler.coin_videos(self.user_cookie, self.appoint_up_list, user_coins, reward_status_current.get('coins_exp', 0), self.coin_task_settings)
                reward_status_current = self.user_handler.get_daily_reward_status(self.user_cookie)
        print("\n--- 所有日常任务尝试完毕 (自动化模式) ---")
        return self.user_handler.get_daily_reward_status(self.user_cookie)

class VideoToolsModule:
    def __init__(self, config_all: dict, bili_request: BiliRequest, daily_tasks_handler: DailyTasksHandler, user_handler: UserHandler):
        self.config = config_all; self.user_cookie = self.config['Cookie']
        self.play_mode_settings = self.config.get('PlayMode_Settings', {})
        self.appoint_up_list = self.config.get('Appoint_Up', [])
        self.priority_ups_list = self.config.get('Coin_Task_Settings', {}).get('Priority_Ups', [])
        self.bili_request = bili_request; self.daily_tasks_handler = daily_tasks_handler; self.user_handler = user_handler
    def _get_user_action_parser(self) -> str:
        while True:
            prompt = "\n选择视频工具操作:\n[1] 解析视频播放上报\n[2] 解析视频封面URL\n[0] 返回主菜单 : "
            action = input(prompt).strip()
            if action in ['0', '1', '2']: return action
            print("无效输入。")
    def _extract_video_id_from_url(self, video_url: str) -> tuple[str | None, str | None]:
        aid_match = re.search(r"(?:av|aid(?:=|%3D))(\d+)", video_url, re.IGNORECASE)
        bvid_match = re.search(r"(BV[a-zA-Z0-9]+)", video_url, re.IGNORECASE)
        return (aid_match.group(1) if aid_match else None, bvid_match.group(1) if bvid_match else None)
    def _handle_cover_url_parsing(self):
        print("\n--- 解析视频封面URL ---")
        video_url = input("请输入B站视频的完整URL: ").strip()
        if not video_url: print("未输入URL。"); return
        aid, bvid = self._extract_video_id_from_url(video_url)
        id_to_use, type_of_id = (bvid, "bvid") if bvid else (aid, "aid")
        if not id_to_use: print("未能从URL中解析出有效视频ID。"); return
        video_details = self.daily_tasks_handler.get_video_details_from_view_api(id_to_use, self.user_cookie, id_type=type_of_id)
        if video_details and video_details.get('pic_url'):
            print(f"\n视频《{video_details['title']}》的封面URL:\n{video_details['pic_url']}")
        else: print(f"获取视频详情或封面URL失败。")
    def _get_videos_for_play_mode(self) -> list:
        print("\n#获取播放模式视频列表#")
        combined_list_raw = self.appoint_up_list + self.priority_ups_list
        up_list_full = list({up['id']: up for up in combined_list_raw}.values())
        selected_up_list = up_list_full
        strategy = self.play_mode_settings.get('up_selection_strategy', 'all')
        if strategy == "random_subset" and up_list_full:
            num_to_select = min(self.play_mode_settings.get('num_ups_for_random_subset', 1), len(up_list_full))
            if num_to_select > 0: selected_up_list = random.sample(up_list_full, num_to_select)
        if not selected_up_list: print("无UP主可选。"); return []
        videos_per_up = self.play_mode_settings.get('videos_per_up_play_mode', 3)
        all_videos = []
        for up in selected_up_list:
             new_vids = self.daily_tasks_handler.get_videos_from_up_list(self.user_cookie, [up], for_coin_task=False, videos_per_up_target=videos_per_up)
             if new_vids:
                 print(f"  从UP '{up.get('name', up.get('id'))}' 获取到 {len(new_vids)} 个视频。")
                 all_videos.extend(new_vids)
        unique_videos = list({v['aid']:v for v in all_videos}.values())
        print(f"共获取到 {len(unique_videos)} 个视频用于播放。")
        return unique_videos
    def _handle_play_mode_reporting(self):
        print("\n--- 解析视频播放上报 ---")
        video_list_raw = self._get_videos_for_play_mode()
        if not video_list_raw: print("无视频可播放。"); return
        chosen_video_raw = random.choice(video_list_raw); aid_str = chosen_video_raw['aid']
        video_details = self.daily_tasks_handler.get_video_details_from_view_api(aid_str, self.user_cookie)
        if not video_details: print(f"无法获取视频 {aid_str} 的详细信息。"); return
        title, duration_sec, desc = video_details['title'], video_details['duration'], video_details['desc']
        print(f"播放: '{title}' (AID:{aid_str})\n实际时长: {str(timedelta(seconds=duration_sec)) if duration_sec > 0 else '未知'}")
        max_local_wait = self.play_mode_settings.get('max_play_duration_local_wait', 120)
        report_duration = random.randint(15, 60) if duration_sec <= 0 else min(int(duration_sec * random.uniform(0.6, 1.0)), duration_sec)
        local_wait_target = max(1, min(report_duration, max_local_wait))
        print(f"\n计划模拟播放上限: {local_wait_target}s\n按 Ctrl+C 可中断模拟播放")
        elapsed_play_time = 0
        try:
            for i in range(local_wait_target, 0, -1):
                print(f"\r模拟播放: '{title}'. 剩余 {i} 秒...", end=""); time.sleep(1); elapsed_play_time += 1
            print("\n模拟播放计时完成.")
        except KeyboardInterrupt: print("\n模拟播放被中断.")
        if elapsed_play_time == 0: print("未模拟有效播放时长，不上报。"); return
        if input(f"已模拟播放 {elapsed_play_time}s. [1]上报, [任意键]不上报: ").strip() == '1':
            data = {"aid": aid_str, "played_time": elapsed_play_time, "csrf": self.user_cookie.get('bili_jct', '')}
            resp = self.bili_request.post(self.daily_tasks_handler.urls['UWV'], self.user_cookie, post_data=data)
            if resp and resp.json().get('code') == 0: print(f"上报成功: '{title}' (时长:{elapsed_play_time}s) 🥳")
            else: print(f"上报失败: '{title}' - {resp.json().get('message') if resp else '请求失败'}")
        else: print("用户选择不上报。")
    def run(self):
        print("\n" + "#"*15 + " B站视频工具模块 " + "#"*15)
        name, uid, *_ = self.user_handler.get_user_data(self.user_cookie)
        if uid == 0: print("无法获取用户信息，视频工具模块可能无法正常运行。"); return
        print(f"当前用户: {name} (UID:{uid})")
        print("-" * 45)
        while True:
            try:
                action = self._get_user_action_parser()
                if action == '1': self._handle_play_mode_reporting()
                elif action == '2': self._handle_cover_url_parsing()
                elif action == '0': break
                print("\n" + "="*20 + " 操作完成，返回主菜单 " + "="*20); time.sleep(1)
            except KeyboardInterrupt: print("\n当前视频工具操作被用户中断."); break
            except Exception as e: print(f"\n视频工具操作执行中发生异常: {e}"); import traceback; traceback.print_exc(); break

class MainApplication:
    def __init__(self):
        self.config_manager = ConfigManager(CONFIG_YAML_CONTENT)
        self.config = self.config_manager.get_config()
        self.bili_request = BiliRequest()
        self.user_handler = UserHandler(self.bili_request)
        self.daily_tasks_handler = DailyTasksHandler(self.bili_request)
        self.manga_task_handler = MangaTaskHandler(self.bili_request, self.config.get('Manga_Task', {}))
        self.automated_tasks_executor = AutomatedTasksExecutor(self.config, self.user_handler, self.daily_tasks_handler, self.manga_task_handler)
        self.video_tools_module = VideoToolsModule(self.config, self.bili_request, self.daily_tasks_handler, self.user_handler)
    def _display_user_and_task_status(self):
        print("\n" + "-" * 20 + " 当前状态 " + "-" * 20)
        name, mid, level, exp, coins, is_lv6, success, exp_needed = self.user_handler.get_user_data(self.config['Cookie'])
        if success: self.user_handler.print_user_data_nicely(name, mid, level, exp, coins, is_lv6, exp_needed)
        else: print("获取用户信息失败。")
        reward_status = self.user_handler.get_daily_reward_status(self.config['Cookie'])
        print("\n--- 每日任务状态 ---")
        self.user_handler.print_daily_reward_status_nicely(reward_status)
        print("-" * (40 + len(" 当前状态 ")))
        return {'name': name, 'uid': mid, 'level': level, 'exp': exp, 'coins': coins, 'is_lv6': is_lv6, 'exp_needed': exp_needed}, reward_status
    def _display_main_menu_and_get_choice(self):
        prompt = "\n选择功能:\n[1] 执行B站日常任务\n[2] 使用B站视频工具\n[0] 退出程序\n请输入选项: "
        while True:
            choice = input(prompt).strip()
            if choice in ['0', '1', '2']: return choice
            print("无效输入，请重新选择。")
    def run_interactive(self):
        print("\n" + "#"*20 + " B站助手已启动 (交互模式) " + "#"*20)
        try:
            while True:
                current_user_info_dict, current_reward_status_dict = self._display_user_and_task_status()
                choice = self._display_main_menu_and_get_choice()
                if choice == '1':
                    self.automated_tasks_executor.execute_tasks(current_user_info_dict, current_reward_status_dict)
                elif choice == '2':
                    self.video_tools_module.run()
                elif choice == '0':
                    print("\n用户选择退出。"); break
                print("\n" + "="*20 + " 操作完成，返回主菜单 " + "="*20); time.sleep(1)
        except KeyboardInterrupt: print("\n交互模式被用户中断 (Ctrl+C)。")
        except Exception as e: print(f"\n交互模式发生未捕获异常: {e}"); import traceback; traceback.print_exc()
    def run_automated(self):
        print("\n" + "#"*20 + " B站助手已启动 (自动模式) " + "#"*20)
        name, mid, level, exp, coins, is_lv6, success, exp_needed = self.user_handler.get_user_data(self.config['Cookie'])
        if success: self.user_handler.print_user_data_nicely(name, mid, level, exp, coins, is_lv6, exp_needed)
        else: print("获取用户信息失败，自动任务可能无法准确执行。")
        initial_reward_status = self.user_handler.get_daily_reward_status(self.config['Cookie'])
        print("\n--- 初始每日任务状态 ---")
        self.user_handler.print_daily_reward_status_nicely(initial_reward_status)
        print("-" * 40)
        current_user_data_for_tasks = {'name': name, 'uid': mid, 'coins': coins, 'is_lv6': is_lv6}
        self.automated_tasks_executor.execute_tasks(current_user_data_for_tasks, initial_reward_status)
        print("\n--- 最终每日任务状态 (自动化) ---")
        final_reward_status = self.user_handler.get_daily_reward_status(self.config['Cookie'])
        self.user_handler.print_daily_reward_status_nicely(final_reward_status)
        print("\n自动化任务执行完毕。")

if __name__ == "__main__":
    app = MainApplication()
    if "--auto" in sys.argv:
        app.run_automated()
    else:
        app.run_interactive()
    print("\n脚本执行流程结束。")
    if "--auto" not in sys.argv : input("按任意键退出...")
