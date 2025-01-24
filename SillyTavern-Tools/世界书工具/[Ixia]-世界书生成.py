import json
import os
from datetime import datetime
from typing import Optional, List, Tuple

def select_directory() -> Optional[str]:
    """
    让用户选择一个目录。
    返回选择的目录路径，如果用户取消则返回 None。
    对应 HTML 中的文件选择 input 元素和文件夹选择逻辑。
    """
    current_dir = os.getcwd()
    print(f"当前工作目录: {current_dir}")

    all_items = [item for item in os.listdir('.') if os.path.isdir(item)]
    if not all_items:
        print("当前目录下没有找到任何文件夹。")
        return None

    print("\n请选择要处理的文件夹 (输入数字 ID):")
    for i, item in enumerate(all_items):
        print(f"{i+1}. {item}")
    print("0. 退出")

    while True:
        try:
            choice = int(input("请输入数字 ID (0 - {}): ".format(len(all_items))))
            if choice == 0:
                return None
            elif 1 <= choice <= len(all_items):
                selected_dir = all_items[choice - 1]
                confirmation_input = input(f"您选择了: {selected_dir}, 确认选择此文件夹吗? (y/n, 默认: y): ").lower()
                if confirmation_input == '' or confirmation_input == 'y':
                    return selected_dir
                elif confirmation_input == 'n':
                    print("已取消选择，请重新选择。")
                else:
                    print("无效的输入，请输入 'y' 或 'n' 或直接回车确认。")
            else:
                print("无效的数字 ID，请输入有效范围内的数字。")
        except ValueError:
            print("无效的输入，请输入数字。")

def create_entry(info: dict, order: int, depth: int) -> dict:
    """
    创建标准条目字典，复刻 HTML 中 Javascript createEntry 函数的逻辑。
    对应 HTML 中的 Javascript createEntry() 函数。
    """
    return {
        "uid": info.get("uid"),                 # "uid": "唯一 ID，整数类型"
        "key": info.get("key"),                 # "key": "触发条目的关键字列表，支持文本和正则表达式，字符串数组"
        "keysecondary": info.get("keysecondary"), # "keysecondary": "可选的次要关键字列表，字符串数组"
        "comment": info.get("comment"),           # "comment": "条目的注释或标题，字符串类型"
        "content": info.get("content"),           # "content": "插入到提示词的文本内容，字符串类型"
        "constant": False,                       # "constant": "是否常驻，如果为 true 则始终插入，布尔类型 (true 或 false)"
        "vectorized": False,                     # "vectorized": "是否仅通过向量匹配激活，布尔类型 (true 或 false)"
        "selective": True,                      # "selective": "是否启用选择性过滤,需要同时满足 key 和 keysecondary 才能触发，布尔类型 (true 或 false)"
        "selectiveLogic": 0,                     # "selectiveLogic": "选择性逻辑，整数类型，取值范围：0 (AND ANY), 1 (AND ALL), 2 (NOT ANY), 3 (NOT ALL)"
        "addMemo": True,                        # "addMemo": "是否显示备注，布尔类型 (true 或 false)"
        "order": order,                           # "order": "插入顺序，数字越大优先级越高，整数类型"
        "position": 1,                           # "position": "插入位置，整数类型，取值范围：0 (Before Char Defs), 1 (After Char Defs), 2 (Before Example Messages), 3 (After Example Messages), 4 (Top of AN), 5 (Bottom of AN), 6 (@ D), 7 (⚙️ - as a system role message), 8 (👤 - as a user role message), 9 (🤖 - as an assistant role message)"
        "disable": False,                        # "disable": "是否禁用该条目，布尔类型 (true 或 false)"
        "excludeRecursion": False,                # "excludeRecursion": "是否在递归扫描时排除此条目，布尔类型 (true 或 false)"
        "preventRecursion": True,                 # "preventRecursion": "触发此条目时是否阻止递归扫描，布尔类型(true 或 false)"
        "delayUntilRecursion": False,             # "delayUntilRecursion": "是否延迟到递归扫描时才触发，布尔类型(true 或 false)"
        "probability": 100,                       # "probability": "条目被插入的概率 (0-100), 整数类型"
        "matchWholeWords": None,                  # "matchWholeWords": "是否匹配整个单词，布尔类型 (true 或 false) 或 null，null 表示使用全局设置"
        "useProbability": True,                   # "useProbability": "是否使用概率属性, 布尔类型 (true 或 false)"
        "depth": depth,                           # "depth": "深度, 当 position 为特定值时使用, 整数类型"
        "group": "",                              # "group": "分组名称，字符串类型"
        "groupOverride": False,                    # "groupOverride": "是否覆盖分组，布尔类型(true 或 false)"
        "groupWeight": 100,                       # "groupWeight": "分组权重，整数类型"
        "scanDepth": None,                      # "scanDepth": "扫描深度，整数类型或 null，null 表示使用全局设置"
        "caseSensitive": None,                     # "caseSensitive": "是否区分大小写，布尔类型 (true 或 false) 或 null，null 表示使用全局设置"
        "useGroupScoring": None,                    # "useGroupScoring": "是否使用分组评分，布尔类型 (true 或 false) 或 null，null 表示使用全局设置"
        "automationId": "",                       # "automationId": "自动化的唯一标识符，字符串类型"
        "role": None,                             # "role": "角色消息，整数类型(0:User, 1:System, 2:Assistant) 或 null"
        "sticky": 0,                              # "sticky": "是否常驻，整数类型，取值范围：0(否), 1(是), 2(直到上下文满)"
        "cooldown": 0,                            # "cooldown": "冷却时间，整数类型"
        "delay": 0,                               # "delay": "延迟时间，整数类型"
        "displayIndex": info.get("displayIndex")    # "displayIndex": "显示索引，整数类型"
    }

