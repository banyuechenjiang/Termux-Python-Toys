import time
import requests_html
import random
import yaml
import sys
import os
import hashlib
from urllib.parse import urlencode
import math
import json
from datetime import datetime, timedelta

#pip install requests_html
#pip install lxml_html_clean
#Termux安装可能需要参考https://www.zhihu.com/question/493575333

CONFIG_YAML_CONTENT = """
User_Cookie:
  - "请填写自己的"

  
Appoint_Up:
  - id: "87031209"
  - id: "3493265644980448"
    name: "碧蓝档案"
  - id: "476491780"
"""

MIN_COIN_FOR_PUTTING = 200
VIDEOS_PER_UP_TO_FETCH = 10
HTML_SESSION = requests_html.HTMLSession()

class WbiManager:
    MIXIN_KEY_ENC_TAB = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
        33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
        61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
        36, 20, 34, 44, 52
    ]
    def __init__(self, request_handler_func):
        self.img_key = None
        self.sub_key = None
        self._request_handler_func = request_handler_func

    def _get_wbi_keys_internal(self, cookies_for_nav_api):
        nav_url = "https://api.bilibili.com/x/web-interface/nav"
        resp = self._request_handler_func(nav_url, cookies_for_nav_api)
        if resp and resp.status_code == 200:
            json_data = resp.json()
            if json_data.get("code") == 0:
                wbi_img = json_data.get("data", {}).get("wbi_img", {})
                img_url = wbi_img.get("img_url", "")
                sub_url = wbi_img.get("sub_url", "")
                if img_url and sub_url:
                    self.img_key = img_url.split('/')[-1].split('.')[0]
                    self.sub_key = sub_url.split('/')[-1].split('.')[0]
                    return True
        print("警告: 获取WBI密钥失败或未能从响应中提取。")
        return False

    def _refresh_wbi_keys_internal(self, cookies_for_nav_api):
        return self._get_wbi_keys_internal(cookies_for_nav_api)

    def get_mixin_key(self, orig_key: str):
        return ''.join([orig_key[i] for i in self.MIXIN_KEY_ENC_TAB])[:32]

    def encode_wbi_params(self, params: dict, cookies_for_nav_api: dict):
        if not self.img_key or not self.sub_key:
            print("尝试刷新WBI密钥...")
            if not self._refresh_wbi_keys_internal(cookies_for_nav_api):
                 print("错误: 刷新WBI密钥后仍不可用，无法签名。")
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
                print("运行错误: 内嵌配置中User_Cookie无效或缺失。")
                sys.exit(1)
            return config_data
        except yaml.YAMLError as e: print(f"内嵌配置解析错误: {e}"); sys.exit(1)
        except IndexError: print("运行错误: User_Cookie列表为空。"); sys.exit(1)

    def _handle_single_cookie_str(self, cookie_str: str) -> dict:
        if not cookie_str or not isinstance(cookie_str, str): return {}
        return {p.split("=", 1)[0].strip(): p.split("=", 1)[1].strip() for p in cookie_str.split(";") if "=" in p}

    def _process_user_config(self, raw_config_data: dict) -> dict:
        user_conf = {}
        parsed_cookie = self._handle_single_cookie_str(raw_config_data["User_Cookie"][0])
        if not parsed_cookie: print("Cookie解析失败或为空。"); sys.exit(1)
        user_conf['Cookie'] = parsed_cookie
        raw_appoint_up_config = raw_config_data.get('Appoint_Up')
        processed_appoint_up = []
        if isinstance(raw_appoint_up_config, list):
            for item in raw_appoint_up_config:
                if isinstance(item, dict) and 'id' in item and str(item['id']).strip().isdigit():
                    entry = {'id': str(item['id']).strip()}
                    if 'name' in item and isinstance(item['name'], str) and item['name'].strip():
                        entry['name'] = item['name'].strip()
                    processed_appoint_up.append(entry)
                elif isinstance(item, (str, int)) and str(item).strip().isdigit():
                    processed_appoint_up.append({'id': str(item).strip()})
        user_conf['Up'] = processed_appoint_up
        return user_conf

    def get_config(self): return self.user_config

