#!/usr/bin/env python3
import argparse
import inspect
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections import defaultdict
from functools import partial
from itertools import groupby
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

import send2trash
import yaml

class AppSettings:
    SCRIPT_VERSION = "5.0"
    DEFAULT_WATCH_PORT = "6620"
    GROUP_SEPARATOR = '&'
    COLLECTION_SUFFIXES = ("合集", "collection")
    IGNORED_FILE_SUBSTRINGS = {".vscode", ".idea", ".DS_Store"}
    ILLEGAL_WINDOWS_CHARS = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    REPLACEMENT_CHARS = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨']
    PUBLISH_README_CONTENT = """# 使用说明

本文件夹保存了编写角色卡/世界书/插件所使用的一些原始内容.

## 世界书

如果本源文件涉及世界书, 它通常是脚本自动同步过去省 token 的, 因此在酒馆里可能比较难看.
你可以直接看本源文件中的相关内容, 也可以搭配 https://sillytavern-stage-girls-dog.readthedocs.io/tool_and_experience/lorebook_script 查看

## 脚本

如果本源文件涉及代码脚本, 它可能是用 JavaScript 或 TypeScript 编写, 再使用打包软件打包到酒馆的, 因此在酒馆里可能比较难看.
你可以直接看本源文件中的相关内容, 也可以配着用 https://sillytavern-stage-girls-dog.readthedocs.io/tool_and_experience/js_slash_runner 查看.
"""
    HELP_TEXT = """命令功能说明:
  extract   - 从世界书文件 (.json) 提取条目到本地文件夹。
  push      - 将本地文件夹的修改同步到世界书文件 (.json)。
  pull      - 从世界书文件 (.json) 拉取最新内容覆盖本地文件。
  
  watch     - 实时监听本地文件变动并自动推送到酒馆网页；需要酒馆额外拓展  
  publish   - 将角色卡和源文件打包发布到目标文件夹。
  
  to_json   - 批量将文件夹内 .yaml 文件转换为 .json 文件。
  to_yaml   - 批量将文件夹内 .json 文件转换为 .yaml 文件。
  其他详见文档 https://sillytaverm-stage-girls-dog.readthedocs.io/工具经验/世界书同步脚本/文件格式

  固有缺陷：因为是一对一的，处理不好注释同名的世界书，请做好区分

"""

class Entry:
    def __init__(self, title: str, file: Path, content: str, spaces: str, type: str):
        self.title, self.file, self.content, self.spaces, self.type = title, file, content, spaces, type

def sanitize_filename_component(name: str) -> str:
    sanitized_name = name.replace('\n', ' ').replace('\r', '')
    if sys.platform not in ['win32', 'cygwin']: return sanitized_name.strip()
    for char, replacement in zip(AppSettings.ILLEGAL_WINDOWS_CHARS, AppSettings.REPLACEMENT_CHARS):
        sanitized_name = sanitized_name.replace(char, replacement)
    return sanitized_name.strip()

def desanitize_filename_component(name: str) -> str:
    if sys.platform not in ['win32', 'cygwin']: return name
    desanitized_name = name
    for char, replacement in zip(AppSettings.ILLEGAL_WINDOWS_CHARS, AppSettings.REPLACEMENT_CHARS):
        desanitized_name = desanitized_name.replace(replacement, char)
    return desanitized_name

def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as f: return yaml.safe_load(f)

def confirm_action(action: str, default_yes: bool = True) -> bool:
    prompt = f" (yes/no, 默认为 {'yes' if default_yes else 'no'}): "
    response = input(f"{action}{prompt}").strip().lower()
    if response == "": return default_yes
    return response in ["yes", "y"]

def extract_file_content(file_path: Path, user_name: Optional[str]) -> str:
    content = file_path.read_text(encoding="utf-8")
    if user_name and user_name != "<user>" and user_name in content:
        content = content.replace(user_name, "<user>")
        file_path.write_text(content, encoding="utf-8")
        print(f"{file_path}: 已替换 {user_name} 为 <user>")
    return content

def run_subprocess(args: List[str], **kwargs) -> subprocess.CompletedProcess:
    if sys.platform == "win32" and 'creationflags' not in kwargs:
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(args, check=True, text=True, encoding="utf-8", **kwargs)

