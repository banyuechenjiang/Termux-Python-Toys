import json
import os
import shutil
from datetime import datetime
from typing import List, Optional, Tuple

import yaml


class WorldbookManager:

  def __init__(self, root_dir: Optional[str] = None):
    self.root_dir = root_dir

  @staticmethod
  def select_directory() -> Optional[str]:
    current_dir = os.getcwd()
    print("-" * 30)
    print(f"当前工作目录: {current_dir}")
    print("-" * 30)

    all_items = [item for item in os.listdir('.') if os.path.isdir(item)]
    if not all_items:
      print("  当前目录下没有找到任何文件夹。")
      return None

    print("\n请选择要处理的文件夹 (输入数字 ID):")
    for i, item in enumerate(all_items):
      print(f"  {i + 1}. {item}")
    print("  0. 退出")

    while True:
      try:
        choice = int(input("请输入数字 ID (0 - {}): ".format(len(all_items))))
        if choice == 0:
          print("  您选择了退出操作。")
          return None
        elif 1 <= choice <= len(all_items):
          selected_dir = all_items[choice - 1]
          confirmation_input = input(
              f"您选择了: {selected_dir}, 确认选择此文件夹吗? (y/n, 默认: y): "
          ).lower()
          if confirmation_input == "" or confirmation_input == "y":
            print(f"  已确认选择文件夹: {selected_dir}")
            return selected_dir
          elif confirmation_input == "n":
            print("  已取消选择，请重新选择。")
          else:
            print("  无效的输入，请输入 'y' 或 'n' 或直接回车确认。")
        else:
          print("  无效的数字 ID，请输入有效范围内的数字。")
      except ValueError:
        print("  无效的输入，请输入数字。")

  @staticmethod
  def select_json_file() -> Optional[str]:
    current_dir = os.getcwd()
    print("-" * 30)
    print(f"当前工作目录: {current_dir}")
    print("-" * 30)

    all_files = os.listdir(".")
    json_files = [f for f in all_files if f.endswith(".json")]
    json_files.sort()

    if not json_files:
      print("  当前目录下没有找到任何 JSON 文件。")
      return None

    print("\n请选择要处理的 JSON 文件 (输入数字 ID):")
    for i, filename in enumerate(json_files):
      print(f"  {i + 1}. {filename}")
    print("  0. 退出")

    while True:
      try:
        choice = int(input("请输入数字 ID (0 - {}): ".format(len(json_files))))
        if choice == 0:
          print("  您选择了退出操作。")
          return None
        elif 1 <= choice <= len(json_files):
          selected_file = json_files[choice - 1]
          confirmation_input = input(
              f"您选择了: {selected_file}, 确认执行拆分吗? (y/n, 默认: y): "
          ).lower()
          if confirmation_input == "" or confirmation_input == "y":
            print(f"  已确认选择 JSON 文件: {selected_file}")
            return selected_file
          elif confirmation_input == "n":
            print("  已取消选择，请重新选择。")
          else:
            print("  无效的输入，请输入 'y' 或 'n' 或直接回车确认。")
        else:
          print("  无效的数字 ID，请输入有效范围内的数字。")
      except ValueError:
        print("  无效的输入，请输入数字。")

  @staticmethod
  def delete_split_directory() -> Optional[str]:
    current_dir = os.getcwd()
    print("-" * 30)
    print(f"当前工作目录: {current_dir}")
    print("-" * 30)

    split_directories = [
        item
        for item in os.listdir(".")
        if os.path.isdir(item) and item.endswith("-拆分")
    ]
    if not split_directories:
      print("  当前目录下没有找到任何以 '-拆分' 结尾的文件夹。")
      return None

    print("\n请选择要删除的拆分文件夹 (输入数字 ID):")
    for i, item in enumerate(split_directories):
      print(f"  {i + 1}. {item}")
    print("  0. 退出")

    while True:
      try:
        choice = int(input("请输入数字 ID (0 - {}): ".format(len(split_directories))))
        if choice == 0:
          print("  您选择了退出操作。")
          return None
        elif 1 <= choice <= len(split_directories):
          selected_dir = split_directories[choice - 1]
          print(f"  已选择删除文件夹: {selected_dir}")
          return selected_dir
        else:
          print("  无效的数字 ID，请输入有效范围内的数字。")
      except ValueError:
        print("  无效的输入，请输入数字。")

  def _create_entry(self, info: dict, order: int, depth: int) -> dict:
    return {
        "uid": info.get("uid"),
        "key": info.get("key"),
        "keysecondary": info.get("keysecondary"),
        "comment": info.get("comment"),
        "content": info.get("content"),
        "constant": False,
        "vectorized": False,
        "selective": True,
        "selectiveLogic": 0,
        "addMemo": True,
        "order": order,
        "position": 1,
        "disable": False,
        "excludeRecursion": False,
        "preventRecursion": True,
        "delayUntilRecursion": False,
        "probability": 100,
        "matchWholeWords": None,
        "useProbability": True,
        "depth": depth,
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": None,
        "caseSensitive": None,
        "useGroupScoring": None,
        "automationId": "",
        "role": None,
        "sticky": 0,
        "cooldown": 0,
        "delay": 0,
        "displayIndex": info.get("displayIndex"),
    }

  def _create_divider_entry(
      self,
      uid: int,
      display_index: int,
      text: str,
      fileList: Optional[List[str]] = None,
      isStart: bool = False,
      startOrder: int = 0,
  ) -> dict:
    # 使用 & 符号连接多层文件夹
    folderName = text.replace("\\", "&").split("/")[-1]
    content = ""
    position = 0
    order = 0
    random_directive_start = "{{random: "
    random_directive_end = "}}"
    # 确保列表标签与 key 一致
    list_start_tag = f"<{folderName}-列表>\n "
    list_end_tag = f"\n</{folderName}-列表>"

    if isStart:
      if fileList:
        fileListStr = ",".join(fileList)
        content = (
            list_start_tag
            + random_directive_start
            + fileListStr
            + random_directive_end
            + list_end_tag
        )

      position = 0
      order = startOrder
    else:
      position = (1,)
      order = startOrder + 2

    comment = f"--始 {text.replace('\\', '&')}--" if isStart else f"--{text.replace('\\', '&')} 终--"

    return {
        "uid": uid,
        "key": [folderName],  # key 也使用 & 符号连接
        "keysecondary": [],
        "comment": comment,
        "content": content,
        "constant": True,
        "vectorized": False,
        "selective": True,
        "selectiveLogic": 0,
        "addMemo": True,
        "order": order,
        "position": position[0] if isinstance(position, tuple) else position,
        "disable": False,
        "excludeRecursion": False,
        "preventRecursion": False,
        "delayUntilRecursion": False,
        "probability": 100,
        "matchWholeWords": None,
        "useProbability": True,
        "depth": 4,
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": None,
        "caseSensitive": None,
        "useGroupScoring": None,
        "automationId": "",
        "role": 1,
        "sticky": 0,
        "cooldown": 0,
        "delay": 0,
        "displayIndex": display_index,
    }

  def _extract_info(
      self,
      content: str,
      fileName: str,
      relative_folder_path: str,
      root_folder_name: str,
      uid: int,
      displayIndex: int,
  ) -> dict:
    title = os.path.splitext(fileName)[0]
    # 使用 & 符号连接多层文件夹
    if relative_folder_path:
      folderParts = relative_folder_path.replace("\\", "&").split("/")
      key_value = [folderParts[-1]]
    else:
      key_value = [root_folder_name]

    return {
        "uid": uid,
        "key": key_value,
        "keysecondary": [title],
        "comment": title,
        "content": content,
        "displayIndex": displayIndex,
        "fileSize": len(content.encode("utf-8")),
    }

  def generate_worldbook(
      self, output_filename: str = "worldbook.json", identifier: str = "Ixia", user_tags: str = ""
  ):
    if not self.root_dir:
      print("  错误：未设置根目录。请先使用 select_directory() 方法选择目录。")
      return

    print("-" * 30)
    print("  开始生成 世界书.json 文件...")
    print("-" * 30)

    entries = {}
    uid_counter = 0
    display_index = 0
    folder_order = 99
    folder_stack = []

    now = datetime.now()
    formatted_date = now.strftime("%Y/%m/%d %H:%M:%S")

    author_line = f"作者：{identifier}" if identifier else ""
    tags_line = f"标签：{user_tags}" if user_tags else "标签："

    metadata_content = r"""{{//
---
生成时间: %s
---
世界书描述：
%s
%s
---
配置信息：
         - 默认不区分大小写
         - 默认不触发递归
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
}}""" % (formatted_date, tags_line, author_line)

    entries[uid_counter] = {
        "uid": uid_counter,
        "key": [],
        "keysecondary": [],
        "comment": "【说明】",
        "content": metadata_content,
        "constant": True,
        "vectorized": False,
        "selective": False,
        "selectiveLogic": 0,
        "addMemo": True,
        "order": 98,
        "position": 0,
        "disable": False,
        "excludeRecursion": False,
        "preventRecursion": False,
        "delayUntilRecursion": False,
        "probability": 100,
        "matchWholeWords": None,
        "useProbability": True,
        "depth": 4,
        "group": "",
        "groupOverride": False,
        "groupWeight": 100,
        "scanDepth": None,
        "caseSensitive": None,
        "useGroupScoring": None,
        "automationId": "",
        "role": 1,
        "sticky": 0,
        "cooldown": 0,
        "delay": 0,
        "displayIndex": display_index,
    }
    uid_counter += 1
    display_index += 1

    uploadFolderName = os.path.basename(self.root_dir)
    total_files_processed = 0

    for folder_path, dirnames, filenames in os.walk(self.root_dir):
      dirnames.sort()
      filenames.sort()

      relative_folder_path = os.path.relpath(folder_path, self.root_dir)
      if relative_folder_path != ".":  # 检查是否为根目录的直接子目录/文件
        current_folder_files = sorted([
            os.path.splitext(f)[0]
            for f in filenames
            if f.endswith(('.txt', '.md', '.yaml', '.yml'))
        ])

        current_depth = relative_folder_path.replace("\\", "/").count("/")
        entries[uid_counter] = self._create_divider_entry(
            uid_counter,
            display_index,
            relative_folder_path,
            current_folder_files,
            True,
            folder_order,
        )
        folder_stack.append(
            {"path": relative_folder_path, "order": folder_order})
        uid_counter += 1
        display_index += 1
        folder_order += 10
        print(f"\n  处理文件夹: {relative_folder_path}")  # 关键：打印处理的文件夹

      for file_name in filenames:
        if file_name.endswith((".txt", ".md", ".yaml", ".yml")):
          file_path = os.path.join(folder_path, file_name)
          try:
            with open(file_path, "r", encoding="utf-8") as f:
              content = f.read()
          except Exception as e:
            print(f"  读取文件 {file_path} 失败: {e}")
            continue

          info = self._extract_info(
              content,
              file_name,
              relative_folder_path,
              uploadFolderName,
              uid_counter,
              display_index,
          )
          if info:
            depth = 4
            file_size = info["fileSize"]
            if file_size <= 512:
              depth = 4
            elif file_size <= 1024:
              depth = 5
            elif file_size <= 1536:
              depth = 6
            elif file_size <= 2048:
              depth = 7
            else:
              depth = 8

            order = 99 if relative_folder_path == "." else folder_order + 1
            entries[uid_counter] = self._create_entry(info, order, depth)
            uid_counter += 1
            display_index += 1
            total_files_processed += 1

    while folder_stack:
      folder_info = folder_stack.pop()
      entries[uid_counter] = self._create_divider_entry(
          uid_counter,
          display_index,
          f"{folder_info['path']}",
          None,
          False,
          folder_info["order"] + 2,
      )
      uid_counter += 1
      display_index += 1

    worldbook = {"entries": entries}
    output = json.dumps(worldbook, indent=2, ensure_ascii=False)

    try:
      identifier_for_filename = identifier if identifier else "Ixia"
      output_filepath = f"「{identifier_for_filename}」-世界书 - {uploadFolderName}.json"
      with open(output_filepath, "w", encoding="utf-8") as outfile:
        outfile.write(output)
      print(f"\n{'-' * 30}")
      print(f"  世界书.json 文件生成成功: {output_filepath}")
      print(f"  共处理了 {total_files_processed} 个文件。")
      print(f"{'-' * 30}")
    except Exception as e:
      print(f"  生成 世界书.json 文件失败: {e}")

  def split_worldbook(self, json_filepath: str, output_file_ext: str = "txt"):

    print("-" * 30)
    print(f"  开始处理 JSON 文件: {json_filepath}")
    print(f"  文件扩展名: .{output_file_ext}")
    print("-" * 30)
    try:
      with open(json_filepath, "r", encoding="utf-8") as f:
        worldbook_data = json.load(f)
    except FileNotFoundError:
      print(f"  错误: JSON 文件未找到: {json_filepath}")
      return
    except json.JSONDecodeError:
      print(
          "  错误: JSON 文件解析失败，请检查文件 '{json_filepath}' 格式是否正确，可能不是有效的 JSON 文件。"
      )
      return

    entries = worldbook_data.get("entries", {})
    total_entries = len(entries)
    processed_entries_count = 0

    print(f"  共计 {total_entries} 个条目待处理...")

    json_filename_without_ext = os.path.splitext(os.path.basename(json_filepath))[
        0]
    output_dir_base = json_filename_without_ext

    prefix_to_remove = "」-世界书 - "
    start_index = output_dir_base.find("「")
    end_index = output_dir_base.find(prefix_to_remove)

    if start_index != -1 and end_index != -1:
      identifier = output_dir_base[start_index +
                                   1:end_index]  # 提取识别名
      output_dir_base = output_dir_base[end_index +
                                        len(prefix_to_remove):]  # 提取剩余部分
    else:
      identifier = "Ixia"

    output_root_dir = f"{output_dir_base}-拆分"
    print(f"  文件将拆分到目录: {output_root_dir}")

    os.makedirs(output_root_dir, exist_ok=True)

    for entry_id, entry_data in entries.items():
      processed_entries_count += 1
      self._process_entry(
          entry_data,
          output_root_dir,
          output_file_ext,
          entry_id,
          processed_entries_count,
          total_entries,
      )

    print(f"\n{'-' * 30}")
    print(f"\n  世界书文件拆分处理完成，文件已保存到: {output_root_dir}")
    print(f"{'-' * 30}")

  def _is_metadata_entry(self, entry_data: dict) -> bool:
    return entry_data.get("comment") == "【说明】" and entry_data.get("uid") == 0

  def _is_divider_entry(self, entry_data: dict) -> bool:
    comment = entry_data.get("comment", "")
    return (
        (comment.startswith("--始 ") and comment.endswith("--"))
        or (comment.startswith("--") and comment.endswith(" 终--"))
    )

  def _extract_folder_name(self, entry_data: dict) -> Optional[str]:
    comment = entry_data.get("comment", "")
    # 根据注释提取文件夹名称，并处理 & 符号
    if comment.startswith("--始 ") and comment.endswith("--"):
      return comment[4:-2].replace("&", "\\")
    elif comment.startswith("--") and comment.endswith(" 终--"):
      return comment[2:-4].replace("&", "\\")
    else:
      key_list = entry_data.get("key")
      # 如果 key 是列表，则返回第一个元素（已经包含 & 符号）
      if isinstance(key_list, list) and key_list:
        return key_list[0]
      else:
        return None

  def _extract_file_name(
      self, entry_data: dict, output_file_ext: str, entry_id: str
  ) -> str:
    file_name = entry_data.get("comment", "").strip()
    if not file_name:
      keysecondary_list = entry_data.get("keysecondary")
      if isinstance(keysecondary_list, list) and keysecondary_list:
        file_name = keysecondary_list[0] + f".{output_file_ext}"
      elif isinstance(keysecondary_list, str) and keysecondary_list:
        file_name = keysecondary_list + f".{output_file_ext}"
      else:
        file_name = f"untitled_{entry_id}.{output_file_ext}"
    else:
      file_name = file_name + f".{output_file_ext}"
    return file_name

  def _process_entry(
      self,
      entry_data: dict,
      output_root_dir: str,
      output_file_ext: str,
      entry_id: str,
      processed_entries_count: int,
      total_entries: int,
  ):
    print(
        f"   处理条目 {processed_entries_count}/{total_entries} (ID: {entry_id})...",
        end="",
    )

    if self._is_metadata_entry(entry_data) or self._is_divider_entry(entry_data):
      if self._is_metadata_entry(entry_data):
          print(f' 跳过 "【说明】" 条目')
      return

    folder_path = self._extract_folder_name(entry_data)
    # 无条件创建完整路径（如果不存在）
    if folder_path:
        full_folder_path = os.path.join(output_root_dir, folder_path.replace("&", "\\"))
        os.makedirs(full_folder_path, exist_ok=True)
        # 仅在起始分隔符时打印创建文件夹的消息
        if entry_data.get("comment", "").startswith("--始 "):
            print(f"   创建文件夹: {full_folder_path}")
    else:
        full_folder_path = output_root_dir

    file_name = self._extract_file_name(entry_data, output_file_ext, entry_id)
    content = entry_data.get("content", "")

    try:
      filepath = os.path.join(full_folder_path, file_name)
      with open(filepath, "w", encoding="utf-8") as outfile:
          if output_file_ext in ("yaml", "yml"):
              yaml.dump(content, outfile, allow_unicode=True)
          else:
              outfile.write(str(content))
      print(f"   文件 '{file_name}' 创建成功。")
    except Exception as e:
      print(f"   写入文件 '{filepath}' 失败: {e}")

  def _extract_divider_info(
      self, entry_data: dict
  ) -> Tuple[Optional[str], Optional[List[str]]]:
    comment = entry_data.get("comment", "")
    content = entry_data.get("content", "")

    if comment.startswith("--始 ") and comment.endswith("--"):
      folder_name = comment[4:-2]  # 直接获取，无需替换
      file_list_str = content.strip()
      if file_list_str.startswith(f"<{folder_name}-列表>") and file_list_str.endswith(
          f"</{folder_name}-列表>"
      ):
        inner_content = file_list_str[
            len(f"<{folder_name}-列表>"): -len(f"</{folder_name}-列表>")
        ].strip()
        if inner_content.startswith("{{random: ") and inner_content.endswith(
            "}}"):
          random_content = inner_content[len("{{random: "):-2].strip()
          file_list = [f.strip()
                       for f in random_content.split(",") if f.strip()]
      return folder_name, file_list
    elif comment.startswith("--") and comment.endswith(" 终--"):
      folder_name = comment[2:-4].strip()  # 直接获取，无需替换
      return folder_name, None
    else:
      return None, None

  @staticmethod
  def delete_directory(dir_name: str):
    dir_path = os.path.join(os.getcwd(), dir_name)
    if not os.path.exists(dir_path):
      print(f"  错误: 文件夹 '{dir_name}' 不存在。")
      return

    if not os.path.isdir(dir_path):
      print(f"  错误: '{dir_name}' 不是一个文件夹。")
      return

    confirmation_input = input(
        f"  请确认您要**永久删除**文件夹 '{dir_name}' 及其所有内容 (输入 'yes' 确认): "
    ).lower()
    if confirmation_input == "yes":
      try:
        shutil.rmtree(dir_path)
        print(f"  文件夹 '{dir_name}' 及其内容已成功删除。")
      except Exception as e:
        print(f"  删除文件夹 '{dir_name}' 失败: {e}")
    else:
      print(f"  已取消删除文件夹 '{dir_name}' 操作。")


