# -*- coding: utf-8 -*-
import sys
import os
import re
import argparse
import time
from typing import List, Dict, Optional

# ==============================================================================
# [AI 助手 (Roocode/Cline/Cursor) 专用操作指南]
#
# 任务: 调用此脚本扫描 TypeScript 项目中的 JSDoc 注释，找出纯英文（未翻译）的部分。
#
# 调用:
# 1. 扫描指定目录
# 2. 扫描当前目录
#
# 输出解析规则:
# - 脚本会将一个文件中所有 [疑似英文] 的注释聚合后一次性输出。
# - 格式为:
#   [FILE] <相对路径>
#   [EN-BLOCK]
#   <注释内容 1>
#   [EN-BLOCK]
#   <注释内容 2>
#   --------------------------------------------------
#
# 下一步行动:
# 读取控制台输出，针对每个 [FILE] 块，一次性完成该文件内所有 [EN-BLOCK] 的汉化翻译。
# 这种聚合模式可以避免对同一文件的多次读写操作。
#
# 无需读取报告文件:
# 脚本会生成一个 .txt 报告作为人类可读的备份，你不需要读取它。
# ==============================================================================

class TsDocAuditor:
    """
    JSDoc 提取与审计工具
    核心功能：提取 .ts/.tsx 中的 JSDoc，并筛选出未翻译的英文注释，
    以聚合形式输出给 AI，方便批量处理。
    """
    
    def __init__(self):
        self.jsdoc_pattern = re.compile(r'/\*\*.*?\*/', re.DOTALL)
        self.target_extensions = ('.ts', '.tsx')
        self.ignore_dirs = {
            'node_modules', '.git', 'dist', 'build', 'coverage', '.next', 'out', '__pycache__'
        }
        self.ts_keywords_pattern = re.compile(
            r'\b(string|number|boolean|void|Promise|any|null|undefined|Array|Object|Function|Date|RegExp|Error|never|unknown|bigint|symbol|this)\b'
        )

    def is_mostly_english(self, text: str) -> bool:
        """启发式算法：判断注释内容是否主要由英文组成。"""
        clean_text = self.ts_keywords_pattern.sub('', text)
        clean_text = re.sub(r'[/*@\s\r\n\t]', '', clean_text)
        
        if not clean_text:
            return False

        try:
            ascii_count = sum(1 for c in clean_text if ord(c) < 128)
            ratio = ascii_count / len(clean_text)
        except ZeroDivisionError:
            return False

        has_letters = any(c.isalpha() for c in clean_text)
        return ratio > 0.8 and has_letters

    def scan_and_report(self, input_path: str):
        """主逻辑：扫描目录，向控制台输出聚合的 AI 指令，并生成一份完整的报告文件。"""
        target_dir = self._resolve_target_directory(input_path)
        if not target_dir:
            return

        print(f"正在扫描目录: {target_dir}")
        print("注意：控制台仅显示疑似 [纯英文/未翻译] 的注释，以聚合模式输出，方便 AI 处理。\n")

        all_results = []
        english_comments_by_file: Dict[str, List[str]] = {}

        for folder_path, dirs, filenames in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]

            for filename in filenames:
                if not filename.lower().endswith(self.target_extensions):
                    continue
                
                full_path = os.path.join(folder_path, filename)
                relative_path = os.path.relpath(full_path, target_dir).replace("\\", "/")
                
                comments = self._extract_comments(full_path)
                if not comments:
                    continue

                for c in comments:
                    is_en = self.is_mostly_english(c)
                    all_results.append((relative_path, c, is_en))
                    
                    if is_en:
                        if relative_path not in english_comments_by_file:
                            english_comments_by_file[relative_path] = []
                        english_comments_by_file[relative_path].append(c)

        if english_comments_by_file:
            print("--- AI 任务开始：请汉化以下 JSDoc 注释 ---")
            for rel_path, en_comments in english_comments_by_file.items():
                self._print_aggregated_ai_output(rel_path, en_comments)
            print("--- AI 任务结束 ---")

        report_path = self._generate_full_report_file(target_dir, all_results)
        
        print("\n" + "=" * 50)
        print("扫描完成。")
        if english_comments_by_file:
            print(f"检测到 {len(english_comments_by_file)} 个文件中存在未翻译注释，详情见上方输出。")
        else:
            print("好消息：未检测到明显的纯英文 JSDoc 注释。")
        print(f"一份完整的审计报告已保存至: {report_path}")
        print("=" * 50)

    def _resolve_target_directory(self, path: str) -> Optional[str]:
        """解析并验证输入路径。如果是文件，则返回其父目录。"""
        path = path.strip('"').strip("'")
        abs_path = os.path.abspath(path)
        
        if os.path.isfile(abs_path):
            return os.path.dirname(abs_path)
        elif os.path.isdir(abs_path):
            return abs_path
        else:
            print(f"错误: 提供的路径无效或不存在 -> {path}")
            return None

    def _extract_comments(self, filepath: str) -> List[str]:
        """从单个文件中读取内容并提取所有 JSDoc 注释。"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return self.jsdoc_pattern.findall(content)
        except Exception as e:
            print(f"无法读取文件 {filepath}: {e}")
            return []

    def _print_aggregated_ai_output(self, relative_path: str, en_comments: List[str]):
        """以聚合的、AI 友好的格式输出单个文件的所有英文注释。"""
        print(f"[FILE] {relative_path}")
        for comment in en_comments:
            print("[EN-BLOCK]")
            print(comment.strip())
        print("-" * 50)

    def _generate_full_report_file(self, root_dir: str, results: List[tuple]) -> str:
        """生成一份详细的、人类可读的 .txt 报告文件。"""
        folder_name = os.path.basename(root_dir)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_filename = f"JSDoc审计报告_{folder_name}_{timestamp}.txt"
        
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(f"JSDoc 审计报告\n")
                f.write(f"扫描目录: {root_dir}\n")
                f.write(f"生成时间: {timestamp}\n")
                f.write("说明: 仅标记 [⚠️ EN] 的注释需要关注。\n")
                f.write("=" * 50 + "\n")

                current_file = ""
                # 按文件路径排序，保证报告结构稳定
                for rel_path, comment, is_en in sorted(results, key=lambda x: x[0]):
                    if rel_path != current_file:
                        f.write(f"\n\n📄 文件: {rel_path}\n" + "-" * (len(rel_path) + 8) + "\n")
                        current_file = rel_path
                    
                    # 关键修改：只为英文注释添加标记，其他保持原样
                    marker = "[⚠️ EN] " if is_en else ""
                    f.write(f"{marker}{comment.strip()}\n")
            
            return output_filename
        except Exception as e:
            return f"生成报告失败: {e}"

def run_as_tool(auditor: TsDocAuditor):
    """处理命令行调用和拖放启动模式。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=None)
    args = parser.parse_args()
    
    target_path = args.path if args.path else sys.argv[1]
    
    auditor.scan_and_report(target_path)
    
    # 如果是在交互式终端中运行（如拖放），则暂停等待用户确认
    if sys.stdout.isatty():
        input("\n处理完成，按回车键退出...")