def _toggle_special_blocks_content(content: str, mode: str) -> str:
    lines, new_lines, in_block = content.splitlines(), [], False
    for line in lines:
        stripped = line.strip()
        is_start, is_end = stripped.startswith('<%'), stripped.endswith('%>')
        if mode == 'comment':
            if is_start: in_block = True
            new_lines.append(f"# {line}" if in_block else line)
            if is_end: in_block = False
        elif mode == 'uncomment':
            is_commented_start = stripped.startswith('# <') and stripped.endswith('%')
            is_commented_line = stripped.startswith('# ')
            if is_commented_start or (in_block and is_commented_line):
                new_lines.append(line.lstrip('# '))
            else: new_lines.append(line)
            if is_commented_start or (in_block and is_commented_line and is_end): in_block = False
            if is_commented_start: in_block = True
    return "\n".join(new_lines)

def _toggle_special_blocks(file_path: Path, mode: str):
    content = file_path.read_text(encoding='utf-8')
    modified_content = _toggle_special_blocks_content(content, mode)
    if content != modified_content: file_path.write_text(modified_content, encoding='utf-8')

def to_flow_yaml(path: Path) -> str:
    original_content = path.read_text(encoding='utf-8')
    lines = original_content.strip().splitlines()
    start_match = re.match(r'^\s*#\s*:\s*<([^>]+)>', lines[0]) if lines else None
    end_match = re.match(r'^\s*#\s*:\s*</([^>]+)>', lines[-1]) if lines else None
    is_tagged = start_match and end_match and start_match.group(1) == end_match.group(1)
    wrapper_start, wrapper_end, content_to_process = (lines[0], lines[-1], "\n".join(lines[1:-1])) if is_tagged else ("", "", original_content)
    try:
        commented = _toggle_special_blocks_content(content_to_process, 'comment')
        flow = run_subprocess(["yq", '.. style="flow"'], input=commented, stdout=subprocess.PIPE).stdout.strip()
        uncommented = _toggle_special_blocks_content(flow, 'uncomment')
        return f"{wrapper_start}\n{uncommented}\n{wrapper_end}" if is_tagged else uncommented
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"警告: 无法将 '{path.name}' 转换为 flow-style YAML, 将按原样处理。")
        return original_content

def _split_entries(path: Path, content: str, file_type: str, should_trim: bool, comment_prefix: str) -> List[Entry]:
    processed_content = content
    if should_trim:
        if file_type == "yaml": processed_content = to_flow_yaml(path)
        elif file_type == "json":
            lines = content.strip().splitlines()
            start_match = re.match(r'^\s*#\s*:\s*<([^>]+)>', lines[0]) if lines else None
            end_match = re.match(r'^\s*#\s*:\s*</([^>]+)>', lines[-1]) if lines else None
            is_tagged = start_match and end_match and start_match.group(1) == end_match.group(1)
            def trim_logic(text: str) -> str: return re.sub(r'("[^"]*")|(\s+)(//.*\n)?', lambda m: m.group(1) or m.group(3), text)
            if is_tagged:
                processed_content = f"{lines[0]}\n{trim_logic('\n'.join(lines[1:-1]))}\n{lines[-1]}"
            else: processed_content = trim_logic(content)
    pattern = re.compile(rf"( *){re.escape(comment_prefix)} \^([^\n]+)\n([\s\S]*?)((?= *{re.escape(comment_prefix)} \^[^\n]+\n)|\Z)", re.MULTILINE)
    codify_pattern = rf"( *){re.escape(comment_prefix)} :(.*)"
    return [Entry(title=m.group(2).strip(), file=path, content=re.sub(codify_pattern, r'\2', m.group(3)).rstrip(), spaces=m.group(1), type=file_type) for m in pattern.finditer(processed_content)]