if __name__ == "__main__":
  worldbook_manager = WorldbookManager()

  while True:
    print("-" * 30)
    print("  欢迎使用 世界书 工具！")
    print("-" * 30)
    has_split_folders = any(
        item.endswith("-拆分") and os.path.isdir(item) for item in os.listdir(".")
    )
    operation_options = "请选择操作类型 (输入数字 0-{}):\n".format(
        2 + (1 if has_split_folders else 0)
    )
    operation_options += "1: 生成世界书 (从文件夹创建 .json 文件)\n"
    operation_options += "2: 提取世界书 (从 .json 文件创建文件夹和文件)\n"
    if has_split_folders:
      operation_options += "3: 删除 '-拆分' 后缀的文件夹及其内容 (谨慎操作)\n"
    operation_options += "0: 退出\n"

    operation_type = input(operation_options).strip()
    if operation_type == "1":
      root_directory = WorldbookManager.select_directory()
      if root_directory:
        identifier = (
            input("请输入识别名 (用于生成文件的名称, 默认为 Ixia；如果有输入会在【说明】中添加 作者): ").strip()
            or "Ixia"
        )
        user_tags = input(
            "请输入标签，多个标签请用逗号分隔 (例如: 标签1,标签2,  如果不需要标签，请直接按 Enter 键): "
        ).strip()
        worldbook_manager.root_dir = root_directory
        worldbook_manager.generate_worldbook(
            identifier=identifier, user_tags=user_tags
        )
        print(f"\n  操作完成，请检查生成的 世界书.json 文件。")
      else:
        print("\n  用户取消操作。")

    elif operation_type == "2":
      selected_json = WorldbookManager.select_json_file()
      if selected_json:
        output_ext = (
            input("请选择输出文件扩展名 (txt/md/yaml/yml, 默认为 txt): ").strip().lower()
            or "txt"
        )
        if output_ext not in ("txt", "md", "yaml", "yml"):
          print("  错误：无效的文件扩展名。使用默认扩展名 txt。")
          output_ext = "txt"
        worldbook_manager.split_worldbook(selected_json, output_ext)
        print(f"\n  操作完成，请检查拆分后的文件夹。")
      else:
        print("\n  用户取消操作。")

    elif operation_type == "3" and has_split_folders:
      selected_split_dir = WorldbookManager.delete_split_directory()
      if selected_split_dir:
        WorldbookManager.delete_directory(selected_split_dir)
      else:
        print("\n  用户取消删除文件夹操作。")

    elif operation_type == "0":
      print("  您选择了退出程序。")
      break
    else:
      print(
          "  无效的操作类型，请输入 0, 1, 2{}。".format(
              ", 3" if has_split_folders else ""
          )
      )
    print("-" * 30)
    print("  操作完成. 您可以继续选择其他操作或退出。")
    print("-" * 30)

  print("-" * 30)
  print("  感谢使用！")
  print("-" * 30)