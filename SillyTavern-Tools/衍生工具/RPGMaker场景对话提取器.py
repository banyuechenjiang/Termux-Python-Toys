import os

def process_scenario_files(scenario_dir, output_dir):
    """
    处理 Scenario 文件夹下的所有 .txt 文件，提取对话内容并保存到指定输出文件夹。
    合并 _s 后缀文件的内容到对应的原始 .txt 文件末尾。
    """

    os.makedirs(output_dir, exist_ok=True)

    processed_base_filenames = set() # 记录已处理过的基础文件名，避免重复处理

    for filename in os.listdir(scenario_dir):
        if filename.endswith(".txt") and not filename.endswith("_s.txt"): # 只处理基础 .txt 文件，排除 _s 文件
            base_filename = filename[:-4] # 去除 .txt 后缀，获取基础文件名
            scenario_filepath = os.path.join(scenario_dir, filename)
            output_filepath = os.path.join(output_dir, filename)
            s_filename = base_filename + "_s.txt" # 构建 _s 文件名
            s_scenario_filepath = os.path.join(scenario_dir, s_filename) # _s 文件的完整路径

            print(f"处理文件: {filename}")

            try:
                with open(scenario_filepath, 'r', encoding='utf-8') as infile, \
                     open(output_filepath, 'w', encoding='utf-8') as outfile:

                    last_line_was_empty = False

                    for line_number, line in enumerate(infile, 1):
                        processed_line = line.strip()
                        is_comment_line = processed_line.startswith(';') or \
                                          processed_line.startswith('@') or \
                                          processed_line.startswith('；') or \
                                          processed_line.startswith('＠')
                        is_empty_line = not processed_line

                        if not is_comment_line:
                            if not is_empty_line:
                                outfile.write(line)
                                last_line_was_empty = False
                            elif not last_line_was_empty:
                                outfile.write(line)
                                last_line_was_empty = True


                print(f"  -> 对话内容已保存到: {output_filepath}")

                # 处理 _s 文件 (如果存在)
                if os.path.exists(s_scenario_filepath):
                    print(f"  发现 _s 文件: {s_filename}, 准备合并...")
                    with open(s_scenario_filepath, 'r', encoding='utf-8') as s_infile, \
                         open(output_filepath, 'a', encoding='utf-8') as outfile: # 注意使用 'a' (append) 模式

                        last_line_was_empty_s = False # 独立的空行标记 for _s 文件
                        outfile.write("\n") # 在合并内容前添加一个换行符，分隔原内容和 _s 内容

                        for line_number_s, line_s in enumerate(s_infile, 1):
                            processed_line_s = line_s.strip()
                            is_comment_line_s = processed_line_s.startswith(';') or \
                                              processed_line_s.startswith('@') or \
                                              processed_line_s.startswith('；') or \
                                              processed_line_s.startswith('＠')
                            is_empty_line_s = not processed_line_s

                            if not is_comment_line_s:
                                if not is_empty_line_s:
                                    outfile.write(line_s)
                                    last_line_was_empty_s = False
                                elif not last_line_was_empty_s:
                                    outfile.write(line_s)
                                    last_line_was_empty_s = True
                        print(f"  -> _s 文件内容已合并到: {output_filepath}")
                else:
                    print(f"  未找到 _s 文件: {s_filename}, 跳过合并。")


            except Exception as e:
                print(f"  ! 处理文件 {filename} 时发生错误: {e}")

if __name__ == "__main__":
    scenario_directory = "Scenario"
    dialogue_directory = "对话"

    process_scenario_files(scenario_directory, dialogue_directory)

    print("\n处理完成。")