def read_entries(directory: Path, should_trim: bool, user_name: Optional[str]) -> List[Entry]:
    entries = []
    for path in directory.rglob("*"):
        if not path.is_file() or any(sub in path.name for sub in AppSettings.IGNORED_FILE_SUBSTRINGS) or path.stem.endswith("!"): continue
        content = extract_file_content(path, user_name)
        if path.stem.endswith(AppSettings.COLLECTION_SUFFIXES):
            file_type = path.suffix.strip('.')
            comment_prefix, start_token = ("//", "// ^") if file_type == "json" else ("#", "# ^")
            if not content.lstrip().startswith(start_token): raise RuntimeError(f"解析 '{path}' 出错, 合集文件开头必须是 '{start_token}条目名'")
            collection_entries = _split_entries(path, content, file_type, should_trim, comment_prefix)
            group_name = path.stem
            for suffix in AppSettings.COLLECTION_SUFFIXES: group_name = group_name.removesuffix(suffix)
            desanitized_group_name = desanitize_filename_component(group_name)
            for entry in collection_entries: entry.title = f"{desanitized_group_name}{AppSettings.GROUP_SEPARATOR}{entry.title}"
            entries.extend(collection_entries)
        else:
            file_type = path.suffix.strip('.')
            if file_type == "yaml":
                if should_trim: content = to_flow_yaml(path)
                content = re.sub(r"( *)\# :(.*)", r'\2', content)
            elif file_type == "json":
                if should_trim:
                    lines = content.strip().splitlines()
                    start_match = re.match(r'^\s*#\s*:\s*<([^>]+)>', lines[0]) if lines else None
                    end_match = re.match(r'^\s*#\s*:\s*</([^>]+)>', lines[-1]) if lines else None
                    is_tagged = start_match and end_match and start_match.group(1) == end_match.group(1)
                    def trim_logic(text: str) -> str: return re.sub(r'("[^"]*")|(\s+)(//.*\n)?', lambda m: m.group(1) or m.group(3), text)
                    if is_tagged: content = f"{lines[0]}\n{trim_logic('\n'.join(lines[1:-1]))}\n{lines[-1]}"
                    else: content = trim_logic(content)
                content = re.sub(r"( *)// :(.*)", r'\2', content)
            entries.append(Entry(title=desanitize_filename_component(path.stem), file=path, content=content.strip(), spaces="", type="normal"))
    return entries

def write_entries(entries: List[Entry]):
    for file, grouped_entries in groupby(sorted(entries, key=lambda x: x.file), key=lambda x: x.file):
        entry_list = list(grouped_entries)
        if entry_list[0].type == 'normal':
            content = entry_list[0].content
        else:
            comment_prefix = '#' if entry_list[0].file.suffix != '.json' else '//'
            content = "\n".join(f"{e.spaces}{comment_prefix} ^{e.title.split(AppSettings.GROUP_SEPARATOR, 1)[-1]}\n{e.content}" for e in entry_list)
        file.write_text(content.strip() + "\n", encoding="utf-8")

def read_json(json_file: Path) -> dict:
    with json_file.open(encoding="utf-8") as f: return json.load(f)

