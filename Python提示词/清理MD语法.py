import sys
import os

# ================= 核心配置区域 (User Configuration) =================

# 1.【清理内容】需要被移除的字符列表 (可自由增删)
REMOVE_CHARS = ['*', '#', ' '] 

# 2.【清理模式】是否清理空行？
# True: 删除所有空行，使文本更紧凑
REMOVE_EMPTY_LINES = False

# 3.【支持类型】需要处理的文件扩展名元组
SUPPORTED_EXTS = ('.txt', '.md', '.log', '.py', '.json', '.csv', '.xml')

# 4.【自动打开】是否在处理后自动打开文件？
AUTO_OPEN_FILE = True 

# 5.【安全阈值】当处理的文件总数超过此数量时，将不再自动打开，以防卡顿
# 如果拖入的是文件夹，强烈建议保持此功能
AUTO_OPEN_THRESHOLD = 5

# ===================================================================

def clean_content(text):
    """核心清理逻辑，由配置驱动"""
    processed_text = text
    for char in REMOVE_CHARS:
        processed_text = processed_text.replace(char, '')

    if REMOVE_EMPTY_LINES:
        lines = processed_text.splitlines()
        non_empty_lines = [line for line in lines if line.strip()]
        return '\n'.join(non_empty_lines)
    else:
        return processed_text

def process_file(file_path):
    """处理单个文件，返回 True/False 表示成功或失败"""
    if not file_path.lower().endswith(SUPPORTED_EXTS):
        return False
        
    try:
        content = ""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='gbk', errors='ignore') as f:
                content = f.read()

        cleaned_data = clean_content(content)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_data)
        
        return True
    except Exception:
        return False

def main():
    """主执行函数"""
    if len(sys.argv) > 1:
        # --- 拖拽模式 ---
        print("开始处理，成功[.]，失败[X]")
        processed_files_paths = []
        
        # 遍历所有拖拽进来的路径（可以是文件或文件夹）
        for path_arg in sys.argv[1:]:
            # Case 1: 如果拖入的是一个文件夹
            if os.path.isdir(path_arg):
                for root, _, files in os.walk(path_arg):
                    for name in files:
                        full_path = os.path.join(root, name)
                        if process_file(full_path):
                            print('.', end='', flush=True) # 打印成功点
                            processed_files_paths.append(full_path)
                        else:
                            # 仅在非支持类型时打印失败，避免过多IO错误刷屏
                            if not full_path.lower().endswith(SUPPORTED_EXTS):
                                pass # 静默跳过非目标文件
                            else:
                                print('X', end='', flush=True) # 打印失败叉
            
            # Case 2: 如果拖入的是一个文件
            elif os.path.isfile(path_arg):
                if process_file(path_arg):
                    print('.', end='', flush=True)
                    processed_files_paths.append(path_arg)
                else:
                    print('X', end='', flush=True)

        print("\n" + "="*40) # 换行并打印分割线
        total_processed = len(processed_files_paths)
        print(f"处理完毕！共成功清理 {total_processed} 个文件。")

        # 根据配置和安全阈值决定是否打开文件
        if AUTO_OPEN_FILE and 0 < total_processed <= AUTO_OPEN_THRESHOLD:
            print(f"文件数量(≤{AUTO_OPEN_THRESHOLD})，正在自动打开...")
            for p in processed_files_paths:
                if os.name == 'nt': os.startfile(p)
                else: os.system(f'open "{p}"')
            sys.exit(0) # 自动打开后直接退出
        elif AUTO_OPEN_FILE and total_processed > AUTO_OPEN_THRESHOLD:
            print(f"注意：文件数量超过 {AUTO_OPEN_THRESHOLD}，已取消自动打开以防系统卡顿。")

        input("按回车键退出...")

    else:
        # --- 交互模式 (双击打开) ---
        print("---文本清理工具---")
        print("\n使用方法:")
        print("  1. 将【文件】拖拽到本脚本上，进行清理。")
        print("  2. 将【文件夹】拖拽到本脚本上，将自动清理其中所有支持类型的文件。")
        print("\n当前配置:")
        print(f"  - 清理字符: {REMOVE_CHARS}")
        print(f"  - 清理空行: {REMOVE_EMPTY_LINES}")
        print(f"  - 自动打开: {AUTO_OPEN_FILE} (阈值: {AUTO_OPEN_THRESHOLD} 个文件)")
        input("\n按回车键退出...")

if __name__ == "__main__":
    main()
