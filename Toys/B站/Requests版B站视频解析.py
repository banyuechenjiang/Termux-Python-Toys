import time
import random
import re
import sys
from urllib.parse import urlencode
from datetime import timedelta, datetime
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
  - id: "476491780"
    name: "SechiAnimation"
  - id: "3493265644980448"
    name: "碧蓝档案"
  - id: "3494361637587456"
    name: "麻雀糖-BA同人短漫"
  - id: "165906284"
    name: "森羅万象【shinra-bansho】"
  - id: "3493078251866300"
    name: "AliceInCradle官方"
PlayMode_Settings:
  up_selection_strategy: "random_subset"
  num_ups_for_random_subset: 3
  videos_per_up_play_mode: 3
  max_play_duration_local_wait: 120
"""

MIN_COIN_FOR_PUTTING = 200
VIDEOS_PER_UP_TO_FETCH_DEFAULT = 5

class WbiManager:
    MIXIN_KEY_ENC_TAB = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
        33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
        61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
        36, 20, 34, 44, 52
    ]
    def __init__(self):
        self.img_key = None
        self.sub_key = None
        self.html_session_for_wbi = requests.Session()
        self.html_session_for_wbi.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            "Accept-Language": "zh-CN,zh;q=0.9"
        })

    def _get_wbi_keys_internal(self, cookies_for_nav_api):
        nav_url = "https://api.bilibili.com/x/web-interface/nav"
        try:
            resp = self.html_session_for_wbi.get(nav_url, cookies=cookies_for_nav_api, timeout=10)
            resp.raise_for_status()
            json_data = resp.json()
            if json_data.get("code") == 0:
                wbi_img = json_data.get("data", {}).get("wbi_img", {})
                img_url = wbi_img.get("img_url", "")
                sub_url = wbi_img.get("sub_url", "")
                if img_url and sub_url:
                    self.img_key = img_url.split('/')[-1].split('.')[0]
                    self.sub_key = sub_url.split('/')[-1].split('.')[0]
                    return True
        except requests.exceptions.RequestException:
            pass
        except Exception:
            pass
        print("WBI密钥获取失败.")
        return False

    def _refresh_wbi_keys_internal(self, cookies_for_nav_api):
        return self._get_wbi_keys_internal(cookies_for_nav_api)

    def get_mixin_key(self, orig_key: str):
        return ''.join([orig_key[i] for i in self.MIXIN_KEY_ENC_TAB])[:32]

    def encode_wbi_params(self, params: dict, cookies_for_nav_api: dict):
        if not self.img_key or not self.sub_key:
            if not self._refresh_wbi_keys_internal(cookies_for_nav_api):
                 print("WBI密钥不可用,无法签名.")
                 return params
        mixin_key = self.get_mixin_key(self.img_key + self.sub_key)
        curr_time = round(time.time())
        signed_params = params.copy()
        signed_params['wts'] = curr_time
        signed_params = dict(sorted(signed_params.items()))
        query = urlencode(signed_params)
        hl = hashlib.md5()
        hl.update(f"{query}{mixin_key}".encode('utf-8'))
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
        user_conf['Up'] = [{'id': str(item['id']).strip(), 'name': item.get('name','').strip()}
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
            'videos_per_up_play_mode': int(raw_play_mode_settings.get('videos_per_up_play_mode', 5)),
            'max_play_duration_local_wait': int(raw_play_mode_settings.get('max_play_duration_local_wait', 120))
        }
        raw_watch_task_settings = raw_config_data.get('Watch_Task_Settings', {})
        user_conf['Watch_Task_Settings'] = {
            'Wait_Time_Min': int(raw_watch_task_settings.get('Wait_Time_Min', 3)),
            'Wait_Time_Max': int(raw_watch_task_settings.get('Wait_Time_Max', 28))
        }
        return user_conf

    def get_config(self): return self.user_config

class BiliRequest:
    def __init__(self):
        self.html_session = requests.Session()
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", 
            "Referer": "https://www.bilibili.com/", 
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.wbi_manager = WbiManager()

    def get(self, url: str, cookies: dict, params:dict=None, needs_wbi:bool=False, **kwargs) -> requests.Response | None:
        headers = {**self.default_headers, **kwargs.pop('headers', {})}
        current_params = params.copy() if params else {}
        if needs_wbi:
            current_params = self.wbi_manager.encode_wbi_params(current_params, cookies)
            if 'w_rid' not in current_params: return None
        full_url = f"{url}?{urlencode(current_params)}" if current_params else url
        try:
            res = self.html_session.get(url=full_url, headers=headers, cookies=cookies, timeout=10, **kwargs)
            res.raise_for_status(); return res
        except requests.exceptions.RequestException as e: print(f"GET失败 {url}: {e}"); return None

    def post(self, url: str, cookies: dict, params: dict = None, post_data: dict = None, needs_wbi: bool = False, **kwargs) -> requests.Response | None:
        headers = {**self.default_headers, **kwargs.pop('headers', {})}
        current_params = params.copy() if params else {}
        
        if needs_wbi:
            current_params = self.wbi_manager.encode_wbi_params(current_params, cookies)
            if 'w_rid' not in current_params: return None
            
        final_url = f"{url}?{urlencode(current_params)}" if current_params else url
        try:
            res = self.html_session.post(url=final_url, headers=headers, cookies=cookies, data=post_data, timeout=15, **kwargs)
            res.raise_for_status(); return res
        except requests.exceptions.RequestException as e: print(f"POST失败 {url}: {e}"); return None

class UserHandler:
    def __init__(self, request_handler: BiliRequest):
        self.request_handler = request_handler
        self.urls = {"Bili_UserData": "http://api.bilibili.com/x/space/myinfo",
                     "Daily_Reward_Status": "https://api.bilibili.com/x/member/web/exp/reward"}

    def get_user_data(self, cookie: dict) -> tuple[str, int, int, int, int, bool, bool]:
        default_return = ("未知", 0, 0, 0, 0, True, False)
        if not cookie: print("Cookie为空."); return default_return
        response = self.request_handler.get(self.urls['Bili_UserData'], cookie)
        if not response: return default_return
        try:
            res_json = response.json()
            if res_json.get('code') == -101: print("Cookie错误或失效"); return default_return
            if res_json.get('code') != 0: print(f"用户信息API失败: {res_json.get('message')}"); return default_return
            d = res_json.get('data', {})
            name = d.get('name','未知用户')
            mid = d.get('mid',0)
            level = d.get('level',0)
            coins_raw = d.get('coins',0)
            coins = int(float(coins_raw)) if str(coins_raw).replace('.','',1).isdigit() else 0
            exp = d.get('level_exp',{}).get('current_exp',0)
            is_lv6 = level >= 6
            
            print(f"用户名: {name}")
            print(f"UID: {mid}")
            print(f"当前等级: LV {level}")
            print(f"当前硬币: {coins} 个")
            print(f"当前经验: {exp}")
            
            if not is_lv6:
                next_exp_val = d.get('level_exp',{}).get('next_exp')
                if next_exp_val is not None and next_exp_val != -1:
                    print(f"下级所需: {int(next_exp_val)}")
                    print(f"仍需经验: {max(0, int(next_exp_val) - exp)}")
            elif level >=6 :
                print("用户已达最高等级 (LV6+).")
            return name, mid, level, exp, coins, is_lv6, True
        except Exception as e: print(f"用户信息响应错误: {e}"); return default_return

    def get_daily_reward_status(self, cookie: dict) -> dict:
        default_status = {'login': False, 'watch': False, 'share': False, 'coins_exp': 0, 'total_exp_today': 0}
        if not cookie: return default_status
        response = self.request_handler.get(self.urls['Daily_Reward_Status'], cookie)
        if response and response.json().get('code') == 0:
            data = response.json().get('data', {})
            status = {k: data.get(k, False) for k in ['login', 'watch', 'share']}
            status['coins_exp'] = data.get('coins', 0)
            status['total_exp_today'] = sum(5 for k in ['login', 'watch', 'share'] if status[k]) + status['coins_exp']
            return status
        print(f"每日奖励状态获取失败: {response.json().get('message', '无API消息') if response else '请求错误'}")
        return default_status

class DailyTasks:
    def __init__(self, request_handler: BiliRequest):
        self.request_handler = request_handler
        self.urls = {"Share_Video": "https://api.bilibili.com/x/web-interface/share/add",
                     "Watch_Video": "https://api.bilibili.com/x/click-interface/web/heartbeat",
                     "Put_Coin": "https://api.bilibili.com/x/web-interface/coin/add",
                     "Archive_Relation": "https://api.bilibili.com/x/web-interface/archive/relation",
                     "Space_Arc_Search": "https://api.bilibili.com/x/space/wbi/arc/search",
                     "Space_Acc_Info": "https://api.bilibili.com/x/space/acc/info",
                     "Video_View_Info": "https://api.bilibili.com/x/web-interface/view"}
        self._up_name_cache = {}

    def _get_up_name_by_mid(self, mid: str, cookie: dict) -> str | None:
        if mid in self._up_name_cache: return self._up_name_cache[mid]
        resp = self.request_handler.get(self.urls['Space_Acc_Info'], cookie, params={'mid': mid})
        if resp and resp.json().get('code') == 0: self._up_name_cache[mid] = resp.json()['data']['name']; return self._up_name_cache[mid]
        return None

    def _check_video_coin_status(self, cookie: dict, aid: str) -> int:
        resp = self.request_handler.get(self.urls['Archive_Relation'], cookie, params={'aid': aid})
        return resp.json()['data'].get('coin', 0) if resp and resp.json().get('code') == 0 else -1
    
    def _parse_duration_str_to_seconds(self, duration_str: str) -> int:
        if isinstance(duration_str, int): return duration_str
        if not isinstance(duration_str, str) or not duration_str: return 0
        parts = list(map(int, duration_str.split(':')))
        if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
        if len(parts) == 2: return parts[0]*60 + parts[1]
        if len(parts) == 1 and duration_str.isdigit(): return parts[0]
        return 0

    def get_video_details_from_view_api(self, aid_or_bvid: str, cookie: dict, id_type:str = "aid") -> dict | None:
        params = {id_type: aid_or_bvid}
        response = self.request_handler.get(self.urls['Video_View_Info'], cookie, params=params)
        if response and response.json().get('code') == 0:
            data = response.json().get('data', {})
            return {'title': data.get('title', '未知标题'), 'duration': data.get('duration', 0),
                    'desc': data.get('desc', ''), 'pic_url': data.get('pic', ''),
                    'aid': str(data.get('aid')), 'bvid': data.get('bvid','')}
        return None

    def get_videos_for_tasks(self, cookie: dict, up_preference_list: list, for_coin_task: bool) -> list:
        print("\n#获取任务视频列表#")
        if not up_preference_list: print("UP主列表为空."); return []
        
        first_up_with_id = next((up for up in up_preference_list if up.get('id')), None)
        if not first_up_with_id: print("UP主列表中没有任何UP主配置了ID，无法初始化WBI。"); return []
        
        # Prime WBI keys if needed, by making a dummy call.
        # The BiliRequest's WBI manager will cache keys upon first successful retrieval.
        self.request_handler.get(self.urls['Space_Arc_Search'], cookie,
                                 params={'mid': first_up_with_id['id'], 'pn': 1, 'ps': 1, 'order':'pubdate','dm_img_list':'[]','dm_cover_img_str':'V2ViRmlsRTMyNw=='}, needs_wbi=True)
        
        collected_videos = []
        for up_conf in up_preference_list:
            mid = up_conf.get('id')
            if not mid: print(f"UP主配置 {up_conf.get('name','未知UP')} 缺少ID，跳过。"); continue

            name = up_conf.get('name') or self._get_up_name_by_mid(mid, cookie) or f"MID:{mid}"
            print(f"从UP '{name}' (ID:{mid}) 获取视频...")
            params = {'mid': mid, 'pn': 1, 'ps': VIDEOS_PER_UP_TO_FETCH_DEFAULT, 'order':'pubdate','dm_img_list':'[]','dm_cover_img_str':'V2ViRmlsRTMyNw=='}
            resp = self.request_handler.get(self.urls['Space_Arc_Search'], cookie, params=params, needs_wbi=True)
            if resp and resp.json().get('code') == 0:
                vlist = resp.json().get('data',{}).get('list',{}).get('vlist',[])
                for v_data in vlist:
                    if 'aid' in v_data:
                        video_entry = {'aid': str(v_data['aid']), 'title': v_data.get('title', '?'),
                                       'initial_duration_str': str(v_data.get('duration', "0")), 'mid': mid}
                        if not for_coin_task or self._check_video_coin_status(cookie, video_entry['aid']) == 0:
                            collected_videos.append(video_entry)
            elif resp: print(f"获取UP '{name}' 视频列表失败: {resp.json().get('message','未知错误')}")
            else: print(f"获取UP '{name}' 视频列表请求失败。")
        
        unique_videos = list({v['aid']: v for v in collected_videos}.values())
        print(f"获取到 {len(unique_videos)} 个{'未投币' if for_coin_task else ''}视频.")
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
        
        v_raw = random.choice(video_list)
        aid, title_raw = v_raw['aid'], v_raw['title']
        
        v_details = self.get_video_details_from_view_api(aid, cookie)
        title = title_raw
        actual_duration_sec = 0

        if v_details:
            title = v_details['title']
            actual_duration_sec = v_details['duration']
        else:
            actual_duration_sec = self._parse_duration_str_to_seconds(v_raw['initial_duration_str'])
        
        local_wait_time = random.randint(min_wait, max_wait)
        report_time = local_wait_time

        if actual_duration_sec > 0:
            report_time = min(local_wait_time, actual_duration_sec)
        
        print(f"观看: '{title}' (AID:{aid}), 上报/等待时长:{report_time}s")
        time.sleep(report_time)
        
        data = {"aid": aid, "played_time": report_time, "csrf": cookie.get('bili_jct', '')}
        resp = self.request_handler.post(self.urls['Watch_Video'], cookie, post_data=data)
        if resp and resp.json().get('code') == 0: print(f"上报成功: '{title}' 🥳"); time.sleep(random.randint(3,7)); return True
        else: print(f"上报失败 '{title}': {resp.json().get('message', '无API消息') if resp else '请求错误'}"); return False

    def coin_videos(self, cookie: dict, video_list: list, coins_bal: int, coins_exp: int, total_exp: int) -> bool:
        print("\n#视频投币任务#")
        if coins_bal < MIN_COIN_FOR_PUTTING: print(f"硬币({coins_bal})不足{MIN_COIN_FOR_PUTTING}."); return True
        if coins_exp >= 50 or total_exp >= 65: print("投币经验已满或总经验已达上限."); return True
        
        csrf = cookie.get('bili_jct', ''); ops_needed = min(math.ceil((min(50 - coins_exp, 65 - total_exp)) / 10), 5)
        if not csrf or ops_needed <= 0 : print("无需投币或缺bili_jct."); return True
        print(f"目标投币次数: {ops_needed} (当前投币Exp:{coins_exp}/50, 总Exp:{total_exp}/65)")
        
        shuffled_videos = random.sample(video_list, k=min(len(video_list), ops_needed + 2))
        thrown = 0
        for i in range(ops_needed):
            if not shuffled_videos or coins_bal < 1: break
            v = shuffled_videos.pop(0); aid, title = v['aid'], v['title']
            print(f"向 '{title}' (av{aid}) 投1币并点赞...")
            resp = self.request_handler.post(self.urls['Put_Coin'], cookie, post_data={'aid':aid,'multiply':1,'select_like':1,'cross_domain':'true','csrf':csrf})
            if resp and resp.json().get('code') == 0: print(f"投币成功: '{title}' 💿"); thrown+=1; coins_bal-=1; time.sleep(random.randint(7,15))
            else: print(f"投币异常 '{title}': {resp.json().get('message', '无API消息') if resp else '请求错误'}")
        if thrown > 0: print(f"本轮共投出 {thrown} 枚硬币.")
        return True

class VideoParserScriptRunner:
    def __init__(self):
        self.config_manager = ConfigManager(CONFIG_YAML_CONTENT)
        self.user_config = self.config_manager.get_config()
        self.request_handler = BiliRequest()
        self.user_handler = UserHandler(self.request_handler)
        self.daily_tasks_handler = DailyTasks(self.request_handler)
        self.current_user_data = {}
        self.video_view_url = "https://api.bilibili.com/x/web-interface/view"


    def _initial_user_info_display(self) -> bool:
        print("\n" + "#"*15 + " B站视频解析脚本 " + "#"*15)
        name, uid, _, _, _, _, success = self.user_handler.get_user_data(self.user_config['Cookie'])
        if not success or uid == 0: print("无法获取用户信息。"); return False
        self.current_user_data.update({'name': name, 'uid': uid})
        print(f"当前用户: {name} (UID:{uid})")
        print("-" * 45); return True

    def _get_user_action_parser(self) -> str:
        while True:
            prompt = "\n选择操作:\n[1] 解析视频播放上报\n[2] 解析视频封面URL\n[0] 退出 : "
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
        params = {}
        if bvid: params['bvid'] = bvid
        elif aid: params['aid'] = aid
        else: print("未能从URL中解析出有效视频ID。"); return
        
        response = self.request_handler.get(self.video_view_url, self.user_config['Cookie'], params=params)
        if response and response.json().get('code') == 0:
            data = response.json().get('data', {})
            pic_url, title = data.get('pic', ''), data.get('title', '未知标题')
            if pic_url: print(f"\n视频《{title}》的封面URL:\n{pic_url}")
            else: print(f"未能获取《{title}》的封面URL。")
        else: print(f"获取视频详情失败: {response.json().get('message') if response else '请求失败'}")

    def _get_videos_for_play_mode(self) -> list:
        print("\n#获取播放模式视频列表#")
        play_mode_settings = self.user_config.get('PlayMode_Settings', {})
        up_list = self.user_config.get('Up', [])
        
        selected_up_list = []
        strategy = play_mode_settings.get('up_selection_strategy', 'all')
        num_ups_subset = play_mode_settings.get('num_ups_for_random_subset', 1)
        
        if strategy == "random_subset" and up_list:
            num_to_select = min(num_ups_subset, len(up_list))
            if num_to_select > 0 : selected_up_list = random.sample(up_list, num_to_select)
        else: selected_up_list = up_list
        
        if not selected_up_list:
            print("无UP主可选或选择数量为0。")
            return []

        videos_per_up = play_mode_settings.get('videos_per_up_play_mode', 3)
        
        first_up_for_wbi = next((up for up in selected_up_list if up.get('id')), None)
        if not first_up_for_wbi:
            print("选定的UP主列表中没有任何UP主配置了ID。")
            return []
        
        self.request_handler.get(self.daily_tasks_handler.urls['Space_Arc_Search'], self.user_config['Cookie'],
                                params={'mid': first_up_for_wbi['id'], 'pn': 1, 'ps': 1, 'order':'pubdate','dm_img_list':'[]','dm_cover_img_str':'V2ViRmlsRTMyNw=='}, needs_wbi=True)

        all_videos_raw = []
        for up_conf in selected_up_list:
            mid = up_conf.get('id')
            if not mid: print(f"UP主配置 {up_conf.get('name','未知UP')} 缺少ID，跳过。"); continue

            name = up_conf.get('name') or self.daily_tasks_handler._get_up_name_by_mid(mid, self.user_config['Cookie']) or f"MID:{mid}"
            print(f"从UP '{name}' (ID:{mid}) 获取 {videos_per_up} 个视频...")
            params_search = {'mid': mid, 'pn': 1, 'ps': videos_per_up, 'order':'pubdate','dm_img_list':'[]','dm_cover_img_str':'V2ViRmlsRTMyNw=='}
            resp = self.request_handler.get(self.daily_tasks_handler.urls['Space_Arc_Search'], self.user_config['Cookie'], params=params_search, needs_wbi=True)
            if resp and resp.json().get('code') == 0:
                vlist = resp.json().get('data',{}).get('list',{}).get('vlist',[])
                for v_data in vlist:
                    if 'aid' in v_data:
                         all_videos_raw.append({'aid': str(v_data['aid']), 'title': v_data.get('title', '?'),
                                                'initial_duration_str': str(v_data.get('duration', "0")), 'mid': mid})
            elif resp:
                 print(f"获取UP '{name}' 视频列表失败: {resp.json().get('message','未知错误')}")
            else:
                 print(f"获取UP '{name}' 视频列表请求失败。")
        
        unique_videos = list({v['aid']: v for v in all_videos_raw}.values())
        print(f"共获取到 {len(unique_videos)} 个视频用于播放。")
        return unique_videos

    def _handle_play_mode_reporting(self):
        print("\n--- 解析视频播放上报 ---")
        video_list_raw = self._get_videos_for_play_mode()
        if not video_list_raw: print("无视频可播放。"); return

        chosen_video_raw = random.choice(video_list_raw)
        aid_str, title_raw = chosen_video_raw['aid'], chosen_video_raw['title']
        
        video_details = self.daily_tasks_handler.get_video_details_from_view_api(aid_str, self.user_config['Cookie'])
        if not video_details: print(f"无法获取视频 {aid_str} 的详细信息。"); return

        title, duration_sec = video_details['title'], video_details['duration']
        desc, pic_url = video_details['desc'], video_details['pic_url']
        
        print(f"播放: '{title}' (AID:{aid_str})\n实际时长: {str(timedelta(seconds=duration_sec)) if duration_sec > 0 else '未知'}")
        print(f"简介:\n{desc if desc else '无'}\n封面URL: {pic_url if pic_url else '无'}")

        play_settings = self.user_config.get('PlayMode_Settings', {})
        max_local_wait = play_settings.get('max_play_duration_local_wait', 120)
        
        if max_local_wait <= 0: max_local_wait = 60

        if duration_sec > 0:
            ideal_report_duration = int(duration_sec * random.uniform(0.6, 1.0))
            ideal_report_duration = min(ideal_report_duration, duration_sec) 
        else: 
            actual_rand_max = min(60, max_local_wait)
            ideal_report_duration = random.randint(max(1, min(15, actual_rand_max)), actual_rand_max) if actual_rand_max >=15 else max(1,actual_rand_max)

        local_wait_target = min(ideal_report_duration, max_local_wait)
        if local_wait_target <= 0: local_wait_target = max(1, min(15, max_local_wait))

        print(f"\n计划模拟播放上限: {local_wait_target}s")
        print("按 Ctrl+C 可中断模拟播放")
        elapsed_play_time = 0
        try:
            for i in range(local_wait_target, 0, -1):
                print(f"\r模拟播放: '{title}'. 剩余 {i} 秒...", end=""); time.sleep(1); elapsed_play_time += 1
            print("\n模拟播放计时完成.")
        except KeyboardInterrupt: print("\n模拟播放被中断.")
        
        if elapsed_play_time == 0: print("未模拟有效播放时长，不上报。"); return

        user_choice = input(f"已模拟播放 {elapsed_play_time}s. [1]上报, [2]不上报: ").strip()
        if user_choice == '1':
            data = {"aid": aid_str, "played_time": elapsed_play_time, "csrf": self.user_config['Cookie'].get('bili_jct', '')}
            resp = self.request_handler.post(self.daily_tasks_handler.urls['Watch_Video'], self.user_config['Cookie'], post_data=data)
            if resp and resp.json().get('code') == 0: print(f"上报成功: '{title}' (时长:{elapsed_play_time}s) 🥳")
            else: print(f"上报失败: '{title}' - {resp.json().get('message') if resp else '请求失败'}")
        else: print("用户选择不上报。")
        

    def run(self):
        if not self._initial_user_info_display():
            input("初始化失败，按任意键退出...")
            return
        try:
            while True:
                try:
                    action = self._get_user_action_parser()
                    if action == '1': self._handle_play_mode_reporting()
                    elif action == '2': self._handle_cover_url_parsing()
                    elif action == '0':
                        print("\n用户选择退出。")
                        break 
                    print("\n" + "="*20 + " 操作结束 " + "="*20)
                    time.sleep(1)
                except KeyboardInterrupt: 
                    print("\n当前操作被用户中断。")
                    choice = input("是否退出整个脚本? (y/n): ").strip().lower()
                    if choice == 'y': print("用户选择退出脚本。"); break 
                    else: print("继续执行脚本。"); continue 
                except Exception as e: 
                    print(f"\n操作执行中发生异常: {e}")
                    import traceback; traceback.print_exc()
                    choice = input("发生异常，是否退出整个脚本? (y/n): ").strip().lower()
                    if choice == 'y': print("用户选择因异常退出脚本。"); break
                    else: print("尝试继续执行脚本。"); continue
        finally:
            print("\n脚本执行流程结束。")
            input("按任意键退出...")

if __name__ == "__main__":
    runner = VideoParserScriptRunner()
    runner.run()
