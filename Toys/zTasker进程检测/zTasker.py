import psutil
import os
import sys
import datetime
import time
import pylnk3 
from msvcrt import kbhit, getch
import subprocess

PREFERRED_PROGRAMS = ["zTasker.exe", "everything.exe", "clash-verge.exe"]
REPORT_INTERVAL_SECONDS = 300
# REPORT_INTERVAL_SECONDS = 10 

DEBUG_SHORTCUT_SCAN = False
DEBUG_PROCESS_FINDING = False

EXPECTED_USER_NAME_IN_PATH = "】" 
POTENTIALLY_MISENCODED_USER_FRAGMENT_LOWER = "ўї" 

AUTO_START_PROGRAMS = {"zTasker.exe", "clash-verge.exe"}
EVERYTHING_EXE_NAME = "everything.exe"
EVERYTHING_CONSECUTIVE_RUNS_TO_CLOSE = 2

class ProcessMonitor:
    @staticmethod
    def get_user_profile_directory():
        return os.environ.get('USERPROFILE')

    @staticmethod
    def _normalize_path_for_comparison(path_string, user_profile_dir_actual):
        if not path_string: return None
        try:
            expanded_path = os.path.expandvars(path_string)
            abs_path = os.path.abspath(expanded_path)
            real_path = os.path.realpath(abs_path)
            norm_case_path = os.path.normcase(real_path)

            path_lower_for_check = norm_case_path.lower()
            misencoded_user_path_prefix_lower = os.path.join("c:\\users", POTENTIALLY_MISENCODED_USER_FRAGMENT_LOWER).lower()
            
            if path_lower_for_check.startswith(misencoded_user_path_prefix_lower):
                if user_profile_dir_actual:
                    correct_user_path_prefix_normcase = os.path.normcase(user_profile_dir_actual)
                    path_suffix = norm_case_path[len(misencoded_user_path_prefix_lower):]
                    corrected_path = os.path.join(correct_user_path_prefix_normcase, path_suffix.lstrip(os.sep))
                    
                    if DEBUG_SHORTCUT_SCAN or DEBUG_PROCESS_FINDING:
                        print(f"    [DEBUG][PathNorm] User Fragment Replaced: '{norm_case_path}' -> '{corrected_path}'")
                    norm_case_path = corrected_path 
                elif DEBUG_SHORTCUT_SCAN or DEBUG_PROCESS_FINDING:
                    print(f"    [DEBUG][PathNorm] Misencoded fragment detected but no USERPROFILE_ACTUAL to correct with.")
            return norm_case_path
        except Exception as e:
            if DEBUG_SHORTCUT_SCAN or DEBUG_PROCESS_FINDING:
                print(f"    [DEBUG][PathNorm] Error normalizing path '{path_string}': {e}")
            return None

    @staticmethod
    def find_process_by_path(target_exe_full_path, user_profile_dir_actual, debug_logging=False):
        norm_target_path = ProcessMonitor._normalize_path_for_comparison(target_exe_full_path, user_profile_dir_actual)
        if not norm_target_path:
            if debug_logging: print(f"[DEBUG][ProcFind] Failed to normalize target path: '{target_exe_full_path}'.")
            return False, None
        
        if debug_logging: print(f"[DEBUG][ProcFind] Normalized TARGET Path to Match: '{norm_target_path}'")

        for proc in psutil.process_iter(attrs=['pid', 'name', 'exe']):
            try:
                proc_exe_path_raw = proc.info['exe']
                if not proc_exe_path_raw: continue

                norm_proc_exe_path = ProcessMonitor._normalize_path_for_comparison(proc_exe_path_raw, user_profile_dir_actual)
                if not norm_proc_exe_path:
                    if debug_logging: print(f"    [DEBUG][ProcFind] PID {proc.pid}: Failed to normalize process exe path '{proc_exe_path_raw}'.")
                    continue
                
                if debug_logging and proc.info['name'].lower() in [p.lower() for p in PREFERRED_PROGRAMS]:
                     print(f"    [DEBUG][ProcFind] PID {proc.pid} ('{proc.info['name']}'): Normalized Proc Exe Path: '{norm_proc_exe_path}'")

                if norm_proc_exe_path == norm_target_path:
                    if debug_logging: print(f"  [DEBUG][ProcFind] >>> MATCH! PID {proc.pid} ('{proc.info['name']}') for target '{norm_target_path}'")
                    return True, proc
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
                if debug_logging: print(f"    [DEBUG][ProcFind] Error processing PID {proc.pid if hasattr(proc,'pid') else '?'}: {e}")
                continue
        
        if debug_logging: print(f"[DEBUG][ProcFind] No process found matching normalized path '{norm_target_path}'.")
        return False, None

def _clear_console():
    os.system('cls')

