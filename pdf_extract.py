import sys
import fitz  # pip install pymupdf
import re
import logging
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# -----------------------------------------------------------------------------
# 1. 基础配置
# -----------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

# -----------------------------------------------------------------------------
# 2. 正则表达式
# -----------------------------------------------------------------------------

RE_SPACES = re.compile(r'\s+')
RE_ACCOUNTING_START = re.compile(r'^(借|贷)[:：\s]')
RE_MONEY_ONLY = re.compile(r'^[\d][\d\s,.]*$')
RE_SENTENCE_END = re.compile(r'[.!?。！？]$')
# 新增：识别页码标记的正则，防止排版时被错误合并
RE_PAGE_MARKER = re.compile(r'^--- \[第 \d+ 页\] ---$')

# -----------------------------------------------------------------------------
# 3. 核心解析逻辑
# -----------------------------------------------------------------------------

class PDFParser:

    @staticmethod
    def clean_text(text: str) -> str:
        if not text: return ""
        return RE_SPACES.sub(' ', text).strip()

    @staticmethod
    def is_money_line(text: str) -> bool:
        """判断一行是否仅仅是金额数字"""
        clean = text.replace(' ', '').replace(',', '').replace('.', '')
        return clean.isdigit() and len(clean) > 0

    @staticmethod
    def process_page_content(page) -> list:
        """提取页面内容"""
        height = page.rect.height
        # 稍微放宽页眉页脚限制，以免误删有效内容
        margin_top, margin_bottom = height * 0.02, height * 0.98
        
        blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
        lines_data = []

        for block in blocks:
            if "lines" not in block: continue
            bbox = block["bbox"]
            if bbox[1] < margin_top or bbox[3] > margin_bottom: continue

            for line in block["lines"]:
                line_parts = []
                for span in line["spans"]:
                    txt = PDFParser.clean_text(span["text"])
                    if txt: line_parts.append(txt)
                
                if line_parts:
                    lines_data.append(" ".join(line_parts))
        return lines_data

    @staticmethod
    def smart_format_accounting(raw_lines: list) -> str:
        """
        包含会计分录 + 页码保护 的排版逻辑
        """
        merged_lines = []
        buffer = ""

        for text in raw_lines:
            # --- 0. 预处理：页码标记 ---
            # 如果是页码标记，强制中断当前 buffer，并独立成行
            if RE_PAGE_MARKER.match(text):
                if buffer:
                    merged_lines.append(buffer)
                    buffer = ""
                # 增加空行，让页码更醒目
                merged_lines.append(f"\n{text}\n")
                continue

            if not buffer:
                buffer = text
                continue
            
            # --- 1. 会计逻辑 ---
            is_money = PDFParser.is_money_line(text)
            prev_is_entry = bool(RE_ACCOUNTING_START.match(buffer))

            # 逻辑 A：金额强制合并
            if is_money:
                buffer += "\t" + text
            # 逻辑 B：普通文本合并
            elif not RE_SENTENCE_END.search(buffer):
                if prev_is_entry:
                     merged_lines.append(buffer)
                     buffer = text
                else:
                    buffer += " " + text
            else:
                merged_lines.append(buffer)
                buffer = text
        
        if buffer: merged_lines.append(buffer)

        # --- 2. 代码块包裹逻辑 (保持不变) ---
        final_output = []
        in_accounting_block = False
        
        for line in merged_lines:
            # 如果是页码行，先关闭代码块，再输出页码
            if "--- [第" in line:
                if in_accounting_block:
                    final_output.append("```\n")
                    in_accounting_block = False
                final_output.append(line)
                continue

            is_entry = bool(RE_ACCOUNTING_START.match(line))
            
            if is_entry:
                if not in_accounting_block:
                    final_output.append("\n```text") 
                    in_accounting_block = True
                final_output.append(line)
            else:
                if in_accounting_block:
                    # 简单判断退出条件
                    if len(line) < 20 or "——" in line or "公允价值" in line:
                         final_output.append(line)
                    else:
                        final_output.append("```\n")
                        in_accounting_block = False
                        final_output.append(line)
                else:
                    final_output.append(line)

        if in_accounting_block:
            final_output.append("```\n")

        return "\n".join(final_output)

    @staticmethod
    def process_file(file_path: Path):
        start = time.time()
        try:
            with fitz.open(file_path) as doc:
                if doc.page_count == 0: return False, "空文件", file_path.stem, 0

                raw_lines = []
                
                # --- 关键修改：按页遍历并插入标记 ---
                for i, page in enumerate(doc, start=1):
                    # 1. 插入页码标记 (作为独立的一行添加到 raw_lines)
                    # 格式：--- [第 X 页] ---
                    page_marker = f"--- [第 {i} 页] ---"
                    raw_lines.append(page_marker)
                    
                    # 2. 提取该页内容
                    page_content = PDFParser.process_page_content(page)
                    raw_lines.extend(page_content)

                # 执行排版
                content = PDFParser.smart_format_accounting(raw_lines)
                
                return True, content, file_path.stem, time.time() - start
        except Exception as e:
            return False, str(e), file_path.stem, time.time() - start

# -----------------------------------------------------------------------------
# 4. 主程序入口
# -----------------------------------------------------------------------------

def run():
    input_paths = sys.argv[1:]
    if not input_paths:
        print("=== PDF 自动补页码工具 ===")
        print("请拖放 PDF 文件到此脚本上运行。")
        input("按回车退出...")
        return

    files = []
    for p in input_paths:
        path = Path(p)
        if path.is_file() and path.suffix.lower() == '.pdf':
            files.append(path)
        elif path.is_dir():
            files.extend(list(path.glob("*.pdf")))

    if not files:
        print("未找到 PDF 文件。")
        return

    output_dir = files[0].parent / "parsed_with_pagenum"
    output_dir.mkdir(exist_ok=True)
    
    print(f"检测到 {len(files)} 个文件，开始处理...")
    
    success_count = 0
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(PDFParser.process_file, f): f for f in files}
        
        for future in as_completed(futures):
            success, res, stem, t = future.result()
            if success:
                (output_dir / f"{stem}.txt").write_text(res, encoding="utf-8")
                print(f"[√] {stem} (页码已补, {t:.2f}s)")
                success_count += 1
            else:
                print(f"[x] {stem} - 失败: {res}")

    print(f"\n处理完成。结果保存在: {output_dir}")
    time.sleep(2)

if __name__ == "__main__":
    run()
