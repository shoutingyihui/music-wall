#!/usr/bin/env bash
# 一次性环境准备：SSH key（走 443 端口，因为本机连不上 github.com:443）+ 仓库初始化提交
set -e
cd ~/music-wall

# --- SSH ---
if [ ! -f ~/.ssh/id_ed25519 ]; then
  ssh-keygen -t ed25519 -C "shoutingyihui@gmail.com" -f ~/.ssh/id_ed25519 -N "" -q
  echo "已生成新密钥"
else
  echo "密钥已存在，复用"
fi
mkdir -p ~/.ssh && chmod 700 ~/.ssh
if ! grep -q "Host github.com" ~/.ssh/config 2>/dev/null; then
  cat >> ~/.ssh/config <<'CFG'
Host github.com
  HostName ssh.github.com
  Port 443
  User git
  IdentityFile ~/.ssh/id_ed25519
  StrictHostKeyChecking accept-new
CFG
  chmod 600 ~/.ssh/config
  echo "已写 ~/.ssh/config（github.com → ssh.github.com:443）"
else
  echo "~/.ssh/config 已有 github.com 配置"
fi

echo "===== 公钥（整行复制）====="
cat ~/.ssh/id_ed25519.pub
echo "==========================="

# --- git ---
if [ ! -d .git ]; then
  git init -q -b main
  git add -A
  git commit -q -m "音乐墙：首版（3 单曲 + 3 专辑）

单文件自包含页面，封面 base64 内嵌，无外部依赖。
index.html 跟随封面深浅，index-light.html 一律浅色。
" && echo "已提交首版"
else
  echo "git 仓库已存在"
fi
echo "--- 本地状态 ---"
git log --oneline 2>/dev/null | head -3
git ls-files | head -30
echo "文件数: $(git ls-files | wc -l) | 体积: $(du -sh --exclude=.git . | cut -f1)"
