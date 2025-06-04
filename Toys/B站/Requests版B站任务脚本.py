import time
import random
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
    
    
Manga_Task:
  Enabled: true
  Read_Target:
    comic_id: "27355"
    ep_id: "381662"
    title: "堀与宫村"
Watch_Task_Settings:
  Wait_Time_Min: 3
  Wait_Time_Max: 28
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
        print("WBI密钥获取失败."); return False

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
        raw_watch_task_settings = raw_config_data.get('Watch_Task_Settings', {})
        user_conf['Watch_Task_Settings'] = {
            'Wait_Time_Min': int(raw_watch_task_settings.get('Wait_Time_Min', 3)),
            'Wait_Time_Max': int(raw_watch_task_settings.get('Wait_Time_Max', 28))}
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

    def post(self, url: str, cookies: dict, params: dict = None, post_data: dict = None, **kwargs) -> requests.Response | None:
        headers_to_use = {**self.default_headers, **kwargs.pop('headers', {})}
        final_url = f"{url}?{urlencode(params)}" if params and isinstance(params, dict) else url
        try:
            res = self.html_session.post(url=final_url, headers=headers_to_use, cookies=cookies, data=post_data, timeout=15, **kwargs)
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
            name=d.get('name','未知用户'); mid=d.get('mid',0); level=d.get('level',0)
            coins_raw=d.get('coins',0); coins=int(float(coins_raw)) if str(coins_raw).replace('.','',1).isdigit() else 0
            exp=d.get('level_exp',{}).get('current_exp',0); is_lv6 = level >= 6
            print(f"用户名: {name}\nUID: {mid}\n当前等级: LV {level}\n当前硬币: {coins} 个\n当前经验: {exp}")
            if not is_lv6:
                next_exp_val = d.get('level_exp',{}).get('next_exp')
                if next_exp_val is not None and next_exp_val != -1:
                    print(f"下级所需: {int(next_exp_val)}\n仍需经验: {max(0, int(next_exp_val) - exp)}")
            elif level >=6 : print("用户已达最高等级 (LV6+).")
            return name, mid, level, exp, coins, is_lv6, True
        except Exception as e: print(f"用户信息响应错误: {e}"); return default_return

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