def start_process(executable_path, process_name):
    try:
        subprocess.Popen([executable_path])
        return f"[动作] 尝试启动 '{process_name}' (路径: {executable_path})。"
    except FileNotFoundError:
        return f"[错误] 启动 '{process_name}': 文件未找到 '{executable_path}'。"
    except PermissionError:
        return f"[错误] 启动 '{process_name}': 权限不足 '{executable_path}'。"
    except Exception as e:
        return f"[错误] 启动 '{process_name}' 时发生未知错误: {e}。"

def terminate_process_by_obj(proc_obj, process_name):
    if not proc_obj:
        return f"[错误] 尝试终止 '{process_name}' 但未提供有效的进程对象。"
    pid = proc_obj.pid
    try:
        proc_obj.terminate()
        try:
            proc_obj.wait(timeout=3)
            return f"[动作] '{process_name}' (PID {pid}) 已发送终止信号并成功退出。"
        except psutil.TimeoutExpired:
            proc_obj.kill()
            return f"[动作] '{process_name}' (PID {pid}) 未在超时内响应终止信号，已被强制终止。"
    except psutil.NoSuchProcess:
        return f"[信息] '{process_name}' (PID {pid}) 在尝试终止时已不存在。"
    except psutil.AccessDenied:
        return f"[错误] 终止 '{process_name}' (PID {pid}): 权限不足。"
    except Exception as e:
        return f"[错误] 终止 '{process_name}' (PID {pid}) 时发生未知错误: {e}。"

