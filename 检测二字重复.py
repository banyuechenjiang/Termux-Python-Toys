import sys
import os
import re

# ================= 核心配置区域 (User Configuration) =================

# 1.【支持类型】需要处理的文件扩展名 (只处理txt)
SUPPORTED_EXTS = ('.txt',)

# 2.【正则模式】用于查找连续相同字符的正则表达式
#    (.)  -> 捕获任意一个字符 (汉字、字母、数字、符号都算)
#    \1   -> 反向引用，匹配与第一个括号内捕获的完全相同的内容
#    所以 (.).\1 会匹配 "a a", "我 我"，而 (.)\1 会匹配 "aa", "我我"
REGEX_PATTERN = re.compile(r'(.)\1')

# ===================================================================

def find_consecutive_chars(file_path):
    """
    读取文件内容，并逐行查找连续的相同字符。
    解决了Windows下常见的GBK编码问题。
    """
    results = []
    content = ""
    
    # --- 关键：编码处理 ---
    # 优先尝试UTF-8，如果失败（UnicodeDecodeError），则回退到GBK
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()
        except Exception as e:
            # 如果两种编码都失败，则报告错误
            print(f"\n[X] 文件读取失败: {os.path.basename(file_path)} - 错误: {e}")
            return []
            
    # 逐行进行正则匹配
    lines = content.splitlines()
    for line_num, line in enumerate(lines, 1):
        # findall会找到一行中所有匹配项，如 "我的的猫和和狗" -> ['的', '和']
        matches = REGEX_PATTERN.findall(line)
        if matches:
            # 将找到的重复字符构造成 "的的", "和和" 的形式
            found_words = [f"{char}{char}" for char in matches]
            results.append((line_num, found_words))
            
    return results


def main():
    """主执行函数，处理拖拽和交互两种模式"""
    
    # --- 拖拽模式 ---
    if len(sys.argv) > 1:
        print("--- 开始检测连续重复字符 ---")
        total_files_found_issues = 0
        
        # 遍历所有拖拽进来的路径（可以是文件或文件夹）
        for path_arg in sys.argv[1:]:
            files_to_process = []
            
            # Case 1: 如果拖入的是一个文件夹
            if os.path.isdir(path_arg):
                for root, _, files in os.walk(path_arg):
                    for name in files:
                        if name.lower().endswith(SUPPORTED_EXTS):
                            files_to_process.append(os.path.join(root, name))
            
            # Case 2: 如果拖入的是一个文件
            elif os.path.isfile(path_arg):
                if path_arg.lower().endswith(SUPPORTED_EXTS):
                    files_to_process.append(path_arg)
            
            # 开始处理收集到的文件列表
            for file_path in files_to_process:
                findings = find_consecutive_chars(file_path)
                
                if findings:
                    total_files_found_issues += 1
                    print("\n" + "="*50)
                    print(f"[!] 在文件 '{os.path.basename(file_path)}' 中发现问题:")
                    print(f"    完整路径: {file_path}")
                    for line_num, words in findings:
                        # 将列表 ['的的', '是是'] 格式化为 "'的的', '是是'"
                        formatted_words = ", ".join([f"'{w}'" for w in words])
                        print(f"    - 行 {line_num}: 发现 {formatted_words}")
        
        # 打印最终总结
        print("\n" + "="*50)
        if total_files_found_issues == 0:
            print("检测完毕！所有已处理的文件中均未发现连续重复字符。")
        else:
            print(f"检测完毕！共在 {total_files_found_issues} 个文件中发现了问题。")

        # --- 关键：暂停命令行窗口 ---
        input("\n按回车键退出...")

    # --- 交互模式 (双击打开) ---
    else:
        print("--- 文本连续字符检测工具 ---")
        print("\n使用方法:")
        print("  将一个或多个【.txt 文件】或【包含 .txt 文件的文件夹】拖拽到本脚本上即可。")
        print("\n脚本会自动检测文件中的 '的的', '是是' 等连续字符，并在命令行中报告。")
        input("\n按回车键退出...")

if __name__ == "__main__":
    main()