class BiliRequest:
    def __init__(self):
        self.default_headers = {
            "User-Agent": requests_html.UserAgent().random,
            "Referer": "https://www.bilibili.com/",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
        self.wbi_manager = WbiManager(self._raw_get_for_wbi)

    def _raw_get_for_wbi(self, url, cookies, **kwargs):
        headers = {**self.default_headers, **kwargs.pop('headers', {})}
        try:
            res = HTML_SESSION.get(url=url, headers=headers, cookies=cookies, timeout=10, **kwargs)
            res.raise_for_status(); return res
        except requests_html.requests.exceptions.RequestException: return None

    def get(self, url: str, cookies: dict, params:dict=None, needs_wbi:bool=False, **kwargs) -> requests_html.HTMLResponse | None:
        headers = {**self.default_headers, **kwargs.pop('headers', {})}
        current_params = params.copy() if params else {}
        if needs_wbi:
            current_params = self.wbi_manager.encode_wbi_params(current_params, cookies)
            if 'w_rid' not in current_params: return None
        query_string = urlencode(current_params) if current_params else ""
        full_url = f"{url}?{query_string}" if query_string else url
        try:
            res = HTML_SESSION.get(url=full_url, headers=headers, cookies=cookies, timeout=10, **kwargs)
            res.raise_for_status(); return res
        except requests_html.requests.exceptions.RequestException as e:
            print(f"GET请求失败: {full_url}, 错误: {e}"); return None

    def post(self, url: str, cookies: dict, post_data: dict, **kwargs) -> requests_html.HTMLResponse | None:
        headers = {**self.default_headers, **kwargs.pop('headers', {})}
        try:
            res = HTML_SESSION.post(url=url, headers=headers, cookies=cookies, data=post_data, timeout=10, **kwargs)
            res.raise_for_status(); return res
        except requests_html.requests.exceptions.RequestException as e:
            print(f"POST请求失败: {url}, 错误: {e}"); return None

class UserHandler:
    def __init__(self, request_handler: BiliRequest):
        self.request_handler = request_handler
        self.urls = {"Bili_UserData": "http://api.bilibili.com/x/space/myinfo",
                     "Daily_Reward_Status": "https://api.bilibili.com/x/member/web/exp/reward"}

    def get_user_data(self, cookie: dict) -> tuple[str, int, int, int, int, bool]:
        default_return = ("未知", 0, 0, 0, 0, True)
        if not cookie: print("Cookie为空。"); return default_return
        response = self.request_handler.get(self.urls['Bili_UserData'], cookie)
        if not response: return default_return
        try:
            res_json = response.json()
            if res_json.get('code') == -101: print("Cookie错误或已失效"); return default_return
            if res_json.get('code') != 0: print(f"获取用户信息API失败: {res_json.get('message')}"); return default_return
            d = res_json.get('data', {})
            name, mid = d.get('name','未知用户'), d.get('mid',0)
            coins_raw = d.get('coins',0); current_coins = int(float(coins_raw)) if str(coins_raw).replace('.','',1).isdigit() else 0
            level = d.get('level',0)
            profile_exp = d.get('level_exp',{}).get('current_exp',0)
            is_lv6 = level >= 6
            print(f"用户名: {name}\nUID: {mid}\n当前硬币数量: {str(coins_raw)} 个\n当前等级: LV {level}\n当前总经验值: {profile_exp}")
            if not is_lv6:
                next_exp_val = d.get('level_exp',{}).get('next_exp')
                if next_exp_val is not None and next_exp_val != -1:
                    print(f"下一级所需经验: {int(next_exp_val)}\n距离升级还需经验: {max(0, int(next_exp_val) - profile_exp)}")
            else: print("用户已达最高等级 (LV6)。")
            return name, mid, level, profile_exp, current_coins, is_lv6
        except Exception as e: print(f"处理用户信息响应错误: {e}"); return default_return

    def get_daily_reward_status(self, cookie: dict) -> dict:
        default_status = {'login': False, 'watch': False, 'share': False, 'coins_exp': 0, 'total_exp_today': 0, 'message': '获取失败'}
        if not cookie: return default_status
        response = self.request_handler.get(self.urls['Daily_Reward_Status'], cookie)
        if response:
            try:
                res_json = response.json()
                if res_json.get('code') == 0:
                    data = res_json.get('data', {})
                    status = {
                        'login': data.get('login', False),
                        'watch': data.get('watch', False),
                        'share': data.get('share', False),
                        'coins_exp': data.get('coins', 0)
                    }
                    status['total_exp_today'] = (5 if status['login'] else 0) + \
                                              (5 if status['watch'] else 0) + \
                                              (5 if status['share'] else 0) + \
                                              status['coins_exp']
                    status['message'] = '获取成功'
                    return status
                else:
                    default_status['message'] = res_json.get('message', 'API返回错误但无消息')
                    print(f"获取每日奖励状态失败: {default_status['message']}")
            except Exception as e:
                default_status['message'] = str(e)
                print(f"解析每日奖励状态响应错误: {e}")
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
        params = {'mid': mid}
        response = self.request_handler.get(self.urls['Space_Acc_Info'], cookie, params=params)
        if response and response.json().get('code') == 0:
            name = response.json()['data']['name']
            self._up_name_cache[mid] = name; return name
        return None

    def _check_video_coin_status(self, cookie: dict, aid: str) -> int:
        if not cookie or not aid: return -1
        params = {'aid': aid}
        response = self.request_handler.get(self.urls['Archive_Relation'], cookie, params=params)
        if response and response.json().get('code') == 0: return response.json()['data'].get('coin', 0)
        return -1

    def _parse_duration_str_to_seconds(self, duration_str: str) -> int:
        if isinstance(duration_str, int): return duration_str
        if not isinstance(duration_str, str) or not duration_str: return 0
        parts = list(map(int, duration_str.split(':')))
        if len(parts) == 3: return parts[0]*3600 + parts[1]*60 + parts[2]
        if len(parts) == 2: return parts[0]*60 + parts[1]
        if len(parts) == 1 and duration_str.isdigit(): return parts[0]
        return 0

    def _get_video_details_from_view_api(self, aid: str, cookie: dict) -> dict | None:
        print(f"尝试通过View API获取视频 AID:{aid} 的详细信息...")
        params = {'aid': aid}
        response = self.request_handler.get(self.urls['Video_View_Info'], cookie, params=params)
        if response and response.json().get('code') == 0:
            data = response.json().get('data', {})
            title = data.get('title', '未知标题 (View API)')
            duration = data.get('duration', 0)
            desc = data.get('desc', '')
            pic_url = data.get('pic', '')
            print(f"View API获取成功: '{title}', 时长: {duration}s")
            return {'title': title, 'duration': duration, 'desc': desc, 'pic_url': pic_url}
        print(f"View API获取视频 AID:{aid} 详细信息失败。")
        return None

    def get_videos_for_tasks_with_details(self, cookie: dict, up_preference_list: list) -> list:
        print("\n#正在获取任务视频列表#")
        print(f"视频获取方式: 仅从指定的UP主列表中获取")
        if isinstance(up_preference_list, list) and up_preference_list:
            mid_for_precheck = up_preference_list[0].get('id')
            if mid_for_precheck:
                self.request_handler.get(self.urls['Space_Arc_Search'], cookie,
                                         params={'mid': mid_for_precheck, 'pn': 1, 'ps': 1,
                                                 'order': 'pubdate', 'dm_img_list':'[]',
                                                 'dm_cover_img_str':'V2ViRmlsRTMyNw=='}, needs_wbi=True)

        all_collected_videos_raw = []
        if isinstance(up_preference_list, list) and up_preference_list:
            for up_config in up_preference_list:
                mid = up_config.get('id')
                display_name = up_config.get('name') or self._get_up_name_by_mid(mid, cookie) or f"MID:{mid}"
                print(f"尝试从UP主 '{display_name}' (ID: {mid}) 获取视频...")
                params = {'mid': mid, 'pn': 1, 'ps': VIDEOS_PER_UP_TO_FETCH,
                          'order': 'pubdate', 'dm_img_list':'[]','dm_cover_img_str':'V2ViRmlsRTMyNw=='}
                resp = self.request_handler.get(self.urls['Space_Arc_Search'], cookie, params=params, needs_wbi=True)
                if resp and resp.json().get('code') == 0:
                    vlist = resp.json().get('data',{}).get('list',{}).get('vlist',[])
                    for i in vlist:
                        if 'aid' in i:
                            all_collected_videos_raw.append({
                                'aid': str(i['aid']),
                                'title': i.get('title', '未知标题'),
                                'initial_duration_str': str(i.get('duration', "0"))
                            })
                    print(f"从UP主 '{display_name}' 获取到原始视频数量: {len(vlist)} 个")

            unique_collected_videos = {v['aid']: v for v in all_collected_videos_raw}.values()
            processed_videos = []
            print(f"\n开始处理 {len(unique_collected_videos)} 个视频的投币状态...")
            for video_raw in unique_collected_videos:
                coin_status = self._check_video_coin_status(cookie, video_raw['aid'])
                initial_duration_sec = self._parse_duration_str_to_seconds(video_raw['initial_duration_str'])
                if coin_status == 0:
                    processed_videos.append({
                        'aid': video_raw['aid'],
                        'title': video_raw['title'],
                        'initial_duration_sec': initial_duration_sec,
                        'desc': '',
                        'pic_url': ''
                    })

            if processed_videos: print(f"共获取到可用任务视频数量: {len(processed_videos)} 个 (已去除已投币视频)")
            else: print("未能从指定UP主处获取到任何未投币的视频。")
            return processed_videos
        return []

    def share_video(self, cookie: dict, video_list: list) -> bool:
        print("\n#正在进行分享视频任务#")
        if not cookie or not video_list: print("Cookie或视频列表缺失，跳过。"); return True

        chosen_video = random.choice(video_list)
        aid, title = chosen_video['aid'], chosen_video['title']
        csrf = cookie.get('bili_jct', '')
        if not csrf: print("分享失败: Cookie缺bili_jct"); return False
        print(f"尝试分享视频 '{title}' (AID: {aid})")
        resp = self.request_handler.post(self.urls['Share_Video'], cookie, {"aid": aid, "csrf": csrf})
        if resp and resp.json().get('code') == 0: print(f"分享视频 '{title}' 完成 🥳"); time.sleep(random.randint(10,25)); return True
        elif resp and resp.json().get('code') == 71000: print(f"视频 '{title}' 今日已分享过 😫"); return True
        else: print(f"分享失败: '{title}' - {resp.json().get('message') if resp else '请求失败'}"); return False

    def watch_video(self, cookie: dict, video_list: list, is_play_mode: bool) -> bool:
        print(f"\n#正在进行{'测试视频播放上报' if is_play_mode else '观看视频任务'}#")
        if not cookie or not video_list: print("Cookie或视频列表缺失，跳过。"); return True

        chosen_video_obj = random.choice(video_list)
        aid, original_title = chosen_video_obj['aid'], chosen_video_obj['title']
        actual_duration_sec = chosen_video_obj['initial_duration_sec']
        current_title = original_title
        current_desc = chosen_video_obj.get('desc','')
        current_pic_url = chosen_video_obj.get('pic_url', '')


        if is_play_mode or actual_duration_sec <= 0:
            fetched_details = self._get_video_details_from_view_api(aid, cookie)
            if fetched_details:
                actual_duration_sec = fetched_details['duration']
                current_title = fetched_details['title']
                current_desc = fetched_details['desc']
                current_pic_url = fetched_details['pic_url']
                chosen_video_obj['desc'] = current_desc
                chosen_video_obj['pic_url'] = current_pic_url


        if actual_duration_sec > 0:
            ideal_report_duration = int(actual_duration_sec * random.uniform(0.6, 1.0))
        else:
            ideal_report_duration = random.randint(15, 60)
            print(f"视频 '{current_title}' (AID:{aid}) 无法获取精确时长或初始时长为0，将使用随机时长。")

        actual_duration_str = str(timedelta(seconds=actual_duration_sec)) if actual_duration_sec > 0 else "未知"
        desc_preview = (current_desc[:70] + '...') if current_desc and len(current_desc) > 70 else current_desc

        if is_play_mode:
            local_wait_time = min(ideal_report_duration, 45)
            final_report_time = local_wait_time
            print(f"观看: '{current_title}' (AID:{aid})\n实际时长: {actual_duration_str}")
            if desc_preview: print(f"简介: {desc_preview}")
            if current_pic_url: print(f"封面URL: {current_pic_url}")
            print(f"计划上报(基于视频长度): {ideal_report_duration}s, 最终上报/本地等待: {final_report_time}s (Play模式)")
        else:
            final_report_time = max(15, min(ideal_report_duration, 300))
            local_wait_time = final_report_time
            print(f"观看: '{current_title}' (AID:{aid}), 计划上报时长:{final_report_time}s (获取经验), 本地等待: {local_wait_time}s")

        time.sleep(local_wait_time)
        data = {"aid": aid, "played_time": final_report_time, "csrf": cookie.get('bili_jct', '')}

        resp = self.request_handler.post(self.urls['Watch_Video'], cookie, data)
        if resp and resp.json().get('code') == 0:
            print(f"上报成功: '{current_title}' 🥳")
            if not is_play_mode: time.sleep(random.randint(10,25))
            return True
        else: print(f"上报失败: '{current_title}' - {resp.json().get('message') if resp else '请求失败'}"); return False

    def coin_videos(self, cookie: dict, video_list: list, current_user_coins: int, current_coins_exp_from_api: int, total_exp_today_from_api: int) -> bool:
        print("\n#正在进行视频投币任务#")
        if not cookie or not video_list: print("Cookie或视频列表缺失，跳过。"); return True
        if current_user_coins < MIN_COIN_FOR_PUTTING: print(f"硬币({current_user_coins})不足{MIN_COIN_FOR_PUTTING}。"); return True

        csrf = cookie.get('bili_jct', '')
        if not csrf: print("投币失败: Cookie缺bili_jct"); return False

        if current_coins_exp_from_api >= 50:
            print(f"今日通过投币已获得经验: {current_coins_exp_from_api} / 50。无需再投币。")
            return True
        if total_exp_today_from_api >= 65:
            print(f"今日总任务经验已达 {total_exp_today_from_api} / 65。无需再投币以获取经验。")
            return True

        exp_needed_from_coins_to_reach_50_cap = 50 - current_coins_exp_from_api
        exp_room_before_65_total_cap = 65 - total_exp_today_from_api

        actual_exp_target_from_coins = min(exp_needed_from_coins_to_reach_50_cap, exp_room_before_65_total_cap)
        ops_to_attempt = min(math.ceil(actual_exp_target_from_coins / 10), 5)


        if ops_to_attempt <= 0: print("计算后无需投币或已达经验上限。"); return True
        print(f"目标投币次数: {ops_to_attempt} (当前投币经验: {current_coins_exp_from_api}/50, 当前总任务经验: {total_exp_today_from_api}/65)")

        coins_thrown_this_run = 0
        shuffled_videos = random.sample(video_list, k=min(len(video_list), ops_to_attempt + 2))

        for i in range(ops_to_attempt):
            if not shuffled_videos: print("已无可用视频投币。"); break
            if current_user_coins < 1 : print("硬币不足。"); break

            video_obj = shuffled_videos.pop(0)
            aid, title = video_obj['aid'], video_obj['title']
            data = {'aid': aid, 'multiply': 1, 'select_like': 1, 'cross_domain': 'true', 'csrf': csrf}
            print(f"尝试向 '{title}' (av{aid}) 投1币并点赞...")
            resp = self.request_handler.post(self.urls['Put_Coin'], cookie, data)
            if resp and resp.json().get('code') == 0:
                print(f"投币成功: '{title}' 💿")
                coins_thrown_this_run += 1; current_user_coins -=1
                if i < ops_to_attempt - 1: time.sleep(random.randint(15,45))
            elif resp: print(f"投币异常: '{title}' - {resp.json().get('message')}")
            else: print(f"投币请求失败: '{title}'")

        if coins_thrown_this_run > 0: print(f"本轮共投出 {coins_thrown_this_run} 枚硬币。")
        return True

class ScriptRunner:
    def __init__(self):
        self.config_manager = ConfigManager(CONFIG_YAML_CONTENT)
        self.user_config = self.config_manager.get_config()
        self.request_handler = BiliRequest()
        self.user_handler = UserHandler(self.request_handler)
        self.daily_tasks_handler = DailyTasks(self.request_handler)
        self.current_user_data = {}

    def _update_current_reward_status(self):
        reward_status = self.user_handler.get_daily_reward_status(self.user_config['Cookie'])
        self.current_user_data['reward_status'] = reward_status
        self.current_user_data['login_done'] = reward_status.get('login', False)
        self.current_user_data['watch_done'] = reward_status.get('watch', False)
        self.current_user_data['share_done'] = reward_status.get('share', False)
        self.current_user_data['coins_exp_today'] = reward_status.get('coins_exp', 0)
        self.current_user_data['total_task_exp_today'] = reward_status.get('total_exp_today', 0)
        return reward_status


    def _initial_user_info_and_reward_status_display(self):
        print("\n" + "#"*50 + "\n#" + " "*10 + "B站日常任务脚本" + " "*10 + "#\n" + "#"*50)
        name, uid, level, profile_exp, coins, is_lv6 = self.user_handler.get_user_data(self.user_config['Cookie'])
        self.current_user_data.update({'name': name, 'uid': uid, 'level': level,
                                  'profile_exp': profile_exp, 'coins': coins, 'is_lv6': is_lv6})

        if uid != 0:
            reward_status = self._update_current_reward_status()
            print(f"\n--- 每日任务状态 (来自API /get/reward) ---")
            print(f"每日登录完成: {'是' if reward_status.get('login') else '否'} (5 Exp)")
            print(f"每日观看完成: {'是' if reward_status.get('watch') else '否'} (5 Exp)")
            print(f"每日分享完成: {'是' if reward_status.get('share') else '否'} (5 Exp)")
            print(f"今日投币获得经验: {reward_status.get('coins_exp',0)} / 50 Exp")
            print(f"今日已通过任务获得总经验: {reward_status.get('total_exp_today',0)} / 65 Exp")
            if reward_status.get('message') != '获取成功' : print(f"获取奖励状态提示: {reward_status.get('message')}")
        print("-" * 50)

    def _get_user_action(self) -> str:
        while True:
            try:
                action = input("\n选择操作: \n[1]执行日常任务 \n[2]测试视频播放 \n[0]退出 : ").strip()
                if action in ['0', '1', '2']: return action
                print("无效输入，请重试。")
            except EOFError: return '0'

    def _handle_daily_tasks(self):
        print("\n--- 执行日常任务 ---")
        current_reward_status = self.current_user_data.get('reward_status', {})
        total_task_exp = current_reward_status.get('total_exp_today', 0)

        if self.current_user_data.get('is_lv6'):
            print(f"用户等级 LV {self.current_user_data['level']} 已满级，跳过所有经验任务。")
            return

        if total_task_exp >= 65:
            print("今日所有日常任务经验已达上限(65)。无需执行。")
            return

        print("需要执行日常任务以获取经验。")
        video_list = self.daily_tasks_handler.get_videos_for_tasks_with_details(self.user_config['Cookie'], self.user_config.get('Up'))
        if not video_list: print("\n未能获取到可用视频列表，无法执行依赖视频的任务。"); return


        if not current_reward_status.get('share', False) and total_task_exp < 65 :
            print("尝试执行分享任务...")
            if self.daily_tasks_handler.share_video(self.user_config['Cookie'], video_list):
                current_reward_status = self._update_current_reward_status()
                total_task_exp = current_reward_status.get('total_exp_today',0)
        else:
            print("分享任务已完成或总经验已达上限，跳过分享。")


        if not current_reward_status.get('watch', False) and total_task_exp < 65 :
            print("尝试执行观看任务 (同时完成登录任务)...")
            if self.daily_tasks_handler.watch_video(self.user_config['Cookie'], video_list, is_play_mode=False):
                current_reward_status = self._update_current_reward_status()
                total_task_exp = current_reward_status.get('total_exp_today',0)
        else:
            print("观看/登录任务已完成或总经验已达上限，跳过观看。")


        coins_exp_today = current_reward_status.get('coins_exp',0)
        if coins_exp_today < 50 and total_task_exp < 65 :
             print("尝试执行投币任务...")
             self.daily_tasks_handler.coin_videos(self.user_config['Cookie'], video_list,
                                             self.current_user_data['coins'], coins_exp_today, total_task_exp)
             self._update_current_reward_status()
        else:
            print("投币任务经验已满(API回报投币经验>=50)，或总经验已达上限，跳过投币。")


    def _handle_play_mode(self):
        print("\n--- 测试视频播放上报 ---")
        video_list = self.daily_tasks_handler.get_videos_for_tasks_with_details(self.user_config['Cookie'], self.user_config.get('Up'))
        if not video_list: print("\n未能获取到可用视频列表，无法测试播放。"); return
        self.daily_tasks_handler.watch_video(self.user_config['Cookie'], video_list, is_play_mode=True)
        self._update_current_reward_status()

    def run(self):
        while True:
            try:
                self._initial_user_info_and_reward_status_display()
                if self.current_user_data.get('uid') == 0:
                    print("无法获取用户信息，脚本终止。")
                    break

                action = self._get_user_action()

                if action == '1': self._handle_daily_tasks()
                elif action == '2': self._handle_play_mode()
                elif action == '0': print("\n用户选择退出。"); break

                print("\n" + "="*30 + " 操作结束 " + "="*30)
                time.sleep(1)
            except KeyboardInterrupt:
                print("\n脚本被用户中断 (Ctrl+C)。正在退出...")
                break
            except Exception as e:
                print(f"\n发生未处理的异常: {e}")
                import traceback
                traceback.print_exc()
                print("脚本因异常终止。")
                break

if __name__ == "__main__":
    runner = ScriptRunner()
    runner.run()
