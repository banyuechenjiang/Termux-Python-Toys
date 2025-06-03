#!/bin/bash

# 颜色变量
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# 函数定义：显示公钥并复制到剪贴板
view_public_key() {
  cat ~/.ssh/id_ed25519.pub | termux-clipboard-set 2>/dev/null
  if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}公钥已复制到剪贴板。内容如下：${NC}"
    cat ~/.ssh/id_ed25519.pub
  else
    echo -e "${RED}无法复制公钥到剪贴板，请手动查看内容：${NC}"
    cat ~/.ssh/id_ed25519.pub
  fi
}

# 函数定义：生成新的 SSH 密钥
generate_ssh_key() {
  read -r -p "请输入你的邮箱地址: " email
  if [[ -z "$email" ]]; then
    echo -e "${RED}错误：邮箱地址不能为空。${NC}"
    exit 1
  fi

  ssh-keygen -t ed25519 -C "$email" -f ~/.ssh/id_ed25519 -q -N "" && \
  chmod 600 ~/.ssh/id_ed25519 && chmod 644 ~/.ssh/id_ed25519.pub && chmod 700 ~/.ssh

  if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}你的公钥已生成并复制到剪贴板。请将此密钥添加到你的 GitHub (或其他 Git 服务器) 账户:${NC}"
    view_public_key
  else
    echo -e "${RED}密钥生成失败，请检查文件权限或环境配置。${NC}"
    exit 1
  fi
}

# 函数定义：测试 SSH 连接
test_ssh_connection() {
  ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"
  if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}SSH 连接测试成功!${NC}"
  else
    echo -e "${RED}SSH 连接测试失败。请检查你的配置。${NC}"
  fi
}

# 主逻辑
if [[ -f ~/.ssh/id_ed25519 ]]; then
  echo -e "${GREEN}SSH 密钥已存在。${NC}"
  read -r -p "是否查看公钥? (y/n): " view_choice
  if [[ "${view_choice,,}" == "y" ]]; then
    view_public_key
  fi
else
  echo -e "${RED}SSH 密钥不存在。${NC}"
  read -r -p "是否生成新的 SSH 密钥? (y/n): " generate_choice
  if [[ "${generate_choice,,}" == "y" ]]; then
    generate_ssh_key

    read -r -p "是否测试 SSH 连接到 GitHub? (y/n): " test_choice
    if [[ "${test_choice,,}" == "y" ]]; then
      test_ssh_connection
    fi
  fi
fi
