import pkg_resources
import os

def get_directory_size(directory, package_name):
    total_size = 0
    for path, dirs, files in os.walk(directory):
        if package_name in path:
            for f in files:
                fp = os.path.join(path, f)
                total_size += os.path.getsize(fp)
    return total_size

# 使用pkg_resources获取已安装软件包列表
installed_packages = pkg_resources.working_set

# 查询软件包大小
for package in installed_packages:
    try:
        package_directory = package.location
        size_bytes = get_directory_size(package_directory, package.key)
        size_mb = size_bytes / (1024 * 1024)
        print(f"{package.key} {package.version}: {size_mb:.2f} MB")
    except:
        print(f"{package.key} {package.version}: Size not found")