def create_divider_entry(uid: int, display_index: int, text: str, fileList: Optional[List[str]] = None, isStart: bool = False, startOrder: int = 0) -> dict:
    """
    创建分隔符条目字典，复刻 HTML 中 Javascript createDividerEntry 函数的逻辑。
    明确将 '{{random: ...}}' 视为固定文本片段，避免转义。
    对应 HTML 中的 Javascript createDividerEntry() 函数。
    """
    folderName = text.split('/').pop()
    content = ""
    position = 0
    order = 0
    random_directive_start = "{{random: "  # 定义 {{random:  为固定字符串
    random_directive_end = "}}"        # 定义  }} 为固定字符串
    list_start_tag = f"<{folderName}-列表>\n "   # 列表开始标签，使用 f-string 动态生成
    list_end_tag = f"\n</{folderName}-列表>"     # 列表结束标签，使用 f-string 动态生成

    if isStart:
        if fileList:
            fileListStr = ",".join(fileList)
            # 拼接字符串，明确 {{random: ...}} 部分为固定文本
            content = list_start_tag + random_directive_start + fileListStr + random_directive_end + list_end_tag
        else:
            # 拼接字符串，明确 {{random: }} 部分为固定文本
            content = list_start_tag + random_directive_start + random_directive_end + list_end_tag

        position = 0
        order = startOrder
    else:
        position = 1,
        order = startOrder + 2

    comment = f"--始 {folderName}--" if isStart else f"--{folderName} 终--"

    return {
        "uid": uid,                             # "uid": "唯一 ID，整数类型"
        "key": [folderName],                    # "key": "触发条目的关键字列表，支持文本和正则表达式，字符串数组"
        "keysecondary": [],                     # "keysecondary": "可选的次要关键字列表，字符串数组"
        "comment": comment,                       # "comment": "条目的注释或标题，字符串类型"
        "content": content,                       # "content": "插入到提示词的文本内容，字符串类型"
        "constant": True,                       # "constant": "是否常驻，如果为 true 则始终插入，布尔类型 (true 或 false)"
        "vectorized": False,                     # "vectorized": "是否仅通过向量匹配激活，布尔类型 (true 或 false)"
        "selective": True,                      # "selective": "是否启用选择性过滤,需要同时满足 key 和 keysecondary 才能触发，布尔类型 (true 或 false)"
        "selectiveLogic": 0,                     # "selectiveLogic": "选择性逻辑，整数类型，取值范围：0 (AND ANY), 1 (AND ALL), 2 (NOT ANY), 3 (NOT ALL)"
        "addMemo": True,                        # "addMemo": "是否显示备注，布尔类型 (true 或 false)"
        "order": order,                           # "order": "插入顺序，数字越大优先级越高，整数类型"
        "position": position[0] if isinstance(position, tuple) else position, # "position": "插入位置，整数类型，取值范围：0 (Before Char Defs), 1 (After Char Defs), 2 (Before Example Messages), 3 (After Example Messages), 4 (Top of AN), 5 (Bottom of AN), 6 (@ D), 7 (⚙️ - as a system role message), 8 (👤 - as a user role message), 9 (🤖 - as an assistant role message)"
        "disable": False,                        # "disable": "是否禁用该条目，布尔类型 (true 或 false)"
        "excludeRecursion": False,                # "excludeRecursion": "是否在递归扫描时排除此条目，布尔类型 (true 或 false)"
        "preventRecursion": False,              # "preventRecursion": "触发此条目时是否阻止递归扫描，布尔类型(true 或 false)"
        "delayUntilRecursion": False,             # "delayUntilRecursion": "是否延迟到递归扫描时才触发，布尔类型(true 或 false)"
        "probability": 100,                       # "probability": "条目被插入的概率 (0-100), 整数类型"
        "matchWholeWords": None,                  # "matchWholeWords": "是否匹配整个单词，布尔类型 (true 或 false) 或 null，null 表示使用全局设置"
        "useProbability": True,                   # "useProbability": "是否使用概率属性, 布尔类型 (true 或 false)"
        "depth": 4,                               # "depth": "深度, 当 position 为特定值时使用, 整数类型"
        "group": "",                              # "group": "分组名称，字符串类型"
        "groupOverride": False,                    # "groupOverride": "是否覆盖分组，布尔类型(true 或 false)"
        "groupWeight": 100,                       # "groupWeight": "分组权重，整数类型"
        "scanDepth": None,                      # "scanDepth": "扫描深度，整数类型或 null，null 表示使用全局设置"
        "caseSensitive": None,                     # "caseSensitive": "是否区分大小写，布尔类型 (true 或 false) 或 null，null 表示使用全局设置"
        "useGroupScoring": None,                    # "useGroupScoring": "是否使用分组评分，布尔类型 (true 或 false) 或 null，null 表示使用全局设置"
        "automationId": "",                       # "automationId": "自动化的唯一标识符，字符串类型"
        "role": 1,                                # "role": "角色消息，整数类型(0:User, 1:System, 2:Assistant) 或 null"
        "sticky": 0,                              # "sticky": "是否常驻，整数类型，取值范围：0(否), 1(是), 2(直到上下文满)"
        "cooldown": 0,                            # "cooldown": "冷却时间，整数类型"
        "delay": 0,                               # "delay": "延迟时间，整数类型"
        "displayIndex": display_index             # "displayIndex": "显示索引，整数类型"
    }