def write_json(json_file: Path, data: dict):
    with json_file.open("w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

def push_impl(directory: Path, json_data: dict, user_name: Optional[str], should_trim: bool) -> Tuple[bool, dict]:
    entries = read_entries(directory, should_trim, user_name)
    changed = False

    local_entries_by_title = defaultdict(list)
    for e in entries:
        local_entries_by_title[e.title].append(e)

    for entry_data in json_data.get("entries", {}).values():
        title = entry_data.get("comment", "").strip()

        if title in local_entries_by_title and local_entries_by_title[title]:
            matching_entry = local_entries_by_title[title].pop(0)

            if entry_data.get("content", "").strip() != matching_entry.content.strip():
                entry_data["content"] = matching_entry.content
                changed = True
        else:
            raise RuntimeError(f"未找到酒馆世界书中条目 '{title}' 对应的文件，或本地同名文件数量少于酒馆世界书中的条目数量。")

    leftover_entries = []
    for title, entry_list in local_entries_by_title.items():
        if entry_list:
            leftover_entries.extend([f'{e.title}({e.file.name})' for e in entry_list])

    if leftover_entries:
        raise RuntimeError(f"未能在酒馆世界书中找到以下本地文件对应的条目: {', '.join(leftover_entries)}")

    if 'originalData' in json_data:
        del json_data['originalData']
        changed = True

    return changed, json_data

def push(directory: Path, lorebook_file: Path, user_name: Optional[str], no_trim: bool, need_confirm: bool):
    if need_confirm and not confirm_action("将本地修改推送到世界书文件?"): return print("取消推送")
    json_data = read_json(lorebook_file)
    changed, updated_json_data = push_impl(directory, json_data, user_name, not no_trim)
    if changed:
        write_json(lorebook_file, updated_json_data)
        print("世界书已更新并成功推送。")
    else: print("内容无变化，无需推送。")

def format_files(directory: Path, extension: str, command: List[str]):
    files = [p for p in directory.rglob(f"*.{extension}") if p.is_file()]
    if not files: return
    try: run_subprocess([command[0], "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (FileNotFoundError, subprocess.CalledProcessError): return print(f"警告: 未找到 '{command[0]}', 跳过 .{extension} 文件格式化。")
    for file_path in files:
        try:
            _toggle_special_blocks(file_path, 'comment')
            run_subprocess(command + [str(file_path)])
            _toggle_special_blocks(file_path, 'uncomment')
        except subprocess.CalledProcessError:
            print(f"格式化 '{file_path.name}' 失败, 可能不是有效的 {extension}。已跳过。")
            try: _toggle_special_blocks(file_path, 'uncomment')
            except Exception: pass
            file_path.rename(file_path.with_suffix(".md"))
            print(f" -> 已将 '{file_path.name}' 重命名为 '{file_path.with_suffix('.md').name}'")

def pull(directory: Path, lorebook_file: Path, user_name: Optional[str], need_confirm: bool):
    if need_confirm and not confirm_action("将世界书文件拉取到本地?"): return print("取消拉取")
    entries, json_data = read_entries(directory, False, user_name), read_json(lorebook_file)
    entry_map = {e.title: e for e in entries}
    for entry_data in json_data.get("entries", {}).values():
        title = entry_data.get("comment", "").strip()
        if title in entry_map:
            content, _, _ = _detect_format(entry_data.get("content", ""))
            entry_map[title].content = content.strip()
        else: raise RuntimeError(f"未找到条目 '{title}' 对应的文件, 请在本地创建 '{sanitize_filename_component(title)}.md'")
    write_entries(entries)
    format_files(directory, "json", ["clang-format", "-i"])
    format_files(directory, "yaml", ["yq", '... style=""', "-i"])
    print("成功拉取")

def is_valid_format(content: str, extension: str) -> bool:
    try:
        run_subprocess(["yq", "-p", extension, "-e"], input=content, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError): return False

def _detect_format(content: str) -> Tuple[str, str, str]:
    stripped = content.strip()
    if not stripped: return content, ".md", "#"
    writing, detection = content, stripped
    tag_match = re.fullmatch(r'\s*<([^>]+)>(.*?)[\s\n]*</\1>\s*', content, re.DOTALL)
    if tag_match:
        writing = f"# :<{tag_match.group(1)}>\n{tag_match.group(2)}\n# :</{tag_match.group(1)}>"
        detection = tag_match.group(2)
    parsable = _toggle_special_blocks_content(detection, 'comment')
    if (parsable.startswith('{') or parsable.startswith('[')) and is_valid_format(parsable, "json"): return writing, ".json", "//"
    if re.search(r"^\s*[^\s:]+\s*:\s+.+", parsable, re.MULTILINE) and is_valid_format(parsable, "yaml"): return writing, ".yaml", "#"
    return writing, ".md", "#"

def extract(directory: Path, lorebook_file: Path, no_detect: bool, group: bool, need_confirm: bool):
    action_desc = f"将 {lorebook_file.name} 提取到 {directory}"
    if group: action_desc += " (并合并 '合集名&条目名' 格式的条目)"
    if need_confirm and not confirm_action(f"{action_desc}?"): return print("取消提取")
    if directory.exists() and any(directory.iterdir()):
        if need_confirm and not confirm_action("提取目标文件夹非空, 将清空并继续?"): return print("操作因文件夹非空而取消。")
        send2trash.send2trash(str(directory))
    directory.mkdir(parents=True, exist_ok=True)
    json_data = read_json(lorebook_file)
    single_entries, grouped_entries = [], defaultdict(list)
    for entry in json_data.get("entries", {}).values():
        title = entry.get("comment", "").strip()
        if group and AppSettings.GROUP_SEPARATOR in title:
            group_name, entry_title = title.split(AppSettings.GROUP_SEPARATOR, 1)
            grouped_entries[group_name.strip()].append({'title': entry_title.strip(), 'content': entry.get("content", "")})
        else: single_entries.append(entry)
    for group_name, items in grouped_entries.items():
        if not items: continue
        _, ext, prefix = _detect_format(items[0]['content']) if not no_detect else (items[0]['content'], ".md", "#")
        full_content = []
        for item in items:
            content, detected_ext, _ = _detect_format(item['content']) if not no_detect else (item['content'], ".md", "#")
            if detected_ext != ext: print(f"警告: 合集 '{group_name}' 中条目 '{item['title']}' 格式({detected_ext})与首个条目({ext})不一致。")
            full_content.append(f"{prefix} ^{item['title']}\n{content}")
        (directory / f"{sanitize_filename_component(group_name)}合集{ext}").write_text("\n".join(full_content).strip() + "\n", encoding='utf-8')
    for entry in single_entries:
        title = entry.get("comment", "").strip()
        content, ext, _ = _detect_format(entry.get("content", "")) if not no_detect else (entry.get("content", ""), ".md", "#")
        (directory / f"{sanitize_filename_component(title)}{ext}").write_text(content.strip() + "\n", encoding='utf-8')
    if not no_detect:
        print("正在格式化提取的文件...")
        format_files(directory, "json", ["clang-format", "-i"])
        format_files(directory, "yaml", ["yq", '... style=""', "-i"])
    print("成功提取")

def watch(directory: Path, lorebook_name: str, user_name: Optional[str], no_trim: bool, port: str):
    try:
        import socketio, tornado.ioloop, tornado.web, watchfiles
    except ImportError:
        print("错误: watch 功能需额外依赖。请运行 'pip install python-socketio tornado watchfiles'")
        sys.exit(1)
    
    sio = socketio.AsyncServer(cors_allowed_origins='*', async_mode='tornado')
    
    async def push_once(reason: str):
        print(f"{'='*80}\n{reason}")
        async def update_lorebook(data: Optional[dict]):
            if data:
                try:
                    changed, updated_json = push_impl(directory, data, user_name, not no_trim)
                    if changed:
                        await sio.emit('lorebook_updated', {'name': lorebook_name, 'content': json.dumps(updated_json)})
                        print(f"成功将更新推送到 '{lorebook_name}'")
                    else: print("内容无变化，无需推送。")
                except Exception as e: print(f'推送错误: {e}')
            else: print("错误: 未在酒馆网页中找到相应世界书")
            print('='*80)
        await sio.emit('request_lorebook_update', {'name': lorebook_name}, callback=update_lorebook)
    
    @sio.event
    async def connect(sid, *_): await push_once(f"成功连接到酒馆网页 '{sid}', 初始化推送...")
    
    @sio.event
    async def disconnect(sid, reason=None): print(f"与酒馆网页 '{sid}' 断开连接" + (f" (原因: {reason})" if reason else ""))
    
    async def background_task():
        async for changes in watchfiles.awatch(directory): await push_once(f"检测到文件变化: {', '.join(map(str, {c[1] for c in changes}))}")
    
    sio.start_background_task(background_task)
    
    print(f'正在监听: http://0.0.0.0:{port} (按 Ctrl+C 退出)')
    app = tornado.web.Application([('/socket.io/', socketio.get_tornado_handler(sio))])
    app.listen(port=int(port))
    
    try:
        tornado.ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        print("\n监听已停止。")
        tornado.ioloop.IOLoop.current().stop()

def publish(publish_dir: Path, character_card: Optional[Path], source_dir: Optional[Path], should_zip: bool, need_confirm: bool):
    publish_list = ""
    if character_card: publish_list += f"\n- 角色卡: {character_card}"
    if source_dir: publish_list += f"\n- 源文件文件夹: {source_dir}"
    if need_confirm and not confirm_action(f"将以下文件发布到 {publish_dir} 文件夹下?{publish_list}"): return print("取消发布")
    publish_dir.mkdir(parents=True, exist_ok=True)
    if character_card: shutil.copy(character_card, publish_dir); print(f"已复制角色卡到 {publish_dir}")
    if source_dir:
        dest_dir, dest_zip = publish_dir / "源文件", publish_dir / "源文件.zip"
        if dest_dir.exists(): send2trash.send2trash(str(dest_dir))
        if dest_zip.exists(): send2trash.send2trash(str(dest_zip))
        if should_zip:
            with zipfile.ZipFile(dest_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file in source_dir.rglob('*'):
                    if file.is_file() and not any(sub in str(file) for sub in AppSettings.IGNORED_FILE_SUBSTRINGS):
                        zf.write(file, Path("世界书源文件") / file.relative_to(source_dir))
                zf.writestr(str(Path("世界书源文件") / "README.md"), AppSettings.PUBLISH_README_CONTENT)
            print(f"已创建源文件压缩包于 {dest_zip}")
        else:
            shutil.copytree(source_dir, dest_dir, ignore=lambda d, f: [x for x in f if any(s in str(Path(d, x)) for s in AppSettings.IGNORED_FILE_SUBSTRINGS)])
            (dest_dir / "README.md").write_text(AppSettings.PUBLISH_README_CONTENT, encoding="utf-8")
            print(f"已拷贝 {source_dir} 到 {dest_dir} 中")
    print("成功发布")

def convert_extension(directory: Path, old_ext: str, new_ext: str, need_confirm: bool):
    if need_confirm and not confirm_action(f"将 {directory} 中所有 {old_ext} 文件转换为 {new_ext} 文件?"): return print("取消转换")
    for path in directory.rglob(f"*{old_ext}"):
        if not path.is_file(): continue
        try:
            run_subprocess(["yq", '.. style=""', "-p", old_ext[1:], "-o", new_ext[1:], "-i", str(path)])
            path.rename(path.with_suffix(new_ext))
        except (subprocess.CalledProcessError, FileNotFoundError): print(f"转换 '{path.name}' 失败，已跳过。")

COMMAND_REGISTRY = {
    'extract': {'handler': extract, 'help': '从世界书文件提取条目', 'interactive_desc': '提取',
        'cli_args': [
            {"name": "--no_detect", "action": "store_true", "help": "禁用格式自动检测，所有条目提取为 .md 文件。"},
            {"name": "--group", "action": "store_true", "help": f"将 标题'{AppSettings.GROUP_SEPARATOR}条目名' 格式的条目，合并为合集文件。"}],
        'interactive_prompts': [
            {"key": "no_detect", "text": "自动检测 .json/.yaml 格式? (禁用将全转为 .md)", "type": "bool_neg"},
            {"key": "group", "text": "是否将 '合集名&条目名' 格式的条目合并为文件?", "type": "bool", "default": False}],
        'required_paths': {'directory': {'key': '世界书本地文件夹', 'must_exist': False}, 'lorebook_file': {'key': '世界书酒馆文件', 'is_file': True}}},
    'push': {'handler': push, 'help': '将本地修改推送到世界书文件', 'interactive_desc': '推送',
        'cli_args': [{"name": "--no_trim", "action": "store_true", "help": "推送时不压缩条目内容。"}],
        'interactive_prompts': [{"key": "no_trim", "type": "bool", "cli_help_ref": "--no_trim"}],
        'required_paths': {'directory': {'key': '世界书本地文件夹', 'is_dir': True}, 'lorebook_file': {'key': '世界书酒馆文件', 'is_file': True}},
        'uses_user_name': True},
    'pull': {'handler': pull, 'help': '从世界书文件拉取内容到本地', 'interactive_desc': '拉取',
        'required_paths': {'directory': {'key': '世界书本地文件夹', 'is_dir': True}, 'lorebook_file': {'key': '世界书酒馆文件', 'is_file': True}},
        'uses_user_name': True},
    'watch': {'handler': watch, 'help': '实时监听本地文件并推送到酒馆网页', 'interactive_desc': '监听',
        'cli_args': [
            {"name": "--no_trim", "action": "store_true", "help": "推送时不压缩条目内容。"},
            {"name": "--port", "default": AppSettings.DEFAULT_WATCH_PORT, "help": f"监听端口号。"}],
        'interactive_prompts': [
            {"key": "no_trim", "type": "bool", "cli_help_ref": "--no_trim"},
            {"key": "port", "text": f"监听端口号 (默认{AppSettings.DEFAULT_WATCH_PORT}): ", "type": "str", "default": AppSettings.DEFAULT_WATCH_PORT}],
        'required_paths': {'directory': {'key': '世界书本地文件夹', 'is_dir': True}}, 'uses_lorebook_name': True, 'uses_user_name': True},
    'publish': {'handler': publish, 'help': '打包发布角色卡和源文件', 'interactive_desc': '发布',
        'cli_args': [{"name": "--should_zip", "action": "store_true", "help": "发布时将源文件文件夹压缩为 zip。"}],
        'interactive_prompts': [{"key": "should_zip", "type": "bool", "cli_help_ref": "--should_zip"}],
        'required_paths': {'publish_dir': {'key': '发布目标文件夹', 'must_exist': False}}, 'uses_optional_paths': True},
    'to_json': {'handler': partial(convert_extension, old_ext=".yaml", new_ext=".json"), 'help': '批量转换 .yaml 为 .json', 'interactive_desc': '转为JSON',
        'required_paths': {'directory': {'key': '世界书本地文件夹', 'is_dir': True}}},
    'to_yaml': {'handler': partial(convert_extension, old_ext=".json", new_ext=".yaml"), 'help': '批量转换 .json 为 .yaml', 'interactive_desc': '转为YAML',
        'required_paths': {'directory': {'key': '世界书本地文件夹', 'is_dir': True}}},
}

def as_path(config: dict, key: str, **kwargs) -> Path:
    if key not in config: raise RuntimeError(f"配置文件中未配置 '{key}'")
    path = Path(config[key])
    if kwargs.get('must_exist', True) and not path.exists(): raise RuntimeError(f"路径 '{path}' (配置项: '{key}') 不存在")
    if kwargs.get('is_dir') and not path.is_dir(): raise RuntimeError(f"路径 '{path}' (配置项: '{key}') 不是一个文件夹")
    if kwargs.get('is_file') and not path.is_file(): raise RuntimeError(f"路径 '{path}' (配置项: '{key}') 不是一个文件")
    return path

def run_command(command: str, config_data: Dict, args: Any):
    cmd_config = COMMAND_REGISTRY[command]
    handler = cmd_config['handler']
    all_possible_kwargs = {'need_confirm': not getattr(args, 'y', False)}

    arg_keys = set()
    for arg_list_key in ['cli_args', 'interactive_prompts']:
        for arg_conf in cmd_config.get(arg_list_key, []):
            key = arg_conf.get('key') or arg_conf.get('name', '').lstrip('-').replace('-', '_')
            if key: arg_keys.add(key)
    for key in arg_keys:
        if hasattr(args, key): all_possible_kwargs[key] = getattr(args, key)

    if 'required_paths' in cmd_config:
        for name, path_conf in cmd_config['required_paths'].items():
            all_possible_kwargs[name] = as_path(config_data, **path_conf)
            
    if cmd_config.get('uses_user_name'): all_possible_kwargs['user_name'] = config_data.get('玩家名')
    if cmd_config.get('uses_lorebook_name'):
        try: lorebook_name = as_path(config_data, key='世界书酒馆文件', is_file=True).stem
        except RuntimeError: lorebook_name = config_data.get('世界书名称')
        if not lorebook_name: raise RuntimeError("配置文件中必须提供 '世界书酒馆文件' 或 '世界书名称' 用于 watch 功能。")
        all_possible_kwargs['lorebook_name'] = lorebook_name
    if cmd_config.get('uses_optional_paths'):
        all_possible_kwargs['character_card'] = as_path(config_data, key='角色卡', is_file=True) if '角色卡' in config_data else None
        all_possible_kwargs['source_dir'] = as_path(config_data, key='源文件文件夹', is_dir=True) if '源文件文件夹' in config_data else None
        if not all_possible_kwargs.get('character_card') and not all_possible_kwargs.get('source_dir'): raise RuntimeError("无可发布内容。")

    handler_params = inspect.signature(handler).parameters.keys()
    final_kwargs = {key: val for key, val in all_possible_kwargs.items() if key in handler_params}
    handler(**final_kwargs)

def run_interactive_mode(configs: Dict):
    print(f"{'-'*38}\nTavern Sync v{AppSettings.SCRIPT_VERSION}\n{'-'*38}")
    if not configs: return print("错误: 配置文件 tavern_sync_config.yaml 为空或不存在。")
    cmd_map = {str(i+1): cmd for i, cmd in enumerate(COMMAND_REGISTRY)}
    while True:
        print("\n请选择操作 (输入数字):")
        for key, cmd in cmd_map.items(): print(f"  {key}: {COMMAND_REGISTRY[cmd]['interactive_desc']} ({cmd})")
        print("  0: 退出 (exit)")
        choice = input("您的选择 (输入 'h' 获取帮助): ").strip().lower()
        if choice == 'h': print(AppSettings.HELP_TEXT); continue
        if choice == "0" or not choice: break
        if choice not in cmd_map: print("无效输入。"); continue
        command = cmd_map[choice]

        print("\n请选择要操作的配置:")
        config_list = list(configs.keys())
        for i, name in enumerate(config_list, 1): print(f"  {i}: {name}")
        print("  0: 返回上一级")
        
        try:
            idx_input = input(f"配置选择 (0-{len(config_list)}): ").strip()
            if not idx_input or idx_input == "0": continue
            config_name, config_data = config_list[int(idx_input) - 1], configs[config_list[int(idx_input) - 1]]
        except (ValueError, IndexError):
            print("无效的配置选择。")
            continue

        try:
            args, cmd_config = argparse.Namespace(y=False), COMMAND_REGISTRY[command]
            cli_help_map = {arg['name']: arg['help'] for arg in cmd_config.get('cli_args', []) if 'help' in arg}
            for prompt in cmd_config.get('interactive_prompts', []):
                prompt_text = prompt.get('text', cli_help_map.get(prompt.get('cli_help_ref', ''), ''))
                if not prompt_text: continue
                key, p_type = prompt['key'], prompt['type']
                if p_type in ("bool", "bool_neg"):
                    val = confirm_action(prompt_text, default_yes=prompt.get('default', True))
                    if p_type == "bool_neg": val = not val
                elif p_type == "str":
                    user_input = input(f"{prompt_text} ").strip()
                    val = user_input if user_input else prompt["default"]
                setattr(args, key, val)
            
            print("-" * 38)
            run_command(command, config_data, args)
            print("-" * 38)
        except Exception as e:
            print(f"\n!! 操作失败: {e}\n")
        
        input("按 Enter键 返回主菜单...")

def main():
    try:
        config_path = Path(__file__).parent / "tavern_sync_config.yaml"
        if not config_path.exists(): config_path.write_text("{}", encoding="utf-8")
        configs = load_config(config_path) or {}
        if not len(sys.argv) > 1: return run_interactive_mode(configs)
        parser = argparse.ArgumentParser(description=f"Tavern Sync v{AppSettings.SCRIPT_VERSION}", epilog=AppSettings.HELP_TEXT, formatter_class=argparse.RawTextHelpFormatter)
        subparsers = parser.add_subparsers(dest="command", required=True)
        for cmd, config in COMMAND_REGISTRY.items():
            p = subparsers.add_parser(cmd, help=config.get("help", ""))
            p.add_argument("config_name", choices=list(configs.keys()), help="配置文件中的配置名称")
            p.add_argument("-y", action="store_true", help="跳过所有确认步骤")
            for arg_config in config.get('cli_args', []):
                local_arg_config = arg_config.copy()
                name = local_arg_config.pop("name")
                p.add_argument(name, **local_arg_config)
        args = parser.parse_args()
        if args.config_name not in configs: return print(f"错误: 找不到名为 '{args.config_name}' 的配置。")
        run_command(args.command, configs[args.config_name], args)
    except KeyboardInterrupt:
        print("\n操作已由用户中断。")
        sys.exit(0)
    except Exception as e:
        print(f"\n程序发生严重错误: {e}", file=sys.stderr)
        if isinstance(e, subprocess.CalledProcessError):
            print(f"命令输出:\n{e.stdout}\n命令错误:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
