import sys
import os
import json
import re
import openpyxl
import time
from datetime import datetime
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Literal, Tuple

# ==============================================================================
# 1. 设计原则：模式切换架构
# ==============================================================================

@dataclass
class HostDefinition:
    name: str
    domains: List[str]
    type: Literal["id_based", "full_url"]
    base_url: Optional[str] = None

ALL_HOST_DEFINITIONS = {
    "catbox": HostDefinition(
        name="Catbox",
        domains=["files.catbox.moe"],
        type="id_based",
        base_url="https://files.catbox.moe/"
    ),
    "sharkpan": HostDefinition(
        name="Sharkpan",
        domains=["sharkpan.xyz"],
        type="full_url"
    )
}

current_scan_mode = "catbox"

@dataclass
class Config:
    images_per_html_file: int = 20
    supported_extensions: List[str] = field(default_factory=lambda: ['png', 'jpg', 'jpeg', 'gif'])
    visualization_folder: str = "可视化报告"

# --- 文件类型智能识别定义 ---
FILE_TYPE_DEFINITIONS = {
    "角色卡": {
        "validator": lambda data: isinstance(data, dict) and (("spec" in data and "char_card_v2" in data.get("spec", "")) or ("name" in data and "create_date" in data)),
        "scan_keys": ["description", "first_mes", "system_prompt", "post_history_instructions", "alternate_greetings"],
    },
    "世界书": {
        "validator": lambda data: isinstance(data, dict) and "entries" in data and isinstance(data.get("entries", {}), dict),
        "scan_keys": ["content", "comment", "keys"],
    }
}

# ==============================================================================
# 2. 设计原则：结构化数据对象
# ==============================================================================

@dataclass
class FoundItem:
    final_url: str
    display_name: str
    host_name: str

@dataclass
class ExtractionTask:
    filepath: str
    config: Config
    patterns: Dict[str, re.Pattern]
    active_host: HostDefinition

@dataclass
class ExtractionResult:
    source_path: str
    found_items: List[FoundItem] = field(default_factory=list)
    error: Optional[str] = None

# ==============================================================================
# 3. 设计原则：关注点分离 - 辅助函数
# ==============================================================================

def build_regex_for_host(host: HostDefinition, config: Config) -> Dict[str, re.Pattern]:
    ext_pattern = '|'.join(re.escape(ext) for ext in config.supported_extensions)
    patterns = {}
    
    if host.type == 'id_based':
        patterns['core_extractor'] = re.compile(r'([a-zA-Z0-9]{6}\.(?:' + ext_pattern + r'))', re.IGNORECASE)
        patterns['full_finder'] = re.compile(r'([^\s:,<>"\']*?[a-zA-Z0-9]{6}\.(?:' + ext_pattern + r'))', re.IGNORECASE)
        patterns['random_block_pattern'] = re.compile(r'\{\{random:(.*?)\}\}', re.IGNORECASE)
    elif host.type == 'full_url':
        domain_pattern = '|'.join(re.escape(d) for d in host.domains)
        patterns['url_finder'] = re.compile(
            r'((?:https?:)?//(?:' + domain_pattern + r')[^\s:,<>"\']*\.(?:' + ext_pattern + r'))',
            re.IGNORECASE
        )
    return patterns

def find_values_by_key(data: Any, target_keys: List[str]) -> str:
    found_values = []
    scan_keys_set = set(target_keys)
    def recurse(sub_data):
        if isinstance(sub_data, dict):
            for key, value in sub_data.items():
                if key in scan_keys_set and isinstance(value, str):
                    found_values.append(value)
                else:
                    recurse(value)
        elif isinstance(sub_data, list):
            for item in sub_data:
                recurse(item)
    recurse(data)
    return "\n".join(found_values)

# ==============================================================================
# 4. 设计原则：阶段化执行 - 核心逻辑
# ==============================================================================