def perform_checks_and_actions(targets_map, user_profile_dir_actual, is_timed_event, everything_state):
    all_reports_text = []
    
    for name, path in targets_map.items():
        report_lines = []
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        report_lines.append(f"\n--- 进程报告: {name} ({timestamp}) ---")
        report_lines.append(f"监测路径: {path}")

        is_running, process_obj = ProcessMonitor.find_process_by_path(path, user_profile_dir_actual, DEBUG_PROCESS_FINDING)

        if is_running and process_obj:
            try:
                with process_obj.oneshot():
                    pid, proc_name, exe = process_obj.pid, process_obj.name(), process_obj.exe()
                    report_lines.append(f"[结果] '{proc_name}' (PID: {pid}) 正在运行。")
                    report_lines.append(f"       实际路径: {exe}")
                    report_lines.append("\n       详细信息:")
                    report_lines.append(f"         CPU: {process_obj.cpu_percent(interval=0.01):.1f}%")
                    mem_mb = process_obj.memory_info().rss / (1024*1024)
                    report_lines.append(f"         内存(RSS): {mem_mb:.2f} MB")
                    ctime = datetime.datetime.fromtimestamp(process_obj.create_time()).strftime('%Y-%m-%d %H:%M:%S')
                    report_lines.append(f"         启动时间: {ctime}")
                    cmd = ' '.join(process_obj.cmdline()) if process_obj.cmdline() else 'N/A'
                    report_lines.append(f"         命令行: {cmd}")
                    report_lines.append(f"         状态: {process_obj.status()}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
                err_msg = "已结束" if isinstance(e, psutil.NoSuchProcess) else \
                          "无权限" if isinstance(e, psutil.AccessDenied) else f"错误: {e}"
                report_lines.append(f"[结果] '{name}' 在获取详情时 {err_msg}")
        else:
            report_lines.append(f"[结果] '{name}' 未找到 (基于路径 '{path}')。")

        if name in AUTO_START_PROGRAMS:
            if not is_running:
                action_msg = start_process(path, name)
                report_lines.append(action_msg)
        
        elif name == EVERYTHING_EXE_NAME and is_timed_event:
            current_check_is_running = is_running
            
            if everything_state["timed_check_count"] == 1:
                everything_state["was_running_in_prev_timed_check"] = current_check_is_running
            elif everything_state["timed_check_count"] >= EVERYTHING_CONSECUTIVE_RUNS_TO_CLOSE:
                if current_check_is_running and everything_state["was_running_in_prev_timed_check"]:
                    if process_obj:
                        action_msg = terminate_process_by_obj(process_obj, name)
                        report_lines.append(action_msg)
                        report_lines.append(f"[控制] '{name}' 已连续 {EVERYTHING_CONSECUTIVE_RUNS_TO_CLOSE} 次自动检测到运行，已尝试关闭。")
                    else:
                        report_lines.append(f"[警告] '{name}' 标记为运行但无进程对象可终止 (应在关闭逻辑前发生)。")
                
                everything_state["timed_check_count"] = 0 
                everything_state["was_running_in_prev_timed_check"] = False 
        
        report_lines.append(f"--- 报告结束 ({name}) ---")
        all_reports_text.append("\n".join(report_lines))
    
    return "\n".join(all_reports_text), everything_state


def select_programs_from_list(programs_list):
    print("\n请选择要监测的程序:")
    for i, name in enumerate(programs_list): print(f"  {i+1}. {name}")
    print(f"  666. 监测以上所有 ({len(programs_list)}个)")
    print(f"  0. 退出")
    selected = []
    while True:
        try:
            choice = input("选项: ").strip()
            if choice == '0': return []
            if choice == '666': selected = list(programs_list); break
            idx = int(choice) - 1
            if 0 <= idx < len(programs_list): selected = [programs_list[idx]]; break
            print("无效选项。")
        except ValueError: print("请输入数字。")
    print(f"已选择: {', '.join(selected) if selected else '无'}")
    return selected

def _scan_single_start_menu_tree(start_menu_dir, preferred_programs_TARGET_exe_names_lower_set, found_paths_map, user_profile_dir_actual, debug_scan):
    if not (os.path.isdir(start_menu_dir) and pylnk3): return
    if debug_scan: print(f"\n[DEBUG][LNKScan] Scanning LNKs in: {start_menu_dir}...")
    
    found_in_this_tree = 0
    for root, _, files in os.walk(start_menu_dir):
        for filename in files:
            if not filename.lower().endswith(".lnk"): continue
            lnk_filepath = os.path.join(root, filename)
            try:
                lnk = pylnk3.Lnk(lnk_filepath)
                raw_target_from_lnk = lnk.path
                if not raw_target_from_lnk:
                    if debug_scan: print(f"    [DEBUG][LNKScan] LNK '{os.path.basename(lnk_filepath)}': Target path is empty.")
                    continue

                resolved_and_normalized_target_path = ProcessMonitor._normalize_path_for_comparison(raw_target_from_lnk, user_profile_dir_actual)
                if not resolved_and_normalized_target_path:
                    if debug_scan: print(f"    [DEBUG][LNKScan] LNK '{os.path.basename(lnk_filepath)}': Failed to normalize target '{raw_target_from_lnk}'.")
                    continue

                if not os.path.isfile(resolved_and_normalized_target_path):
                    if debug_scan: print(f"    [DEBUG][LNKScan] LNK '{os.path.basename(lnk_filepath)}' (norm_target: '{resolved_and_normalized_target_path}') IS NOT A FILE. Raw LNK target: '{raw_target_from_lnk}'.")
                    continue
                
                resolved_target_exe_name_lower = os.path.basename(resolved_and_normalized_target_path).lower()
                if resolved_target_exe_name_lower in preferred_programs_TARGET_exe_names_lower_set:
                    original_prog_name_case_sensitive = next((p for p in PREFERRED_PROGRAMS if p.lower() == resolved_target_exe_name_lower), None)
                    if original_prog_name_case_sensitive:
                        if original_prog_name_case_sensitive not in found_paths_map:
                            found_paths_map[original_prog_name_case_sensitive] = resolved_and_normalized_target_path
                            found_in_this_tree +=1
                            print(f"  [快捷方式发现] '{original_prog_name_case_sensitive}' -> '{resolved_and_normalized_target_path}' (LNK: '{filename}')")
                        elif debug_scan:
                            print(f"    [DEBUG][LNKScan] '{original_prog_name_case_sensitive}' already found. LNK ('{filename}') target: '{resolved_and_normalized_target_path}' vs existing: '{found_paths_map[original_prog_name_case_sensitive]}'")
            except Exception as e:
                if debug_scan: print(f"    [DEBUG][LNKScan] Error parsing LNK '{os.path.basename(lnk_filepath)}': {e}")
    if debug_scan: print(f"[DEBUG][LNKScan] Found {found_in_this_tree} new paths in {os.path.basename(start_menu_dir)} tree.")

def resolve_program_paths_via_shortcuts(programs_to_find, user_profile_dir_actual, debug_scan):
    resolved_map = {}
    if pylnk3 is None:
        print("[警告] pylnk3模块不可用，无法扫描快捷方式。")
        return resolved_map

    target_exe_names_lower_set = {p.lower() for p in programs_to_find}

    if user_profile_dir_actual:
        user_start_menu = os.path.join(user_profile_dir_actual, "AppData", "Roaming", "Microsoft", "Windows", "Start Menu")
        if os.path.isdir(user_start_menu):
            _scan_single_start_menu_tree(user_start_menu, target_exe_names_lower_set, resolved_map, user_profile_dir_actual, debug_scan)
        elif debug_scan: print(f"[DEBUG][LNKScan] User Start Menu directory not found: {user_start_menu}")
    
    programs_still_needed_count = sum(1 for p_name in programs_to_find if p_name not in resolved_map)
    if programs_still_needed_count > 0:
        if debug_scan: print(f"[DEBUG][LNKScan] {programs_still_needed_count} program(s) still need paths. Checking common Start Menu...")
        common_start_menu_path = os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "Microsoft", "Windows", "Start Menu")
        if os.path.isdir(common_start_menu_path):
            _scan_single_start_menu_tree(common_start_menu_path, target_exe_names_lower_set, resolved_map, user_profile_dir_actual, debug_scan)
        elif debug_scan: print(f"[DEBUG][LNKScan] Common Start Menu directory not found: {common_start_menu_path}")
            
    for name in programs_to_find:
        if name not in resolved_map:
            if debug_scan or len(programs_to_find) == 1:
                 print(f"  [路径解析] 未能通过快捷方式为 '{name}' 找到路径。")
    return resolved_map