def extract_info(content: str, fileName: str, relative_folder_path: str, root_folder_name: str, uid: int, displayIndex: int) -> dict:
    """
    提取文件信息，复刻 HTML 中 Javascript extractInfo 函数的逻辑。
    根据 relative_folder_path 和 root_folder_name 确定 key。
    对应 HTML 中的 Javascript extractInfo() 函数。
    """
    title = os.path.splitext(fileName)[0]
    if relative_folder_path: # 文件在子文件夹中
        folderParts = relative_folder_path.replace("\\", "/").split('/')
        folderName = folderParts[-1] # 获取最后一个目录名 (子文件夹名)
        key_value = [folderName]
    else: # 文件在根目录下
        key_value = [root_folder_name] # 使用根文件夹名作为 key

    return {
        "uid": uid,                             # "uid": "唯一 ID，整数类型"
        "key": key_value,                       # "key": "触发条目的关键字列表，支持文本和正则表达式，字符串数组"
        "keysecondary": [title],                # "keysecondary": "可选的次要关键字列表，字符串数组"
        "comment": title,                       # "comment": "条目的注释或标题，字符串类型"
        "content": content,                       # "content": "插入到提示词的文本内容，字符串类型"
        "displayIndex": displayIndex,            # "displayIndex": "显示索引，整数类型"
        "fileSize": len(content.encode('utf-8')) # "fileSize": "用于计算深度"
    }