def run_interactively(auditor: TsDocAuditor):
    """处理交互式菜单启动模式。"""
    print("-" * 40)
    print("  TS JSDoc 汉化辅助工具")
    print("-" * 40)

    # 获取当前目录下的文件夹列表
    try:
        # 排除隐藏文件夹和忽略列表中的文件夹
        sub_dirs = [d for d in os.listdir('.') if os.path.isdir(d) and not d.startswith('.') and d not in auditor.ignore_dirs]
        sub_dirs.sort()
    except Exception as e:
        print(f"无法读取当前目录: {e}")
        input("\n按回车键退出...")
        return
        
    # 添加"当前目录"选项
    options = ['. (当前目录)'] + sub_dirs
    
    if not options:
        print("当前目录下没有找到可供选择的文件夹。")
        input("\n按回车键退出...")
        return

    print("请选择要扫描的文件夹:")
    for i, dir_name in enumerate(options):
        print(f"  {i+1}. {dir_name}")
    print("  0. 退出")

    while True:
        try:
            choice_str = input(f"\n请输入数字 (0-{len(options)}): ").strip()
            if not choice_str: continue # 允许直接回车
            choice = int(choice_str)
            
            if choice == 0:
                print("操作已取消。")
                return
            elif 1 <= choice <= len(options):
                # 将选择的 '.(当前目录)' 转为实际的 '.'
                target_path = options[choice - 1].split(' ')[0]
                auditor.scan_and_report(target_path)
                break
            else:
                print("无效的数字，请重新输入。")
        except ValueError:
            print("无效输入，请输入一个数字。")
        except (KeyboardInterrupt, EOFError):
            print("\n操作已取消。")
            return
            
    input("\n按回车键退出...")

def main():
    """程序主入口，根据启动参数决定执行流程。"""
    auditor = TsDocAuditor()
    
    # 通过判断是否存在命令行参数来分离两种主要执行流程
    if len(sys.argv) > 1:
        run_as_tool(auditor)
    else:
        run_interactively(auditor)

if __name__ == "__main__":
    main()
