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
  - ""
  
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
  enable_fallback_fetch: true
  videos_to_fetch_in_fallback: 75

  Priority_Ups:
    - id: "476491780"
      name: "SechiAnimation"
    - id: "3493265644980448"
      name: "碧蓝档案"
    - id: "3494361637587456"
      name: "麻雀糖-BA同人短漫"

Global_Settings:
  videos_per_up_to_fetch_default: 10
"""

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
        self.html_session_for_wbi.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com/", "Accept-Language": "zh-CN,zh;q=0.9"})
    def _get_wbi_keys_internal(self, cookies_for_nav_api):
        nav_url = "https://api.bilibili.com/x/web-interface/nav"
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
    def _process_user_config(self, raw_config_data: dict) -> dict:
        user_conf = {}
        parsed_cookie = self._handle_single_cookie_str(raw_config_data["User_Cookie"][0])
        if not parsed_cookie: print("Cookie解析失败."); sys.exit(1)
        user_conf['Cookie'] = parsed_cookie
        raw_appoint_up_config = raw_config_data.get('Appoint_Up', [])
        user_conf['Appoint_Up'] = [{'id': str(item['id']).strip(), 'name': item.get('name','').strip()}
                           for item in raw_appoint_up_config if isinstance(item, dict) and 'id' in item and str(item['id']).strip().isdigit()]
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
        processed_coin_config = {
            'min_coin_for_putting': int(raw_coin_task_settings.get('min_coin_for_putting', 200)),
            'enable_fallback_fetch': raw_coin_task_settings.get('enable_fallback_fetch', True),
            'videos_to_fetch_in_fallback': int(raw_coin_task_settings.get('videos_to_fetch_in_fallback', 50)),
            'Priority_Ups': []
        }
        raw_priority_ups = raw_coin_task_settings.get('Priority_Ups', [])
        if isinstance(raw_priority_ups, list):
            processed_coin_config['Priority_Ups'] = [{'id': str(item['id']).strip(), 'name': item.get('name','').strip()}
                                                      for item in raw_priority_ups if isinstance(item, dict) and 'id' in item and str(item['id']).strip().isdigit()]
        user_conf['Coin_Task_Settings'] = processed_coin_config
        raw_global_settings = raw_config_data.get('Global_Settings', {})
        user_conf['Global_Settings'] = {
            'videos_per_up_to_fetch_default': int(raw_global_settings.get('videos_per_up_to_fetch_default', 10))
        }
        return user_conf
    def get_config(self): return self.user_config

class BiliRequest:
    def __init__(self):
        self.html_session = requests.Session()
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", 
            "Referer": "https://www.bilibili.com/", "Accept-Language": "zh-CN,zh;q=0.9"}
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
        self.urls = {"Bili_UserData": "http://api.bilibili.com/x/space/myinfo",
                     "Daily_Reward_Status": "https://api.bilibili.com/x/member/web/exp/reward"}
    def get_user_data(self, cookie: dict) -> tuple[str, int, int, int, int, bool, bool, int]:
        default_return = ("未知", 0, 0, 0, 0, True, False, 0)
        if not cookie: print("Cookie为空."); return default_return
        response = self.request_handler.get(self.urls['Bili_UserData'], cookie)
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
        response = self.request_handler.get(self.urls['Daily_Reward_Status'], cookie)
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
        self.urls = {"Share_Video":"https://api.bilibili.com/x/web-interface/share/add",
                     "Watch_Video":"https://api.bilibili.com/x/click-interface/web/heartbeat",
                     "Put_Coin":"https://api.bilibili.com/x/web-interface/coin/add",
                     "Archive_Relation":"https://api.bilibili.com/x/web-interface/archive/relation",
                     "Space_Arc_Search":"https://api.bilibili.com/x/space/wbi/arc/search",
                     "Space_Acc_Info":"https://api.bilibili.com/x/space/acc/info",
                     "Video_View_Info":"https://api.bilibili.com/x/web-interface/view"}
        self._up_name_cache = {}
    def _get_up_name_by_mid(self, mid: str, cookie: dict) -> str | None:
        if mid in self._up_name_cache: return self._up_name_cache[mid]
        resp = self.request_handler.get(self.urls['Space_Acc_Info'], cookie, params={'mid': mid})
        if resp and resp.json().get('code') == 0: self._up_name_cache[mid] = resp.json()['data']['name']; return self._up_name_cache[mid]
        return None
    def _check_video_coin_status(self, cookie: dict, aid: str) -> int:
        resp = self.request_handler.get(self.urls['Archive_Relation'], cookie, params={'aid': aid})
        return resp.json()['data'].get('coin', 0) if resp and resp.json().get('code') == 0 else -1
    def get_video_details_from_view_api(self, aid_or_bvid: str, cookie: dict, id_type:str = "aid") -> dict | None:
        params = {id_type: aid_or_bvid}
        response = self.request_handler.get(self.urls['Video_View_Info'], cookie, params=params)
        if response and response.json().get('code') == 0:
            data = response.json().get('data', {})
            return {'title': data.get('title', '未知标题'), 'duration': data.get('duration', 0),
                    'desc': data.get('desc', ''), 'pic_url': data.get('pic', ''),
                    'aid': str(data.get('aid')), 'bvid': data.get('bvid','')}
        return None
    def get_videos_from_up_list(self, cookie: dict, up_list: list, videos_per_up_target: int, for_coin_task: bool = False, coin_videos_needed: int = 0) -> list:
        if not up_list: print("UP主列表为空."); return []
        self.request_handler.wbi_manager._refresh_wbi_keys_internal(cookie)
        collected_videos = []
        
        for up_conf in up_list:
            mid = up_conf.get('id')
            if not mid: print(f"UP主配置 {up_conf.get('name','未知UP')} 缺少ID，跳过。"); continue
            name = up_conf.get('name') or self._get_up_name_by_mid(mid, cookie) or f"MID:{mid}"
            
            if for_coin_task:
                print(f"为投币任务从UP '{name}' 获取最多 {videos_per_up_target} 个视频...")
                page_num = 1
                while True:
                    if len(list({v['aid']: v for v in collected_videos}.values())) >= videos_per_up_target: break
                    if coin_videos_needed > 0 and len(list({v['aid']: v for v in collected_videos}.values())) >= coin_videos_needed: break
                    params_search = {'mid': mid, 'pn': page_num, 'ps': 50, 'order':'pubdate','dm_img_list':'[]','dm_cover_img_str':'V2ViRmlsRTMyNw=='}
                    resp = self.request_handler.get(self.urls['Space_Arc_Search'], cookie, params=params_search, needs_wbi=True)
                    if not resp or resp.json().get('code') != 0:
                        print(f"获取UP '{name}' 第 {page_num} 页视频失败: {resp.json().get('message','未知错误') if resp else '请求错误'}")
                        break
                    vlist = resp.json().get('data',{}).get('list',{}).get('vlist',[])
                    if not vlist: break
                    for v_data in vlist:
                        if 'aid' in v_data and self._check_video_coin_status(cookie, str(v_data['aid'])) == 0:
                            collected_videos.append({'aid': str(v_data['aid']), 'title': v_data.get('title', '?'), 'mid': mid, 'pubdate': v_data.get('created', 0)})
                    page_num += 1; time.sleep(random.uniform(0.5, 1.5))
            else:
                print(f"从UP '{name}' 获取 {videos_per_up_target} 个最新视频...")
                params_search = {'mid': mid, 'pn': 1, 'ps': videos_per_up_target, 'order':'pubdate','dm_img_list':'[]','dm_cover_img_str':'V2ViRmlsRTMyNw=='}
                resp = self.request_handler.get(self.urls['Space_Arc_Search'], cookie, params=params_search, needs_wbi=True)
                if resp and resp.json().get('code') == 0:
                    vlist = resp.json().get('data',{}).get('list',{}).get('vlist',[])
                    for v_data in vlist:
                        if 'aid' in v_data: collected_videos.append({'aid': str(v_data['aid']), 'title': v_data.get('title', '?'), 'mid': mid, 'pubdate': v_data.get('created', 0)})
        
        unique_videos = list({v['aid']: v for v in collected_videos}.values())
        final_msg = f"获取结束，共找到 {len(unique_videos)} 个唯一的符合投币条件的视频。" if for_coin_task else f"获取结束，共找到 {len(unique_videos)} 个视频。"
        print(final_msg)
        return unique_videos

    def share_video(self, cookie: dict, video_list: list) -> bool:
        print("\n#视频分享任务#")
        if not video_list: print("无视频可分享."); return True
        v = random.choice(video_list); aid, title, csrf = v['aid'], v['title'], cookie.get('bili_jct', '')
        if not csrf: print("分享失败:缺bili_jct"); return False
        print(f"分享视频 '{title}' (AID:{aid})")
        resp = self.request_handler.post(self.urls['Share_Video'], cookie, post_data={"aid": aid, "csrf": csrf})
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
        resp = self.request_handler.post(self.urls['Watch_Video'], cookie, post_data=data)
        if resp and resp.json().get('code') == 0: print(f"上报成功: '{title}' 🥳"); time.sleep(random.randint(3,7)); return True
        else: print(f"上报失败 '{title}': {resp.json().get('message', '无API消息') if resp else '请求错误'}"); return False
    def coin_videos(self, cookie: dict, initial_video_list: list, coins_bal: int, coins_exp: int, coin_task_settings: dict) -> bool:
        print("\n#视频投币任务#")
        min_coin_for_putting = coin_task_settings.get('min_coin_for_putting', 200)
        if coins_bal < min_coin_for_putting:
            print(f"硬币({coins_bal})不足{min_coin_for_putting}."); return True
        if coins_exp >= 50:
            print("投币经验已满(50)."); return True
        csrf = cookie.get('bili_jct', '')
        ops_needed = min(math.ceil((50 - coins_exp) / 10), 5, int(coins_bal))
        if not csrf or ops_needed <= 0:
            print("无需投币或缺bili_jct."); return True
        print(f"目标投币次数: {ops_needed} (当前投币Exp:{coins_exp}/50)")
        thrown_count = 0
        video_pool = initial_video_list.copy()
        video_pool.sort(key=lambda v: v.get('pubdate', float('inf')))
        priority_ups = coin_task_settings.get('Priority_Ups', [])
        shuffled_priority_ups = random.sample(priority_ups, len(priority_ups))
        while thrown_count < ops_needed:
            if video_pool:
                for v in list(video_pool):
                    if thrown_count >= ops_needed or coins_bal < 1: break
                    aid, title = v['aid'], v['title']
                    print(f"向 '{title}' (av{aid}) 投1币并点赞...")
                    resp = self.request_handler.post(self.urls['Put_Coin'], cookie, post_data={'aid':aid,'multiply':1,'select_like':1,'cross_domain':'true','csrf':csrf})
                    if resp and resp.json().get('code') == 0:
                        print(f"投币成功: '{title}' 💿"); thrown_count+=1; coins_bal-=1
                        time.sleep(random.randint(7,15))
                    else:
                        print(f"投币异常 '{title}': {resp.json().get('message', '无API消息') if resp else '请求错误'}")
                        if "投币AVID" in resp.json().get('message', ''): coins_bal -= 1
                    video_pool.remove(v)
            if thrown_count < ops_needed:
                if coin_task_settings.get('enable_fallback_fetch') and shuffled_priority_ups:
                    next_up = shuffled_priority_ups.pop(0)
                    needed_for_task = ops_needed - thrown_count
                    print(f"\n投币数量不足，启动后备方案：尝试从优先UP主 '{next_up['name']}' 获取 {needed_for_task} 个可投币视频。")
                    videos_to_fetch = coin_task_settings.get('videos_to_fetch_in_fallback', 50)
                    fallback_videos = self.get_videos_from_up_list(cookie, [next_up], videos_to_fetch, for_coin_task=True, coin_videos_needed=needed_for_task)
                    
                    new_aids = {v['aid'] for v in video_pool}
                    for fv in fallback_videos:
                        if fv['aid'] not in new_aids: video_pool.append(fv)
                    if fallback_videos: video_pool.sort(key=lambda v: v.get('pubdate', float('inf')))
                else:
                    print(f"\n无法获取更多视频（已无优先UP主或后备方案被禁用），投币任务提前结束。")
                    break
        print(f"\n本轮投币任务结束，共投出 {thrown_count} 枚硬币。")
        return True

class MangaTaskHandler:
    def __init__(self, request_handler: BiliRequest, manga_config: dict):
        self.request_handler=request_handler; self.manga_config=manga_config
        self.urls={"ClockIn":"https://manga.bilibili.com/twirp/activity.v1.Activity/ClockIn",
                     "AddHistory":"https://manga.bilibili.com/twirp/bookshelf.v1.Bookshelf/AddHistory"}
        self._manga_headers={"Origin":"https://manga.bilibili.com","Referer":"https://manga.bilibili.com/",
                               "Accept":"application/json","Content-Type":"application/x-www-form-urlencoded"}
    def perform_clock_in(self, cookie: dict) -> bool:
        print("\n#漫画签到#")
        if not self.manga_config.get("Enabled",False): print("漫画任务未启用."); return True
        post_data_clockin={'platform':'android'}
        resp=self.request_handler.post(self.urls['ClockIn'],cookie,post_data=post_data_clockin,headers=self._manga_headers)
        if resp:
            try:
                res_json=resp.json(); code=res_json.get('code'); msg=res_json.get('msg','').lower()
                if code==0: print("漫画签到成功 🥳"); return True
                elif "cannot clockin repeatedly" in msg or "已签到" in msg or "不能重复签到" in msg or "already" in msg or code==1:
                    print(f"漫画今日已签到过 😊 (API Code: {code}, Msg: \"{res_json.get('msg','')}\")"); return True
                else: print(f"漫画签到失败: Code {code}, Msg: \"{res_json.get('msg','')}\""); return False
            except requests.exceptions.JSONDecodeError: print(f"漫画签到响应错误: 无法解析JSON - {resp.text[:100]}"); return False
            except Exception as e: print(f"漫画签到响应处理异常: {e}"); return False
        else: print("漫画签到请求失败 (无响应对象)."); return False
    def perform_manga_read(self, cookie: dict) -> bool:
        print("\n#漫画阅读#")
        if not self.manga_config.get("Enabled",False): print("漫画任务未启用."); return True
        rt=self.manga_config.get("Read_Target")
        if not rt or not rt.get('comic_id') or not rt.get('ep_id'):
            print("漫画阅读目标配置不完整 (缺少comic_id或ep_id)."); return True
        comic_id_str=rt['comic_id']; ep_id_str=rt['ep_id']
        manga_title_from_config=rt['title'] 
        print(f"阅读漫画 '{manga_title_from_config}' (Comic ID: {comic_id_str}, Episode ID: {ep_id_str})")
        post_data_read={'comic_id':comic_id_str,'ep_id':ep_id_str,'platform':'android'}
        resp=self.request_handler.post(self.urls['AddHistory'],cookie,post_data=post_data_read,headers=self._manga_headers)
        if resp:
            try:
                res_json=resp.json()
                if res_json.get('code')==0:
                    print(f"漫画阅读 '{manga_title_from_config}' 上报成功 👍"); time.sleep(random.randint(2,5)); return True
                else:
                    print(f"漫画阅读失败 '{manga_title_from_config}': Code {res_json.get('code')}, Msg: \"{res_json.get('message',res_json.get('msg','N/A'))}\""); return False
            except requests.exceptions.JSONDecodeError: print(f"漫画阅读响应错误: 无法解析JSON - {resp.text[:100]}"); return False
            except Exception as e: print(f"漫画阅读响应处理异常: {e}"); return False
        else: print("漫画阅读请求失败 (无响应对象)."); return False

class AutomatedTasksExecutor:
    def __init__(self, config_all: dict, user_handler: UserHandler, daily_tasks_handler: DailyTasksHandler, manga_task_handler: MangaTaskHandler):
        self.config = config_all
        self.user_cookie = self.config['Cookie']
        self.appoint_up_list = self.config.get('Appoint_Up',[])
        self.play_mode_settings = self.config.get('PlayMode_Settings', {})
        self.watch_task_settings = self.config.get('Watch_Task_Settings', {})
        self.global_settings = self.config.get('Global_Settings', {})
        self.coin_task_settings = self.config.get('Coin_Task_Settings', {})
        self.user_handler = user_handler
        self.daily_tasks_handler = daily_tasks_handler
        self.manga_task_handler = manga_task_handler
    def execute_tasks(self, current_user_data_dict: dict, initial_reward_status: dict) -> dict:
        reward_status_current = initial_reward_status.copy()
        is_lv6 = current_user_data_dict.get('is_lv6', True)
        user_coins = current_user_data_dict.get('coins', 0)
        print("\n--- 开始执行日常任务 ---")

        if is_lv6:
            print("用户已满级LV6, 无需执行经验任务。")
            return reward_status_current
        
        if reward_status_current.get('total_exp_today', 0) >= 65:
            print("每日总经验已达上限(65)，跳过所有日常任务。")
            return reward_status_current

        if not reward_status_current.get('share', False):
            self.manga_task_handler.perform_clock_in(self.user_cookie)
            self.manga_task_handler.perform_manga_read(self.user_cookie)
        else:
            print("\n#漫画任务检查#\n分享任务已完成，跳过漫画任务。")

        reward_status_current = self.user_handler.get_daily_reward_status(self.user_cookie)
        if reward_status_current.get('total_exp_today', 0) >= 65:
            print("\n经验已满，结束任务。")
            return reward_status_current
        
        print("\n#视频任务检查#")
        if not reward_status_current.get('watch', False) or not reward_status_current.get('share', False):
            combined_up_list_raw = self.appoint_up_list + self.coin_task_settings.get('Priority_Ups', [])
            up_pool_for_tasks = list({up['id']: up for up in combined_up_list_raw}.values())
            videos_for_tasks = []
            if up_pool_for_tasks:
                random_up_for_tasks = random.choice(up_pool_for_tasks)
                videos_to_get = self.play_mode_settings.get('videos_per_up_play_mode', 3)
                videos_for_tasks = self.daily_tasks_handler.get_videos_from_up_list(self.user_cookie, [random_up_for_tasks], videos_to_get)

            if not videos_for_tasks:
                print("无法获取视频，跳过观看和分享任务。")
            else:
                if not reward_status_current.get('watch', False):
                    min_w, max_w = self.watch_task_settings.get('Wait_Time_Min', 3), self.watch_task_settings.get('Wait_Time_Max', 28)
                    if self.daily_tasks_handler.watch_video(self.user_cookie, videos_for_tasks, min_w, max_w):
                        reward_status_current = self.user_handler.get_daily_reward_status(self.user_cookie)
                
                if not reward_status_current.get('share', False):
                    if self.daily_tasks_handler.share_video(self.user_cookie, videos_for_tasks):
                        reward_status_current = self.user_handler.get_daily_reward_status(self.user_cookie)
        else:
            print("\n观看/分享任务均已完成, 跳过.")

        coins_exp_current = reward_status_current.get('coins_exp', 0)
        if coins_exp_current < 50:
            videos_per_up_default = self.global_settings.get('videos_per_up_to_fetch_default', 10)
            initial_coin_videos = self.daily_tasks_handler.get_videos_from_up_list(self.user_cookie, self.appoint_up_list, videos_per_up_default, for_coin_task=True)
            self.daily_tasks_handler.coin_videos(self.user_cookie, initial_coin_videos, user_coins, coins_exp_current, self.coin_task_settings)
        else:
            print("\n投币任务经验已满, 跳过.")
            
        print("\n--- 所有日常任务尝试完毕 ---")
        return self.user_handler.get_daily_reward_status(self.user_cookie)

class VideoToolsModule:
    def __init__(self, config_all: dict, bili_request: BiliRequest, daily_tasks_handler: DailyTasksHandler, user_handler: UserHandler):
        self.config = config_all
        self.user_cookie = self.config['Cookie']
        self.play_mode_settings = self.config.get('PlayMode_Settings', {})
        self.appoint_up_list = self.config.get('Appoint_Up', [])
        self.priority_ups_list = self.config.get('Coin_Task_Settings', {}).get('Priority_Ups', [])
        self.bili_request = bili_request
        self.daily_tasks_handler = daily_tasks_handler
        self.user_handler = user_handler
    def _get_user_action_parser(self) -> str:
        while True:
            prompt = "\n选择视频工具操作:\n[1] 解析视频播放上报\n[2] 解析视频封面URL\n[0] 返回主菜单 : "
            action = input(prompt).strip()
            if action in ['0', '1', '2']: return action
            print("无效输入。")
    def _extract_video_id_from_url(self, video_url: str) -> tuple[str | None, str | None]:
        aid_match = re.search(r"(?:av|aid(?:=|%3D))(\d+)", video_url, re.IGNORECASE)
        bvid_match = re.search(r"(BV[a-zA-Z0-9]+)", video_url, re.IGNORECASE)
        aid = aid_match.group(1) if aid_match else None
        bvid = bvid_match.group(1) if bvid_match else None
        return aid, bvid
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
        elif video_details: print(f"未能获取《{video_details['title']}》的封面URL。")
        else: print(f"获取视频详情失败。")
    def _get_videos_for_play_mode(self) -> list:
        print("\n#获取播放模式视频列表#")
        combined_list_raw = self.appoint_up_list + self.priority_ups_list
        up_list_full = list({up['id']: up for up in combined_list_raw}.values())
        selected_up_list = []
        strategy = self.play_mode_settings.get('up_selection_strategy', 'all')
        num_ups_subset = self.play_mode_settings.get('num_ups_for_random_subset', 1)
        if strategy == "random_subset" and up_list_full:
            num_to_select = min(num_ups_subset, len(up_list_full))
            if num_to_select > 0:
                selected_up_list = random.sample(up_list_full, num_to_select)
                print(f"随机策略: 已从 {len(up_list_full)} 位UP主中选择 {len(selected_up_list)} 位。")
        else:
            selected_up_list = up_list_full
            print("UP选择策略: 全部。")
        if not selected_up_list: print("无UP主可选或选择数量为0。"); return []
        videos_per_up = self.play_mode_settings.get('videos_per_up_play_mode', 3)
        return self.daily_tasks_handler.get_videos_from_up_list(self.user_cookie, selected_up_list, videos_per_up, for_coin_task=False)
    def _handle_play_mode_reporting(self):
        print("\n--- 解析视频播放上报 ---")
        video_list_raw = self._get_videos_for_play_mode()
        if not video_list_raw: print("无视频可播放。"); return
        chosen_video_raw = random.choice(video_list_raw)
        aid_str = chosen_video_raw['aid']
        video_details = self.daily_tasks_handler.get_video_details_from_view_api(aid_str, self.user_cookie)
        if not video_details: print(f"无法获取视频 {aid_str} 的详细信息。"); return
        title, duration_sec = video_details['title'], video_details['duration']
        desc, pic_url = video_details['desc'], video_details['pic_url']
        print(f"播放: '{title}' (AID:{aid_str})\n实际时长: {str(timedelta(seconds=duration_sec)) if duration_sec > 0 else '未知'}")
        print(f"简介:\n{desc if desc else '无'}\n封面URL: {pic_url if pic_url else '无'}")
        max_local_wait = self.play_mode_settings.get('max_play_duration_local_wait', 120)
        if max_local_wait <= 0: max_local_wait = 60
        ideal_report_duration = 0
        if duration_sec > 0: ideal_report_duration = min(int(duration_sec * random.uniform(0.6, 1.0)), duration_sec)
        else: 
            actual_rand_max = min(60, max_local_wait)
            ideal_report_duration = random.randint(max(1, min(15, actual_rand_max)), actual_rand_max) if actual_rand_max >=15 else max(1,actual_rand_max)
        local_wait_target = min(ideal_report_duration, max_local_wait)
        if local_wait_target <= 0: local_wait_target = max(1, min(15, max_local_wait))
        print(f"\n计划模拟播放上限: {local_wait_target}s\n按 Ctrl+C 可中断模拟播放")
        elapsed_play_time = 0
        try:
            for i in range(local_wait_target, 0, -1):
                print(f"\r模拟播放: '{title}'. 剩余 {i} 秒...", end=""); time.sleep(1); elapsed_play_time += 1
            print("\n模拟播放计时完成.")
        except KeyboardInterrupt: print("\n模拟播放被中断.")
        if elapsed_play_time == 0: print("未模拟有效播放时长，不上报。"); return
        user_choice = input(f"已模拟播放 {elapsed_play_time}s. [1]上报, [2]不上报: ").strip()
        if user_choice == '1':
            data = {"aid": aid_str, "played_time": elapsed_play_time, "csrf": self.user_cookie.get('bili_jct', '')}
            resp = self.bili_request.post(self.daily_tasks_handler.urls['Watch_Video'], self.user_cookie, post_data=data)
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
                print("\n" + "="*20 + " 视频工具操作结束 " + "="*20); time.sleep(1)
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
        prompt = ("\n选择功能:\n"
                  "[1] 执行B站日常任务\n"
                  "[2] 使用B站视频工具\n"
                  "[0] 退出程序\n"
                  "请输入选项: ")
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
                print("\n" + "="*20 + " 返回主菜单 " + "="*20); time.sleep(1)
        except KeyboardInterrupt: print("\n交互模式被用户中断 (Ctrl+C)。")
        except Exception as e: print(f"\n交互模式发生未捕获异常: {e}"); import traceback; traceback.print_exc()
    def run_automated(self):
        print("\n" + "#"*20 + " B站助手已启动 (自动模式) " + "#"*20)
        print("正在获取初始用户信息和任务状态...")
        name, mid, level, exp, coins, is_lv6, success, exp_needed = self.user_handler.get_user_data(self.config['Cookie'])
        if success: self.user_handler.print_user_data_nicely(name, mid, level, exp, coins, is_lv6, exp_needed)
        else: print("获取用户信息失败，自动任务可能无法准确执行。")
        initial_reward_status = self.user_handler.get_daily_reward_status(self.config['Cookie'])
        print("\n--- 初始每日任务状态 ---")
        self.user_handler.print_daily_reward_status_nicely(initial_reward_status)
        print("-" * 40)
        current_user_data_for_tasks = {'name': name, 'uid': mid, 'coins': coins, 'is_lv6': is_lv6}
        final_reward_status = self.automated_tasks_executor.execute_tasks(current_user_data_for_tasks, initial_reward_status)
        print("\n--- 最终每日任务状态 (自动化) ---")
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