def main_monitoring_loop(targets_map, user_profile_dir_actual):
    active = True
    report_timer = REPORT_INTERVAL_SECONDS 
    names_str = ", ".join(targets_map.keys())
    
    everything_state = {
        "timed_check_count": 0,
        "was_running_in_prev_timed_check": False
    }

    print(f"\n[启动监测] 目标: {names_str}")
    print(f"每 ~{REPORT_INTERVAL_SECONDS // 60} 分钟报告。'0'+Enter退出, Enter立即报告。")

    while active:
        input_processed = False
        if kbhit():
            try:
                char = getch()
                if char == b'0': 
                    active = False
                    input_processed = True
                    print("\n[控制] 收到退出指令...")
                elif char in (b'\r', b'\n'): 
                    _clear_console()
                    print(f"\n[控制] 即时报告 for '{names_str}':")
                    report_output, _ = perform_checks_and_actions(targets_map, user_profile_dir_actual, False, {"timed_check_count":0, "was_running_in_prev_timed_check":False})
                    print(report_output)
                    report_timer = 0 
                    input_processed = True
                while kbhit() and input_processed: getch() 
            except Exception as e: print(f"[错误] 处理输入: {e}")

        if not active: break

        if report_timer >= REPORT_INTERVAL_SECONDS:
            _clear_console()
            print(f"\n[定时报告] for '{names_str}':")
            if any(name == EVERYTHING_EXE_NAME for name in targets_map.keys()):
                 everything_state["timed_check_count"] += 1

            report_output, new_everything_state = perform_checks_and_actions(targets_map, user_profile_dir_actual, True, everything_state)
            print(report_output)
            everything_state = new_everything_state 
            report_timer = 0
        
        time.sleep(1)
        if not input_processed: report_timer += 1
    print("\n--- 监测结束 ---")

if __name__ == "__main__":
    _clear_console()
    print("--- 高级进程监测脚本 (v3.6 - 自动启停) ---")
    
    if pylnk3 is None:
        print("[关键错误] pylnk3 模块未能加载。请运行: pip install pylnk3")
        sys.exit(1)

    actual_user_profile = ProcessMonitor.get_user_profile_directory()
    if not actual_user_profile:
        print("[关键错误] 无法获取当前用户的USERPROFILE目录。脚本无法安全运行。")
        sys.exit(1)
    
    if EXPECTED_USER_NAME_IN_PATH not in actual_user_profile:
        print(f"[警告] 预期的用户名 '{EXPECTED_USER_NAME_IN_PATH}' 未在 USERPROFILE ('{actual_user_profile}') 中找到。")
        print(f"       强制替换逻辑可能无效。请检查 EXPECTED_USER_NAME_IN_PATH 设置。")

    selected_names = select_programs_from_list(PREFERRED_PROGRAMS)
    if not selected_names: print("未选择程序。退出。"); sys.exit(0)

    print(f"\n[信息] 解析选定程序路径 (通过快捷方式): {', '.join(selected_names)}")
    resolved_targets = resolve_program_paths_via_shortcuts(selected_names, actual_user_profile, DEBUG_SHORTCUT_SCAN)

    if not resolved_targets:
        print("\n[错误] 未能为任何选定程序解析出有效路径。退出。")
        sys.exit(1)
    
    print("\n[信息] 将监测以下程序:")
    valid_targets = {}
    for name, path in resolved_targets.items():
        final_check_path = ProcessMonitor._normalize_path_for_comparison(path, actual_user_profile)
        if final_check_path and os.path.isfile(final_check_path):
            valid_targets[name] = path 
            print(f"  - {name}: {path} (有效)")
        else:
            print(f"  - {name}: {path} (路径在最终检查后无效或非文件!)")
            if DEBUG_SHORTCUT_SCAN: print(f"    Normalized check for '{path}' resulted in '{final_check_path}', isfile: {os.path.isfile(final_check_path) if final_check_path else 'N/A'}")

    if not valid_targets:
        print("\n[错误] 所有解析路径均无效。无法启动监测。")
        sys.exit(1)
    
    main_monitoring_loop(valid_targets, actual_user_profile)
