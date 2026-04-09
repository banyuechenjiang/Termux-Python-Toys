import os
import socket
import sys
import json
import concurrent.futures
import shutil
import subprocess
from pathlib import Path

# ==========================================
# 配置文件名：定义在脚本同级目录下
# ==========================================
CONFIG_FILE = Path(__file__).parent / "ssh_config.json"

def load_or_create_config():
    """
    配置管理逻辑：
    1. 检查配置文件是否存在，若不存在则生成含默认值的模板并退出。
    2. 若文件存在，则读取并解析 JSON 配置项。
    """
    # 定义默认配置模板，方便用户首次使用时参考修改
    default_template = {
        "SSH_BASE_DIR": "D:\\.ssh",       # SSH 密钥及配置文件存放的根目录
        "SSH_CONFIG_NAME": "config",      # SSH 配置文件名（通常就叫 config）
        "DYNAMIC_TARGET": "phone",        # 需要根据网络环境动态切换 IP 的主机别名
        "SSH_PORT": 8022,                 # Termux SSH 默认监听端口
        "HOME_WIFI_PREFIX": "x.x.x.",     # 家庭 WiFi 的网段标识（如 192.168.1.）
        "HOME_PHONE_IP": "x.x.x.x",       # 手机在家庭网络中通过路由器绑定的固定 IP
        "SCAN_WORKERS": 50,               # 热点扫描时的并发线程数
        "SCAN_TIMEOUT": 0.5              # 单次端口扫描的超时时间（单位：秒）
    }

    # 首次运行处理：创建模板并提示用户修改
    if not CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default_template, f, indent=4, ensure_ascii=False)
            print(f"\n[!] 首次运行：已生成脱敏配置模板 {CONFIG_FILE.name}")
            print("[!] 请在该 JSON 中填入你的真实 IP 映射，然后重新运行。")
            input("\n按回车键退出..."); sys.exit(0)
        except Exception as e:
            print(f"[!] 创建配置文件失败: {e}")
            input(); sys.exit(1)

    # 读取已存在的配置文件
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] 读取配置文件失败，请检查 JSON 格式: {e}")
        input(); sys.exit(1)

# --- 全局变量初始化：将配置映射到具体变量 ---
cfg = load_or_create_config()

SSH_BASE_DIR = Path(cfg["SSH_BASE_DIR"])
SSH_CONFIG_FILE = SSH_BASE_DIR / cfg["SSH_CONFIG_NAME"]
DYNAMIC_TARGET = cfg["DYNAMIC_TARGET"]
SSH_PORT = cfg["SSH_PORT"]
HOME_WIFI_PREFIX = cfg["HOME_WIFI_PREFIX"]
HOME_PHONE_IP = cfg["HOME_PHONE_IP"]
SCAN_WORKERS = cfg.get("SCAN_WORKERS", 50)
SCAN_TIMEOUT = cfg.get("SCAN_TIMEOUT", 0.15)

def get_local_ip():
    """
    获取本机当前的局域网内网 IP 地址。
    通过尝试连接公网 DNS (8.8.8.8) 来诱导系统选择正确的网络接口，无需真正发送数据。
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except: 
        ip = "127.0.0.1"
    finally: 
        s.close()
    return ip

def get_ssh_hosts():
    """
    解析 SSH config 文件，提取所有定义的 Host 别名。
    用于在控制台展示可供连接的主机菜单。
    """
    hosts = []
    if not SSH_CONFIG_FILE.exists(): return hosts
    try:
        with open(SSH_CONFIG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 匹配以 Host 开头的行，并排除通配符 Host *
                if line.lower().startswith("host ") and "*" not in line:
                    parts = line.split()
                    if len(parts) > 1: 
                        hosts.extend(parts[1:])
    except: 
        pass
    return hosts

def check_ip_port(ip, port):
    """
    尝试通过 TCP 三次握手连接指定 IP 的端口。
    用于探测手机端 SSH 服务是否存活。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(SCAN_TIMEOUT)
        # connect_ex 返回 0 表示连接成功
        return ip if s.connect_ex((ip, port)) == 0 else None

def scan_hotspot_subnet(local_ip):
    """
    并发扫描当前子网（/24 网段）。
    当本机作为热点或连接热点时，自动寻找开启了 SSH 端口的目标。
    """
    prefix = ".".join(local_ip.split('.')[:-1]) + "."
    print(f" [*] 正在探测热点网段 {prefix}0/24 ...")
    # 生成 1-254 的 IP 列表，排除掉本机 IP
    ips = [prefix + str(i) for i in range(1, 255) if prefix + str(i) != local_ip]
    
    # 使用线程池加速扫描过程
    with concurrent.futures.ThreadPoolExecutor(max_workers=SCAN_WORKERS) as executor:
        futures = {executor.submit(check_ip_port, ip, SSH_PORT): ip for ip in ips}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: return res # 找到第一个匹配的主机即返回
    return None