class DailyTasks:
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
                    'aid': str(data.get('aid')), 'bvid': data.get('bvid','')}
        return None

    def get_videos_for_tasks(self, cookie: dict, up_preference_list: list, for_coin_task: bool) -> list:
        print("\n#获取任务视频列表#")
        if not up_preference_list: print("UP主列表为空."); return []
        first_up_with_id = next((up for up in up_preference_list if up.get('id')), None)
        if not first_up_with_id: print("UP主列表中没有任何UP主配置了ID。"); return []
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
                        video_entry = {'aid':str(v_data['aid']),'title':v_data.get('title','?'),
                                       'initial_duration_str':str(v_data.get('length',"0")),'mid':mid}
                        if not for_coin_task or self._check_video_coin_status(cookie, video_entry['aid']) == 0:
                            collected_videos.append(video_entry)
            elif resp: print(f"获取UP '{name}' 视频列表失败: {resp.json().get('message','未知错误')}")
            else: print(f"获取UP '{name}' 视频列表请求失败。")
        unique_videos = list({v['aid']:v for v in collected_videos}.values())
        print(f"获取到 {len(unique_videos)} 个{'未投币' if for_coin_task else ''}视频.")
        return unique_videos

    def share_video(self, cookie: dict, video_list: list) -> bool:
        print("\n#视频分享任务#")
        if not video_list: print("无视频可分享."); return True
        v=random.choice(video_list); aid,title,csrf=v['aid'],v['title'],cookie.get('bili_jct','')
        if not csrf: print("分享失败:缺bili_jct"); return False
        print(f"分享视频 '{title}' (AID:{aid})")
        resp = self.request_handler.post(self.urls['Share_Video'],cookie,post_data={"aid":aid,"csrf":csrf})
        if resp and resp.json().get('code')==0: print(f"分享 '{title}' 完成 🥳"); time.sleep(random.randint(3,7)); return True
        elif resp and resp.json().get('code')==71000: print(f"'{title}' 今日已分享过 😫"); return True
        else: print(f"分享失败 '{title}': {resp.json().get('message','无API消息') if resp else '请求错误'}"); return False

    def watch_video(self, cookie: dict, video_list: list, min_wait: int, max_wait: int) -> bool:
        print("\n#观看视频任务#")
        if not video_list: print("无视频可观看."); return True
        v_raw=random.choice(video_list); aid,title_raw=v_raw['aid'],v_raw['title']
        v_details=self.get_video_details_from_view_api(aid,cookie)
        title=title_raw; actual_duration_sec=0
        if v_details: title=v_details['title']; actual_duration_sec=v_details['duration']
        else: actual_duration_sec=self._parse_duration_str_to_seconds(v_raw['initial_duration_str'])
        local_wait_time=random.randint(min_wait,max_wait); report_time=local_wait_time
        if actual_duration_sec > 0: report_time=min(local_wait_time,actual_duration_sec)
        print(f"观看: '{title}' (AID:{aid}), 上报/等待时长:{report_time}s")
        time.sleep(report_time)
        data={"aid":aid,"played_time":report_time,"csrf":cookie.get('bili_jct','')}
        resp=self.request_handler.post(self.urls['Watch_Video'],cookie,post_data=data)
        if resp and resp.json().get('code')==0: print(f"上报成功: '{title}' 🥳"); time.sleep(random.randint(3,7)); return True
        else: print(f"上报失败 '{title}': {resp.json().get('message','无API消息') if resp else '请求错误'}"); return False

    def coin_videos(self, cookie: dict, video_list: list, coins_bal: int, coins_exp: int, total_exp: int) -> bool:
        print("\n#视频投币任务#")
        if coins_bal<MIN_COIN_FOR_PUTTING: print(f"硬币({coins_bal})不足{MIN_COIN_FOR_PUTTING}."); return True
        if coins_exp>=50 or total_exp>=65: print("投币经验已满或总经验已达上限."); return True
        csrf=cookie.get('bili_jct',''); ops_needed=min(math.ceil((min(50-coins_exp,65-total_exp))/10),5)
        if not csrf or ops_needed<=0: print("无需投币或缺bili_jct."); return True
        print(f"目标投币次数: {ops_needed} (当前投币Exp:{coins_exp}/50, 总Exp:{total_exp}/65)")
        shuffled_videos=random.sample(video_list,k=min(len(video_list),ops_needed+2))
        thrown=0
        for _ in range(ops_needed):
            if not shuffled_videos or coins_bal<1: break
            v=shuffled_videos.pop(0); aid,title=v['aid'],v['title']
            print(f"向 '{title}' (av{aid}) 投1币并点赞...")
            resp=self.request_handler.post(self.urls['Put_Coin'],cookie,post_data={'aid':aid,'multiply':1,'select_like':1,'cross_domain':'true','csrf':csrf})
            if resp and resp.json().get('code')==0: print(f"投币成功: '{title}' 💿"); thrown+=1; coins_bal-=1; time.sleep(random.randint(7,15))
            else: print(f"投币异常 '{title}': {resp.json().get('message','无API消息') if resp else '请求错误'}")
        if thrown>0: print(f"本轮共投出 {thrown} 枚硬币.")
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

