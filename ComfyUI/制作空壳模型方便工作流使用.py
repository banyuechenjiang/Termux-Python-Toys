import os

def create_dummy_file(folder_path, filename):
    # 确保后缀名存在，如果没有手动加后缀，默认给个 .safetensors
    if "." not in filename:
        filename += ".safetensors"
        
    full_path = os.path.join(folder_path, filename)
    
    # 检查文件是否已存在，防止误覆盖你可能真的下载了的小文件
    if os.path.exists(full_path):
        print(f"⚠️ 文件已存在，跳过: {filename}")
        return

    # 创建 0 字节的空文件
    try:
        with open(full_path, 'w') as f:
            pass
        print(f"✅ 成功创建空壳模型: {filename} -> 位于 {folder_path}")
    except Exception as e:
        print(f"❌ 创建失败 {filename}: {e}")

def main():
    print("="*50)
    print("  ComfyUI 空壳模型生成器 (零字节占位文件)")
    print("="*50)
    
    # 定义基础目录
    base_dirs = {
        "1": ("大模型 (Checkpoints)", "models/checkpoints"),
        "2": ("LoRA", "models/loras"),
        "3": ("ControlNet", "models/controlnet"),
        "4": ("VAE", "models/vae")
    }

    while True:
        print("\n请选择要创建的模型类型:")
        for key, (name, _) in base_dirs.items():
            print(f"[{key}] {name}")
        print("[0] 退出")
        
        choice = input("请输入序号: ").strip()
        if choice == '0':
            break
        if choice not in base_dirs:
            print("输入有误，请重新输入。")
            continue
            
        type_name, rel_path = base_dirs[choice]
        
        # 确保目录存在
        os.makedirs(rel_path, exist_ok=True)
        
        print(f"\n当前选择: {type_name}")
        print("请输入模型名称 (例如: sdxl_base_1.0.safetensors 或 直接输入 sdxl_base_1.0)")
        print("提示: 支持一次性粘贴多个名称，用逗号或空格隔开")
        
        input_str = input("模型名称: ").strip()
        if not input_str:
            continue
            
        # 支持用逗号或空格分隔批量创建
        filenames = input_str.replace(',', ' ').split()
        
        for fname in filenames:
            create_dummy_file(rel_path, fname)

if __name__ == "__main__":
    main()