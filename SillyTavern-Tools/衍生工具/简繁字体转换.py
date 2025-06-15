import os
import json
import sys
import re

try:
    import opencc
    import yaml
except ImportError:
    print("错误：缺少必要的库。")
    print("请先通过 pip 安装 'opencc-python-rebuilt' 和 'PyYAML'。")
    print("命令: pip install opencc-python-rebuilt PyYAML")
    sys.exit(1)

CHINESE_CHARS_RE = re.compile(r"[\u4e00-\u9fff]")

def convert_structured_data_and_count(data, converter):
    """
    递归转换结构化数据（字典、列表），同时统计并收集变化的字符对。
    返回: (转换后的数据, 变化字符数, 变化详情列表)
    """
    if isinstance(data, dict):
        new_dict = {}
        total_changes = 0
        all_diffs = []
        for k, v in data.items():
            converted_v, changes, diffs = convert_structured_data_and_count(v, converter)
            new_dict[k] = converted_v
            total_changes += changes
            all_diffs.extend(diffs)
        return new_dict, total_changes, all_diffs
    elif isinstance(data, list):
        new_list = []
        total_changes = 0
        all_diffs = []
        for item in data:
            converted_item, changes, diffs = convert_structured_data_and_count(item, converter)
            new_list.append(converted_item)
            total_changes += changes
            all_diffs.extend(diffs)
        return new_list, total_changes, all_diffs
    elif isinstance(data, str):
        converted_str = converter.convert(data)
        diffs = [{'original': c1, 'converted': c2} for c1, c2 in zip(data, converted_str) if c1 != c2]
        changes = len(diffs)
        return converted_str, changes, diffs
    else:
        return data, 0, []

def needs_conversion_check(content, converter):
    """快速预检，判断文件内容是否可能需要转换。"""
    unique_chars = set(CHINESE_CHARS_RE.findall(content))
    if not unique_chars:
        return False
    original_char_str = "".join(unique_chars)
    converted_char_str = converter.convert(original_char_str)
    return original_char_str != converted_char_str