class DailyScriptRunner:
    def __init__(self):
        self.config_manager = ConfigManager(CONFIG_YAML_CONTENT)
        self.user_config = self.config_manager.get_config()
        self.request_handler = BiliRequest()
        self.user_handler = UserHandler(self.request_handler)
        self.daily_tasks_handler = DailyTasks(self.request_handler)
        self.manga_task_handler = MangaTaskHandler(self.request_handler, self.user_config.get('Manga_Task', {}))
        self.current_user_data = {}

    def _initial_user_info_and_reward_status_display(self) -> bool:
        print("\n" + "#"*15 + " B站日常任务 " + "#"*15)
        name,uid,_,_,coins,is_lv6,success = self.user_handler.get_user_data(self.user_config['Cookie'])
        if not success or uid == 0: return False
        self.current_user_data.update({'name':name,'uid':uid,'coins':coins,'is_lv6':is_lv6})
        reward_status = self.user_handler.get_daily_reward_status(self.user_config['Cookie'])
        self.current_user_data['reward_status'] = reward_status
        print(f"\n--- 每日任务状态 ---")
        print(f"登录: {'是' if reward_status.get('login') else '否'} (+5 Exp)")
        print(f"观看: {'是' if reward_status.get('watch') else '否'} (+5 Exp)")
        print(f"分享: {'是' if reward_status.get('share') else '否'} (+5 Exp)")
        print(f"投币Exp: {reward_status.get('coins_exp',0)}/50 Exp")
        print(f"总任务Exp: {reward_status.get('total_exp_today',0)}/65 Exp")
        print("-" * 40); return True

    def _handle_daily_tasks_and_manga(self):
        is_lv6 = self.current_user_data.get('is_lv6', True)
        
        reward_status_after_video_tasks = self.current_user_data.get('reward_status', {}).copy()
        total_exp_after_video_tasks = reward_status_after_video_tasks.get('total_exp_today', 0)
        coins_exp_after_video_tasks = reward_status_after_video_tasks.get('coins_exp', 0)

        if is_lv6:
            print("\n用户已满级LV6,跳过经验相关视频任务.")
        elif total_exp_after_video_tasks >= 65:
            print("\n今日所有日常任务经验已达上限(65),跳过经验相关视频任务.")
        else: 
            general_videos = self.daily_tasks_handler.get_videos_for_tasks(self.user_config['Cookie'], self.user_config.get('Up',[]), for_coin_task=False)
            
            if not reward_status_after_video_tasks.get('share', False) and total_exp_after_video_tasks < 65:
                self.daily_tasks_handler.share_video(self.user_config['Cookie'], general_videos)
                reward_status_after_video_tasks = self.user_handler.get_daily_reward_status(self.user_config['Cookie']) 
                total_exp_after_video_tasks = reward_status_after_video_tasks.get('total_exp_today',0)
                coins_exp_after_video_tasks = reward_status_after_video_tasks.get('coins_exp', 0)
            else:
                print("\n分享任务已完成或总经验达上限,跳过.")

            if not reward_status_after_video_tasks.get('watch', False) and total_exp_after_video_tasks < 65: 
                watch_cfg = self.user_config.get('Watch_Task_Settings', {})
                min_w, max_w = watch_cfg.get('Wait_Time_Min', 3), watch_cfg.get('Wait_Time_Max', 28)
                self.daily_tasks_handler.watch_video(self.user_config['Cookie'], general_videos, min_w, max_w)
                reward_status_after_video_tasks = self.user_handler.get_daily_reward_status(self.user_config['Cookie']) 
                total_exp_after_video_tasks = reward_status_after_video_tasks.get('total_exp_today',0)
                coins_exp_after_video_tasks = reward_status_after_video_tasks.get('coins_exp', 0)
            else:
                print("\n观看/登录任务已完成或总经验达上限,跳过.")
            
            if coins_exp_after_video_tasks < 50 and total_exp_after_video_tasks < 65:
                coin_videos = self.daily_tasks_handler.get_videos_for_tasks(self.user_config['Cookie'], self.user_config.get('Up',[]), for_coin_task=True)
                self.daily_tasks_handler.coin_videos(self.user_config['Cookie'], coin_videos, self.current_user_data.get('coins',0), coins_exp_after_video_tasks, total_exp_after_video_tasks)
                reward_status_after_video_tasks = self.user_handler.get_daily_reward_status(self.user_config['Cookie']) 
                total_exp_after_video_tasks = reward_status_after_video_tasks.get('total_exp_today',0)
            else:
                print("\n投币任务经验已满或总经验达上限,跳过.")
        
        if total_exp_after_video_tasks >= 65:
            print("\n今日所有日常任务经验已达上限(65),跳过漫画任务.")
        else:
            self.manga_task_handler.perform_clock_in(self.user_config['Cookie'])
            self.manga_task_handler.perform_manga_read(self.user_config['Cookie'])

    def run(self):
        try:
            if not self._initial_user_info_and_reward_status_display():
                print("无法获取用户信息,脚本终止."); return
            self._handle_daily_tasks_and_manga()
            print("\n" + "="*15 + " 所有任务执行完毕 " + "="*15)
        except KeyboardInterrupt: print("\n脚本被用户中断.")
        except Exception as e: print(f"\n发生异常: {e}"); import traceback; traceback.print_exc()
        finally: input("按任意键退出...")

if __name__ == "__main__":
    runner = DailyScriptRunner()
    runner.run()