def _phase_1_extract_from_file(task: ExtractionTask) -> ExtractionResult:
    try:
        with open(task.filepath, 'r', encoding='utf-8', errors='ignore') as f:
            full_text = f.read()
    except Exception as e:
        return ExtractionResult(source_path=task.filepath, error=f"读取文件失败: {e}")

    scan_area = full_text
    try:
        data = json.loads(full_text)
        for f_type, definition in FILE_TYPE_DEFINITIONS.items():
            if definition["validator"](data):
                json_key_content = find_values_by_key(data, definition["scan_keys"])
                if json_key_content:
                    scan_area = json_key_content + "\n" + full_text
                break
    except json.JSONDecodeError:
        pass
    
    found_map: Dict[str, FoundItem] = {}
    patterns = task.patterns
    host = task.active_host

    if host.type == 'id_based':
        for block_match in patterns['random_block_pattern'].finditer(scan_area):
            items = [item.strip() for item in block_match.group(1).split(',')]
            for random_item in items:
                if patterns['core_extractor'].fullmatch(random_item):
                    core_id = random_item.lower()
                    found_map[core_id] = FoundItem(final_url=f"{host.base_url}{core_id}", display_name=random_item, host_name=host.name)
        
        for match in patterns['full_finder'].finditer(scan_area):
            display_name = match.group(1)
            core_match = patterns['core_extractor'].search(display_name)
            if core_match:
                core_id = core_match.group(1).lower()
                if core_id not in found_map or len(display_name) > len(found_map[core_id].display_name):
                    found_map[core_id] = FoundItem(final_url=f"{host.base_url}{core_id}", display_name=display_name, host_name=host.name)

    elif host.type == 'full_url':
        for match in patterns['url_finder'].finditer(scan_area):
            full_url = match.group(1)
            final_url = 'https:' + full_url if full_url.startswith('//') else full_url
            if final_url not in found_map:
                 found_map[final_url] = FoundItem(final_url=final_url, display_name=full_url, host_name=host.name)

    short_basename = os.path.splitext(os.path.basename(task.filepath))[0]
    short_basename = short_basename[:10] if len(short_basename) > 10 else short_basename
    url_counter = 1
    for item in found_map.values():
        cleaned_display_name = item.display_name.replace('\n', ' ').strip()
        cleaned_display_name = re.sub(r'^\d+\.\s*', '', cleaned_display_name)
        
        if cleaned_display_name == item.final_url or cleaned_display_name == item.final_url.replace("https://", "//"):
            item.display_name = f"{short_basename}-{host.name}-{url_counter}"
            url_counter += 1
        else:
            item.display_name = cleaned_display_name

    return ExtractionResult(source_path=task.filepath, found_items=list(found_map.values()))

def _phase_2_generate_reports(all_results: List[ExtractionResult], config: Config, active_host: HostDefinition):
    if not all_results:
        print(f"所有JSON文件处理完毕，但未找到任何【{active_host.name}】链接。")
        return
    
    all_items_for_excel = []
    for res in all_results:
        for item in res.found_items:
            all_items_for_excel.append({
                "final_url": item.final_url,
                "display_name": item.display_name,
                "source_path": res.source_path
            })
    create_excel_report(all_items_for_excel, config, active_host)
    create_html_previews(all_results, config, active_host)

def create_excel_report(all_items: List[Dict], config: Config, active_host: HostDefinition):
    final_data_map: Dict[str, Tuple[str, str]] = {}
    for item in all_items:
        if item['final_url'] not in final_data_map or len(item['display_name']) > len(final_data_map[item['final_url']][0]):
            final_data_map[item['final_url']] = (item['display_name'], os.path.basename(item['source_path']))
    
    print(f"\n共找到 {len(final_data_map)} 个唯一的【{active_host.name}】链接，正在生成总的Excel文件...")
    
    sorted_rows = sorted(final_data_map.items(), key=lambda x: (x[1][1], x[1][0]))

    timestamp = datetime.now().strftime("%H%M%S")
    
    excel_filename = f"{active_host.name.lower()}_urls_{timestamp}.xlsx"
    
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = f"{active_host.name} Report"
    sheet.append(['URL', '描述文本', '源文件'])
    
    for url, (display_name, source_file) in sorted_rows:
        sheet.append([url, display_name, source_file])
        
    sheet.column_dimensions['A'].width = 60
    sheet.column_dimensions['B'].width = 45
    sheet.column_dimensions['C'].width = 30
    
    try:
        workbook.save(excel_filename)
        print(f"成功创建Excel文件: {os.path.abspath(excel_filename)}")
    except Exception as e:
        print(f"创建Excel文件失败: {e}")