def generate_worldbook_json(root_dir: str, output_filename: str = 'worldbook.json'):
    """
    遍历指定根目录下的文件夹和文件，生成 worldbook.json 文件。
    完全复刻 HTML 中 Javascript generateWorldbook 函数的逻辑。
    添加名称排序，使生成顺序更可控。
    修改为同时处理 .txt 和 .md 文件。
    对应 HTML 中的 Javascript generateWorldbook() 函数。
    """
    entries = {} #  对应 Javascript 中的 entries = {};
    uid_counter = 0 #  对应 Javascript 中的 uidCounter = 0;
    display_index = 0 #  对应 Javascript 中的 displayIndex = 0;
    folder_order = 99 # 对应 Javascript 中的 folder_order = 99;
    current_folder = "" # 对应 Javascript 中的 currentFolder = "";

    now = datetime.now()
    formatted_date = now.strftime("%Y/%m/%d %H:%M:%S")
    metadata_content = """{{//
---
生成时间: {}
---
世界书描述：
标签：
---
配置信息：
 - 区分大小写:  否
---
免责声明：
本世界书由半自动化工具生成，可能包含不准确或不完善的信息。
用户应自行判断信息的适用性，并承担使用本世界书的风险。
本世界书中的内容，不构成任何形式的建议或保证。
本工具不保证生成的文本完全符合预期，也不对由此产生的任何直接或间接损失负责。
---
内容来源：本世界书的内容由用户提供的文本文件生成，本工具不对这些文件的内容和来源的合法性负责。
---
版权声明：
本世界书采用知识共享署名-相同方式共享 4.0 国际许可协议进行许可。
(Creative Commons Attribution-ShareAlike 4.0 International License)
查看许可证副本请访问：https://creativecommons.org/licenses/by-sa/4.0/
---
作者：
---
}}""".format(formatted_date) #  对应 Javascript 中的 metadataContent

    entries[uid_counter] = {  # 直接硬编码 "【说明】" 条目  对应 Javascript 中 entries[uidCounter] = { ... };  (第一个条目)
        "uid": uid_counter,
        "key": [],
        "keysecondary": [],
        "comment": "【说明】", #  对应 Javascript 中 comment: "【说明】",
        "content": metadata_content, #   对应 Javascript 中 content: metadataContent,
        "constant": True,
        "vectorized": False,
        "selective": False,
        "selectiveLogic": 0,
        "addMemo": True,
        "order": 98, #  对应 Javascript 中 order: 98,
        "position": 0, #  对应 Javascript 中 position: 0,
        "disable": False,
        "excludeRecursion": False,
        "preventRecursion": False,
        "delayUntilRecursion": False,
        "probability": 100,
        "matchWholeWords": None,
        "useProbability": True,
        "depth": 4, #  对应 Javascript 中 depth: 4,
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": None,
        "caseSensitive": None,
        "useGroupScoring": None,
        "automationId": "",
        "role": 1, #  对应 Javascript 中 role: 1,
        "sticky": 0,
        "cooldown": 0,
        "delay": 0,
        "displayIndex": display_index #  对应 Javascript 中 displayIndex: displayIndex
    }
    uid_counter += 1 #  对应 Javascript 中 uidCounter++;
    display_index += 1 #  对应 Javascript 中 displayIndex++;

    uploadFolderName = os.path.basename(root_dir) # 获取根文件夹名用于 worldbook 文件命名  对应 Javascript 中 const uploadFolderName = firstFile.webkitRelativePath.split('/')[0];

    for folder_path, dirnames, filenames in os.walk(root_dir): # 对应 Javascript 中 for (const file of files) 循环, 遍历文件夹
        # 对子文件夹列表 dirnames 进行名称排序  对应 Javascript 中 Array.from(fileInput.files).sort(...) 的排序逻辑
        dirnames.sort()
        # 对文件列表 filenames 进行名称排序  对应 Javascript 中 Array.from(fileInput.files).sort(...) 的排序逻辑
        filenames.sort()

        folderName = os.path.basename(folder_path) # 对应 Javascript 中 const folderName = filePath.split('/').slice(0, -1).join('/');
        if folderName == uploadFolderName: # 对应 Javascript 中 if (currentFolder !== folderName) 判断
            continue # 跳过根目录本身  对应 Javascript 中  if (currentFolder !== folderName)  的 continue;

        relative_folder_path = os.path.relpath(folder_path, root_dir) # 对应 Javascript 中 const filePath = file.webkitRelativePath;

        if current_folder != relative_folder_path: # 对应 Javascript 中 if (currentFolder !== folderName) 判断
            if current_folder != "": # 对应 Javascript 中  if (currentFolder !== "") 判断
                entries[uid_counter] = create_divider_entry(uid_counter, display_index, f"End of {current_folder}", None, False, folder_order) # 对应 Javascript 中 entries[uidCounter] = createDividerEntry(uidCounter, displayIndex, `End of ${currentFolder}`, null, false, folder_order);
                uid_counter += 1 #  对应 Javascript 中 uidCounter++;
                display_index += 1 #  对应 Javascript 中 displayIndex++;

            # 获取当前文件夹下的 .txt 和 .md 文件，并进行名称排序  对应 Javascript 中 const currentFolderFiles = files.filter(...).map(...);
            current_folder_files = sorted([os.path.splitext(f)[0] for f in filenames if f.endswith(('.txt', '.md'))]) #  对应 Javascript 中  .filter(f => f.webkitRelativePath.startsWith(folderName + '/'))  和 .map(f => f.name.split('.').slice(0, -1).join(''))
            entries[uid_counter] = create_divider_entry(uid_counter, display_index, relative_folder_path, current_folder_files, True, folder_order) # 对应 Javascript 中 entries[uidCounter] = createDividerEntry(uidCounter, displayIndex, `${folderName}`, currentFolderFiles, true, folder_order);
            uid_counter += 1 #  对应 Javascript 中 uidCounter++;
            display_index += 1 #  对应 Javascript 中 displayIndex++;
            current_folder = relative_folder_path #  对应 Javascript 中 currentFolder = folderName;
            folder_order += 10 #  对应 Javascript 中 folder_order += 10;

        for file_name in filenames: # 遍历排序后的 filenames 列表 对应 Javascript 中 for (const file of files) 循环
            if file_name.endswith(('.txt', '.md')): # 对应 Javascript 中 if (fileName.endsWith('.txt')) 判断, 修改为同时处理 .md
                file_path = os.path.join(folder_path, file_name) # 对应 Javascript 中 const filePath = file.webkitRelativePath;
                try: # 对应 Javascript 中  await file.text();
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read() # 对应 Javascript 中 const content = await file.text();
                except Exception as e:
                    print(f"读取文件 {file_path} 失败: {e}") # 对应 Javascript 中  错误处理
                    continue # 对应 Javascript 中 continue;

                info = extract_info(content, file_name, relative_folder_path, uploadFolderName, uid_counter, display_index) # 对应 Javascript 中 const info = extractInfo(content, fileName, filePath, uidCounter, displayIndex, fileSize);
                if info: # 对应 Javascript 中 if (info) 判断
                    depth = 4 # 默认深度  对应 Javascript 中 let depth = 4;
                    file_size = info["fileSize"] # 对应 Javascript 中 const fileSize = file.size;
                    if file_size <= 512: depth = 4 #  对应 Javascript 中 if (info["fileSize"] <= 512) depth = 4;
                    elif file_size <= 1024: depth = 5 #  对应 Javascript 中 else if (info["fileSize"] <= 1024) depth = 5;
                    elif file_size <= 1536: depth = 6 #  对应 Javascript 中 else if (info["fileSize"] <= 1536) depth = 6;
                    elif file_size <= 2048: depth = 7 #  对应 Javascript 中 else if (info["fileSize"] <= 2048) depth = 7;
                    else: depth = 8 #  对应 Javascript 中 else depth = 8;

                    order = folder_order + 1 #  对应 Javascript 中 let order = folder_order + 1;
                    entries[uid_counter] = create_entry(info, order, depth) # 对应 Javascript 中 entries[uidCounter] = createEntry(info, order, depth);
                    uid_counter += 1 #  对应 Javascript 中 uidCounter++;
                    display_index += 1 #  对应 Javascript 中 displayIndex++;

    if current_folder != "": # 对应 Javascript 中 if (currentFolder !== "") 判断
        entries[uid_counter] = create_divider_entry(uid_counter, display_index, f"End of {current_folder}", None, False, folder_order) # 对应 Javascript 中 entries[uidCounter] = createDividerEntry(uidCounter, displayIndex, `End of ${currentFolder}`, null, false, folder_order);

    worldbook = {"entries": entries} # 对应 Javascript 中 const worldbook = { "entries": entries };
    output = json.dumps(worldbook, indent=2, ensure_ascii=False) # 对应 Javascript 中 const output = JSON.stringify(worldbook, null, 2);

    try: # 对应 Javascript 中 try...catch 块
        output_filepath = f"「Ixia」-世界书 - {uploadFolderName}.json" #  文件名与 HTML 脚本保持一致 对应 Javascript 中 a.download = `「Ixia」-世界书 - ${uploadFolderName}.json`;
        with open(output_filepath, 'w', encoding='utf-8') as outfile: # 对应 Javascript 中  生成下载链接和文件下载
            outfile.write(output) # 对应 Javascript 中  生成下载链接和文件下载
        print(f"Worldbook JSON 文件生成成功: {output_filepath}") # 对应 Javascript 中 document.getElementById('output').textContent = output;  和  生成下载链接
    except Exception as e: # 对应 Javascript 中 try...catch 块
        print(f"生成 Worldbook JSON 文件失败: {e}") # 对应 Javascript 中  错误处理


if __name__ == "__main__":
    root_directory = select_directory()
    if root_directory:
        generate_worldbook_json(root_directory)
        print(f"请检查生成的 worldbook.json 文件。")
    else:
        print("用户取消操作。")