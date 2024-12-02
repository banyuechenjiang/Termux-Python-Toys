import ast
import os
import argparse

# 缓存文件解析结果，避免重复解析
file_data_cache = {}

def extract_functions_classes_vars_and_main(code):
    """从 Python 代码中提取模块、全局变量、函数、类、主函数调用等。"""
    tree = ast.parse(code)

    imports = []  # 存储导入的模块
    global_vars = []  # 存储全局变量
    functions = []  # 存储函数
    classes = []  # 存储类
    main_calls = []  # 存储主函数调用

    class CodeVisitor(ast.NodeVisitor):
        def visit_Import(self, node):
            imports.append(f"import {' '.join(alias.name for alias in node.names)}")

        def visit_ImportFrom(self, node):
            imports.append(f"from {node.module} import {', '.join(alias.name for alias in node.names)}")

        def visit_Assign(self, node):
            if isinstance(node.targets[0], ast.Name):
                global_vars.append(node.targets[0].id)

        def visit_FunctionDef(self, node):
            if node.name == "__main__":
                main_calls.append(node.name)
            else:
                functions.append((node.name, node.lineno, node.col_offset, ast.unparse(node)))

        def visit_ClassDef(self, node):
            classes.append((node.name, node.lineno, node.col_offset, ast.unparse(node)))

    visitor = CodeVisitor()
    visitor.visit(tree)

    return imports, global_vars, functions, classes, main_calls

def print_file_info(filename, imports, global_vars, functions, classes):
    """打印文件的基本信息"""
    print(f"\n选定文件：{filename}\n")
    if imports:
        print("模块 :")
        for i, imp in enumerate(imports):
            print(f"  {i + 1}. {imp}")

    if global_vars:
        print("\n全局变量 :")
        for i, var in enumerate(global_vars):
            print(f"  {i + 1}. {var}")

    if classes or functions:
        print("\n函数和类:")
        for i, (name, _, _, _) in enumerate(classes + functions):
            print(f"  {i + 1}. {name} ({'类' if i < len(classes) else '函数'})")

def paginate_output(text, lines_per_page=20):
    """分页显示内容，每页显示指定行数"""
    lines = text.splitlines()
    for i in range(0, len(lines), lines_per_page):
        print("\n".join(lines[i:i + lines_per_page]))
        if i + lines_per_page < len(lines):
            input("\n--按 Enter 查看下一页--")

def main():
    parser = argparse.ArgumentParser(description="从 Python 文件中提取模块、变量、函数和类。")
    parser.add_argument("filename", nargs="?", help="Python 文件的路径。如果省略，可以从列表中选择。")
    args = parser.parse_args()

    while True:
        if not args.filename:
            # 列出当前目录下的 Python 文件
            python_files = [f for f in os.listdir(".") if f.endswith(".py")]
            if not python_files:
                print("当前目录中没有 Python 文件。")
                break

            print("可用的 Python 文件：")
            for i, f in enumerate(python_files):
                print(f"{i + 1}. {f}")
            print("0. 退出")

            try:
                choice = int(input("输入要分析的文件的编号（或输入 0 退出）："))
                if choice == 0:
                    break
                filename = python_files[choice - 1]
            except (ValueError, IndexError):
                print("无效选择，请输入正确编号。")
                continue
        else:
            filename = args.filename

        if filename in file_data_cache:
            # 从缓存中获取解析结果
            imports, global_vars, functions, classes, main_calls, code = file_data_cache[filename]
        else:
            # 读取文件并解析
            with open(filename, "r", encoding="utf-8") as f:
                code = f.read()

            # 解析代码结构
            imports, global_vars, functions, classes, main_calls = extract_functions_classes_vars_and_main(code)
            file_data_cache[filename] = (imports, global_vars, functions, classes, main_calls, code)  # 缓存结果

        print_file_info(filename, imports, global_vars, functions, classes)

        while True:
            choice = input(
                "\n输入要查看详情的编号或名称\n"
                "(输入 'a' 查看整个文件, 'm' 查看导入模块, 'g' 查看全局变量, "
                "'h' 查看主函数, '0' 返回文件列表, 'q' 退出): ").strip().lower()

            if choice == "a":
                print("\n文件内容:\n")
                print(code)  # 直接打印整个文件内容
            elif choice == "m":
                print("\n导入模块内容:")
                for i, imp in enumerate(imports):
                    print(f"{i + 1}. {imp}")
            elif choice == "g":
                print("\n全局变量内容:")
                if global_vars:
                    for i, var in enumerate(global_vars):
                        print(f"{i + 1}. {var}")
                else:
                    print("无全局变量")
            elif choice == "h":
                print("\n主函数调用:")
                if main_calls:
                    for i, call in enumerate(main_calls):
                        print(f"{i + 1}. {call}")
                else:
                    print("无主函数调用")
            elif choice == "0":  # 返回文件列表
                args.filename = None  # 清除文件名，以便重新选择
                break
            elif choice == "q":  # 退出程序
                return
            else:
                try:
                    idx = int(choice) - 1
                    item = (classes + functions)[idx]
                    print(f"\n{item[0]}:\n")
                    
                    # 分页显示超过80行的内容
                    if len(item[3].splitlines()) > 80:
                        paginate_output(item[3])
                    else:
                        print(item[3])
                except (ValueError, IndexError):
                    print("无效输入，请重新输入。")

if __name__ == "__main__":
    main()