def create_html_previews(all_results: List[ExtractionResult], config: Config, active_host: HostDefinition):
    print(f"\n正在为 {len(all_results)} 个源文件生成HTML预览...")
    os.makedirs(config.visualization_folder, exist_ok=True)
    img_div = """<div class="image-container"><div class="image-wrapper"><a href="{url}" target="_blank"><img alt="{display_name}" class="story-image" src="{url}" loading="lazy"></a></div><div class="text-content" title="{full_display}">{display_name_short}</div></div>"""
    html_page = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>图片预览 - {page_title}</title><style>body{{font-family:sans-serif;background-color:#f0f2f5;margin:0;padding:20px}}h1{{text-align:center;color:#333;word-break:break-all}}.grid-container{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:20px}}.image-container{{border:1px solid #ddd;border-radius:8px;overflow:hidden;background-color:#fff;box-shadow:0 2px 5px rgba(0,0,0,0.1);transition:transform .2s}}.image-container:hover{{transform:translateY(-5px)}}.image-wrapper{{width:100%;padding-top:100%;position:relative}}.story-image{{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover}}.text-content{{padding:10px;font-size:14px;text-align:center;word-break:break-all;background-color:#fafafa;border-top:1px solid #eee;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}a{{text-decoration:none;color:inherit}}</style></head><body><h1>图片预览: {page_title}</h1><div class="grid-container">{body_content}</div></body></html>"""
    for res in all_results:
        base_name = os.path.basename(res.source_path)
        subfolder_name = os.path.splitext(base_name)[0]
        output_dir = os.path.join(config.visualization_folder, subfolder_name)
        os.makedirs(output_dir, exist_ok=True)
        print(f"  - 正在处理 '{base_name}' -> 输出到 '{subfolder_name}' 文件夹...")
        sorted_items = sorted(res.found_items, key=lambda item: item.display_name)
        for i in range(0, len(sorted_items), config.images_per_html_file):
            chunk = sorted_items[i:i + config.images_per_html_file]
            page_num = (i // config.images_per_html_file) + 1
            ext_counts = Counter(os.path.splitext(item.final_url)[1].lstrip('.').lower() for item in chunk)
            ext_str = '&'.join(f"{count}_{ext}" for ext, count in sorted(ext_counts.items()))
            if len(ext_counts) == 1:
                html_filename = f"{active_host.name.lower()}_{page_num}-{ext_str}.html"
            else:
                html_filename = f"{active_host.name.lower()}_{page_num}-{ext_str}-{len(chunk)}.html"
            divs = []
            for item in chunk:
                display_name_short = (item.display_name[:30] + '...') if len(item.display_name) > 30 else item.display_name
                divs.append(img_div.format(url=item.final_url, display_name=item.display_name, full_display=item.display_name, display_name_short=display_name_short))
            html_divs = "".join(divs)
            full_html = html_page.format(body_content=html_divs, page_title=subfolder_name)
            try:
                with open(os.path.join(output_dir, html_filename), 'w', encoding='utf-8') as f:
                    f.write(full_html)
            except Exception as e:
                print(f"    ! 写入HTML文件 '{html_filename}' 失败: {e}")
    print(f"\n所有HTML预览文件已生成在文件夹中: {os.path.abspath(config.visualization_folder)}")

# ==============================================================================
# 5. 设计原则：关注点分离 - UI与主流程控制器
# ==============================================================================

def process_path(input_path: str, config: Config):
    global current_scan_mode
    active_host = ALL_HOST_DEFINITIONS[current_scan_mode]

    print("-" * 50)
    print(f"开始处理路径: {input_path}")
    
    json_files = []
    if os.path.isdir(input_path):
        for root, _, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith('.json'):
                    json_files.append(os.path.join(root, file))
    elif input_path.lower().endswith('.json'):
        json_files = [input_path]

    if not json_files:
        print("在指定路径下没有找到任何JSON文件。")
        return

    patterns = build_regex_for_host(active_host, config)
    print(f"将查找【{active_host.name}】链接，支持后缀: {', '.join(config.supported_extensions)}")
    print(f"发现 {len(json_files)} 个JSON文件，开始并行提取...")

    all_results: List[ExtractionResult] = []
    tasks = [ExtractionTask(filepath=f, config=config, patterns=patterns, active_host=active_host) for f in json_files]
    
    with ThreadPoolExecutor() as executor:
        future_to_task = {executor.submit(_phase_1_extract_from_file, task): task for task in tasks}
        for future in as_completed(future_to_task):
            result = future.result()
            if result.error:
                print(f"  - [✗ 错误] {os.path.basename(result.source_path)}: {result.error}")
            elif result.found_items:
                print(f"  - [✓ 完成] {os.path.basename(result.source_path)} (找到 {len(result.found_items)} 个链接)")
                all_results.append(result)

    print("\n所有文件提取完毕。")
    _phase_2_generate_reports(all_results, config, active_host)

def run_interactive_ui(config: Config):
    global current_scan_mode
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        active_host_name = ALL_HOST_DEFINITIONS[current_scan_mode].name
        
        print("="*50 + "\n 链接智能提取工具 (UI简化最终版)\n" + "="*50)
        
        try:
            entries = os.listdir('.')
            folders = sorted([d for d in entries if os.path.isdir(d) and not d.startswith('.') and d != config.visualization_folder])
            json_files_in_dir = sorted([f for f in entries if os.path.isfile(f) and f.lower().endswith('.json')])
            
            choices = {}
            current_choice = 1
            if folders:
                print("\n--- 请选择要扫描的文件夹 ---")
                for item in folders:
                    choices[str(current_choice)] = item
                    print(f"  [{current_choice}] {item}")
                    current_choice += 1
            
            if json_files_in_dir:
                print("\n--- 或选择要扫描的单个JSON文件 ---")
                for item in json_files_in_dir:
                    choices[str(current_choice)] = item
                    print(f"  [{current_choice}] {item}")
                    current_choice += 1

        except Exception as e:
            print(f"错误：无法扫描当前目录: {e}")
            time.sleep(3)
            continue

        if not choices:
            print("\n当前目录下未找到任何子文件夹或 .json 文件。")

        print("\n" + "-"*20)
        print(f"  [M] 切换扫描模式 (当前: 【{active_host_name}】)")
        print("  [Q] 退出程序")
        
        user_input = input("\n请输入选项编号或操作字母并按Enter: ").lower()

        if user_input in ['q', 'quit']:
            print("程序已退出。")
            break
        elif user_input == 'm':
            current_scan_mode = 'sharkpan' if current_scan_mode == 'catbox' else 'catbox'
            print(f"\n扫描模式已切换至: 【{ALL_HOST_DEFINITIONS[current_scan_mode].name}】")
            time.sleep(1.5)
        elif user_input in choices:
            process_path(choices[user_input], config)
            input("\n处理完成！按 Enter 键返回主菜单...")
        else:
            print("无效的输入，请重新选择。")
            time.sleep(1.5)

def main():
    config = Config()
    
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        process_path(input_path, config)
        input("\n处理完成！按 Enter 键退出...")
    else:
        run_interactive_ui(config)

if __name__ == "__main__":
    main()