def main():
    # --- 环境初始化 ---
    os.system("chcp 65001 >nul") # 切换代码页为 UTF-8，防止控制台中文乱码
    if sys.platform == "win32":
        os.system(f"title Termux SSH 自动调度器")

    # 1. 获取所有可用的 SSH 主机列表
    all_hosts = get_ssh_hosts()
    if not all_hosts:
        print(f"[!] 错误: 未在 {SSH_CONFIG_FILE} 中找到主机配置。")
        input(); return

    # 2. 打印交互菜单
    print("\n" + " SSH 主机调度中心 ".center(46, "="))
    for i, name in enumerate(all_hosts, 1):
        print(f"  [{i}] {name}")
    print("="*50)
    
    # 获取用户输入，支持默认值
    try:
        choice = input(f" 请选择 (1-{len(all_hosts)}, 默认[1]): ").strip()
        selected_host = all_hosts[int(choice)-1] if choice else all_hosts[0]
    except: 
        selected_host = all_hosts[0]

    # 3. 环境变量注入：解决 Windows SSH 客户端对目录权限和默认路径的依赖问题
    os.environ["HOME"] = str(SSH_BASE_DIR)
    os.environ["USERPROFILE"] = str(SSH_BASE_DIR)
    ssh_path = shutil.which("ssh") # 查找系统 PATH 中的 ssh 路径

    if not ssh_path:
        print("[!] 错误: 系统中未找到 ssh.exe")
        input(); return

    local_ip = get_local_ip()
    target_ip = None
    info_lines = []

    # 4. 核心逻辑：自动判定连接模式（静态 IP 还是 动态扫描）
    if selected_host == DYNAMIC_TARGET:
        # 模式 A：处于预设的家庭 WiFi 网段，直接使用固定 IP
        if local_ip.startswith(HOME_WIFI_PREFIX):
            info_lines = [
                f"[ 模式 ]  家庭 WiFi",
                f"[ 本机 ]  {local_ip}",
                f"[ 目标 ]  {HOME_PHONE_IP} (固定地址)"
            ]
            target_ip = HOME_PHONE_IP
        else:
            # 模式 B：处于非家庭环境（如手机开热点给电脑），启动全网段扫描
            print("\n" + " 正在搜索手机 IP ".center(46, "-"))
            target_ip = scan_hotspot_subnet(local_ip)
            if target_ip:
                info_lines = [
                    f"[ 模式 ]  手机热点 (自动发现)",
                    f"[ 本机 ]  {local_ip}",
                    f"[ 目标 ]  {target_ip} (已定位)"
                ]
            else:
                # 模式 C：扫描无果，猜测通常为网关地址（.1）
                target_ip = ".".join(local_ip.split('.')[:-1]) + ".1"
                info_lines = [
                    f"[ 模式 ]  热点模式 (回退网关)",
                    f"[ 本机 ]  {local_ip}",
                    f"[ 目标 ]  {target_ip} (默认)"
                ]
    else:
        # 普通静态主机模式（直接使用 config 里的 HostName）
        info_lines = [
            f"[ 模式 ]  普通远程主机",
            f"[ 别名 ]  {selected_host}"
        ]

    # 5. 打印连接详情汇总
    print("\n" + " 连接详情 ".center(46, "-"))
    for line in info_lines:
        print(f"  {line}")
    print("-" * 50)
    print("\n[!] 正在弹出独立 SSH 终端并关闭当前程序...")

    # 6. 构造 SSH 命令参数
    ssh_args = [ssh_path, "-F", str(SSH_CONFIG_FILE)]
    if selected_host == DYNAMIC_TARGET:
        # 针对手机端：强制覆盖 HostName 和 Port，并禁用指纹校验（防止因 IP 变化触发警告）
        ssh_args.extend([
            "-p", str(SSH_PORT), 
            "-o", f"HostName={target_ip}", 
            "-o", "StrictHostKeyChecking=no"
        ])
    ssh_args.append(selected_host)

    # 7. 启动新窗口执行 SSH 命令并退出当前进程
    try:
        # CREATE_NEW_CONSOLE 确保 ssh 在新窗口运行，当前脚本窗口可以立即关闭
        subprocess.Popen(ssh_args, creationflags=subprocess.CREATE_NEW_CONSOLE)
        sys.exit(0) 
    except Exception as e:
        print(f"[!] 启动失败: {e}")
        input()

if __name__ == "__main__":
    main()