def process_file_for_conversion(input_path, output_path, converter):
    """
    处理单个文件转换。
    返回: (状态, 变化字符数, 聚合后的差异字典或None)
    """
    try:
        file_ext = os.path.splitext(input_path)[1].lower()
        if file_ext not in ['.json', '.yaml', '.yml', '.txt', '.md']:
            return 'unsupported', 0, None
        
        with open(input_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
            
        if not needs_conversion_check(original_content, converter):
            print("  └─ 预检结果: 无需转换，内容已是目标格式。")
            return 'no_change', 0, None
            
        print("  └─ 预检结果: 检测到可转换内容，开始深度处理...")
        
        converted_content_str = None
        change_count = 0
        diffs_list = []
        
        if file_ext == '.json':
            original_data = json.loads(original_content)
            converted_data, change_count, diffs_list = convert_structured_data_and_count(original_data, converter)
            if change_count > 0:
                converted_content_str = json.dumps(converted_data, ensure_ascii=False, indent=4)
        elif file_ext in ['.yaml', '.yml']:
            original_data = yaml.safe_load(original_content)
            converted_data, change_count, diffs_list = convert_structured_data_and_count(original_data, converter)
            if change_count > 0:
                converted_content_str = yaml.dump(converted_data, allow_unicode=True, sort_keys=False)
        elif file_ext in ['.txt', '.md']:
            converted_data = converter.convert(original_content)
            diffs_list = [{'original': c1, 'converted': c2} for c1, c2 in zip(original_content, converted_data) if c1 != c2]
            change_count = len(diffs_list)
            if change_count > 0:
                converted_content_str = converted_data

        if change_count == 0:
            print("  └─ 深度处理结果: 无实际变化。")
            return 'no_change', 0, None

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f_out:
            f_out.write(converted_content_str)
            
        print(f"  └─ 转换成功 (共 {change_count} 个字符被更改)。")

        # --- 核心改动：聚合差异列表为差异字典 ---
        aggregated_diff = None
        if diffs_list:
            original_chars = "".join(d['original'] for d in diffs_list)
            converted_chars = "".join(d['converted'] for d in diffs_list)
            aggregated_diff = {'original': original_chars, 'converted': converted_chars}
        
        return 'success', change_count, aggregated_diff

    except Exception as e:
        print(f"  └─ 错误: 处理文件 {os.path.basename(input_path)} 时发生错误: {e}")
        return 'fail', 0, None

def count_chinese_chars_in_file(input_path):
    """统计单个文件中的汉字数量。"""
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        matches = CHINESE_CHARS_RE.findall(content)
        return len(matches)
    except Exception as e:
        print(f"  └─ 错误: 无法读取或处理文件 {os.path.basename(input_path)}: {e}")
        return None

def main():
    print("==============================================")
    print("     多功能文件处理工具 (v3.3 - 聚合日志版)")
    print("==============================================")
    
    # --- UI 和文件选择部分保持不变 ---
    print("请选择要执行的功能:")
    print("  1. 繁体 -> 简体 转换")
    print("  2. 简体 -> 繁体 转换")
    print("  3. 统计汉字个数")
    print("  0. 退出程序")
    mode_choice = ''
    while mode_choice not in ['1', '2', '3', '0']:
        mode_choice = input("请输入功能编号 (0, 1, 2, 或 3): ")

    if mode_choice == '0':
        print("程序已退出。")
        sys.exit(0)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_base_dir = os.path.join(script_dir, "字体转化")
    supported_extensions = ('.json', '.yaml', '.yml', '.txt', '.md')
    
    process_options = []
    try:
        current_script_name = os.path.basename(__file__)
        items_in_dir = [item for item in os.listdir(script_dir) if item != os.path.basename(output_base_dir) and item != current_script_name]
        for item_name in items_in_dir:
            item_path = os.path.join(script_dir, item_name)
            if os.path.isdir(item_path):
                process_options.append({'name': item_name, 'type': 'dir'})
            elif os.path.isfile(item_path) and item_name.lower().endswith(supported_extensions):
                process_options.append({'name': item_name, 'type': 'file'})
    except FileNotFoundError:
        print(f"错误：找不到脚本所在目录 '{script_dir}'。")
        input("\n按回车键退出。")
        return

    if not process_options:
        print("\n错误：在脚本所在文件夹下未找到任何子文件夹或支持的文件。")
        input("\n按回车键退出。")
        return

    print("\n请选择要进行处理的文件夹或文件:")
    for i, option in enumerate(process_options, 1):
        tag = "[文件夹]" if option['type'] == 'dir' else "[文  件]"
        print(f"  {i:2}. {tag} {option['name']}")
    
    choice = -1
    while not (1 <= choice <= len(process_options)):
        try:
            choice_str = input(f"请输入编号 (1-{len(process_options)}): ")
            choice = int(choice_str)
        except ValueError:
            print("输入无效，请输入一个数字。")
            
    selected_option = process_options[choice - 1]
    
    tasks = []
    if selected_option['type'] == 'dir':
        input_dir = os.path.join(script_dir, selected_option['name'])
        files_in_dir = [f for f in os.listdir(input_dir) if f.lower().endswith(supported_extensions)]
        for filename in files_in_dir:
            tasks.append({'input': os.path.join(input_dir, filename), 'output_filename': filename})
    else:
        tasks.append({'input': os.path.join(script_dir, selected_option['name']), 'output_filename': selected_option['name']})
        
    if not tasks:
        print("在选定目标中未找到支持处理的文件。")
        input("\n按回车键退出。")
        return

    if mode_choice in ['1', '2']:
        action_desc = "繁体 -> 简体" if mode_choice == '1' else "简体 -> 繁体"
        print(f"\n已选择: {action_desc}转换")
        converter = opencc.OpenCC('t2s' if mode_choice == '1' else 's2t')
        suffix = '_简体' if mode_choice == '1' else '_繁体'
        
        output_dir_name_base = ""
        if selected_option['type'] == 'dir':
            output_dir_name_base = selected_option['name']
        else:
            filename_base, _ = os.path.splitext(selected_option['name'])
            output_dir_name_base = filename_base
        
        output_dir_name_with_suffix = f"{output_dir_name_base}{suffix}"
        final_output_dir = os.path.join(output_base_dir, output_dir_name_with_suffix)
        print(f"结果将保存至: {final_output_dir}\n")

        success_count, fail_count, no_change_count, total_changed_chars = 0, 0, 0, 0
        all_conversion_diffs = {}

        for task in tasks:
            input_filepath = task['input']
            output_filepath = os.path.join(final_output_dir, task['output_filename'])
            print(f"- 正在处理: {os.path.basename(input_filepath)}")
            
            # 接收聚合后的 diff_data
            status, changes, diff_data = process_file_for_conversion(input_filepath, output_filepath, converter)
            
            if status == 'success':
                success_count += 1
                total_changed_chars += changes
                # 如果有差异数据，则直接存入
                if diff_data:
                    all_conversion_diffs[os.path.basename(input_filepath)] = diff_data
            elif status == 'fail':
                fail_count += 1
            elif status == 'no_change':
                no_change_count += 1
        
        if all_conversion_diffs:
            diff_filename = f"{output_dir_name_with_suffix}_diff.yaml"
            diff_file_path = os.path.join(output_base_dir, diff_filename)
            try:
                os.makedirs(output_base_dir, exist_ok=True)
                with open(diff_file_path, 'w', encoding='utf-8') as f:
                    yaml.dump(all_conversion_diffs, f, allow_unicode=True, sort_keys=False, indent=2)
                print(f"\n* 转换对比日志已保存至: {diff_file_path}")
            except Exception as e:
                print(f"\n* 错误: 无法写入转换对比日志文件: {e}")

        # --- 总结报告部分保持不变 ---
        total_scanned = success_count + fail_count + no_change_count
        print("\n==============================================")
        print("          转换完成！")
        print("----------------------------------------------")
        print(f"总共扫描文件: {total_scanned}个")
        print(f"  - 转换成功: {success_count}个")
        print(f"  - 无需转换: {no_change_count}个")
        print(f"  - 处理失败: {fail_count}个")
        print("----------------------------------------------")
        if total_changed_chars > 0: print(f"总共转换字符: {total_changed_chars}个")
        if success_count > 0: print(f"转换结果已保存至 '{final_output_dir}'")
        print("==============================================")
    
    elif mode_choice == '3':
        # --- 统计功能保持不变 ---
        print(f"\n已选择: 统计汉字个数")
        print(f"统计目标: {selected_option['name']}\n")
        
        total_chars = 0
        processed_count = 0
        fail_count = 0

        for task in tasks:
            input_filepath = task['input']
            filename = os.path.basename(input_filepath)
            print(f"- 正在统计: {filename}")
            char_count = count_chinese_chars_in_file(input_filepath)
            
            if char_count is not None:
                print(f"  └─ 结果: {char_count} 个汉字")
                total_chars += char_count
                processed_count += 1
            else:
                fail_count += 1
        
        print("\n==============================================")
        print("          统计完成！")
        print("----------------------------------------------")
        print(f"总共扫描文件: {processed_count}个")
        if fail_count > 0:
            print(f"读取失败文件: {fail_count}个")
        print("----------------------------------------------")
        print(f"总计汉字数量: {total_chars} 个")
        print("==============================================")

    input("\n按回车键退出。")

if __name__ == "__main__":
    main()
