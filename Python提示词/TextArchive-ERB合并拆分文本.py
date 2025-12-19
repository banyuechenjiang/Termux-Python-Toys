import os
import re
import sys

# ================= 配置常量 =================
TARGET_EXTS = {
    '.txt', '.md', '.yaml', '.yml', '.json', 
    '.ini', '.conf', '.log', '.py', '.sh'
}
ERB_EXT = ".erb"
SPLIT_SUFFIX = "-拆分"
ENCODING = "utf-8"

# 预编译正则 (全局单例)
# 警告：正则逻辑依赖文件整体结构，修改需谨慎
PATTERN = re.compile(r'--- (.+?) ---\n(.*?)(?=\n--- |\Z)', re.DOTALL)
# ===========================================

def scan_files(folder):
    """生成器：按需返回文件路径"""
    for root, _, filenames in os.walk(folder):
        for f in sorted(filenames):
            if os.path.splitext(f)[1].lower() in TARGET_EXTS:
                yield os.path.join(root, f)

def merge_to_erb(folder_path):
    """流式处理：单文件内存占用，极大降低峰值负载"""
    folder_path = folder_path.rstrip(os.sep)
    output_file = f"{os.path.basename(folder_path)}{ERB_EXT}"
    
    print(f"[*] 模式: 聚合 -> {output_file}")
    
    count = 0
    try:
        # 建立持续写入流，避免大文件内存溢出
        with open(output_file, "w", encoding=ENCODING, newline='\n') as out_f:
            files = scan_files(folder_path)
            
            for path in files:
                try:
                    rel_path = os.path.relpath(path, folder_path).replace(os.sep, '/')
                    
                    with open(path, "r", encoding=ENCODING, errors='replace') as in_f:
                        content = in_f.read()
                    
                    # 写入头部标识
                    out_f.write(f"--- {rel_path} ---\n")
                    out_f.write(content)
                    
                    # 强制边界补全 (流式写入的关键)
                    if content and not content.endswith('\n'):
                        out_f.write("\n")
                    
                    count += 1
                    sys.stdout.write(f"\r[+] 写入流: {count} | {rel_path[:30]}...")
                    sys.stdout.flush()
                    
                except Exception as e:
                    print(f"\n[!] 读写中断: {path} | {e}")
                    
        if count == 0:
            print("\n[-] 警告: 目标文件夹无有效文件")
            os.remove(output_file) # 清理空文件
        else:
            print(f"\n[OK] 聚合完成: {output_file}")
            
    except Exception as e:
        print(f"\n[-] 致命IO错误: {e}")

def split_from_erb(erb_path):
    """内存映射优化：迭代器匹配"""
    print(f"[*] 模式: 释放 -> {erb_path}")
    output_dir = f"{os.path.splitext(os.path.basename(erb_path))[0]}{SPLIT_SUFFIX}"
    
    try:
        with open(erb_path, 'r', encoding=ENCODING, errors='replace') as f:
            data = f.read()
    except Exception as e:
        print(f"[-] 读取源失败: {e}")
        return

    matches = PATTERN.finditer(data)
    count = 0
    
    for match in matches:
        rel_path, content = match.groups()
        
        # 路径安全化
        safe_path = re.sub(r'[*?"<>|]', '', rel_path.strip()).replace('/', os.sep)
        full_path = os.path.join(output_dir, safe_path)
        
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding=ENCODING, newline='\n') as f:
                # 智能移除聚合时补全的换行
                f.write(content[:-1] if content.endswith('\n') and content else content)
            
            count += 1
            sys.stdout.write(f"\r[+] 释放流: {count} | {safe_path[:30]}...")
            sys.stdout.flush()
        except Exception as e:
            print(f"\n[!] 写入中断: {full_path} | {e}")

    print(f"\n[OK] 释放完成: {output_dir}" if count > 0 else "\n[-] 未解析到数据块")

def interactive_mode():
    actions = {'1': (True, merge_to_erb), '2': (False, split_from_erb)}
    
    while True:
        print(f"\n=== 极简归档器 ===")
        print("1. 聚合 (Dir -> ERB)")
        print("2. 释放 (ERB -> Dir)")
        print("0. 退出")
        
        choice = input("指令 > ").strip()
        if choice == '0': sys.exit(0)
        
        if choice in actions:
            is_dir, func = actions[choice]
            items = [x for x in os.listdir('.') if (os.path.isdir(x) if is_dir else x.lower().endswith(ERB_EXT))]
            
            if not items:
                print("[-] 无匹配项")
                continue
                
            for i, item in enumerate(items): print(f"  {i+1}. {item}")
            
            idx = input("序号 > ")
            if idx.isdigit() and 1 <= int(idx) <= len(items):
                func(items[int(idx)-1])

if __name__ == "__main__":
    # 拖拽/命令行模式
    if len(sys.argv) > 1:
        target = sys.argv[1]
        if os.path.isdir(target):
            merge_to_erb(target)
        elif os.path.isfile(target) and target.lower().endswith(ERB_EXT):
            split_from_erb(target)
        else:
            print(f"[-] 输入无效: 仅支持文件夹或 {ERB_EXT} 文件")
        
        input("\n[任务完成] 按回车键退出...")
    # 交互菜单模式
    else:
        interactive_mode()
