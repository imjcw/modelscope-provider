#!/usr/bin/env bash
# start.sh — 启动 AI Provider 服务
# 用法: bash start.sh

set -e

cd "$(dirname "$0")"

# ---------- 激活虚拟环境 ----------
if [ -d ".venv" ]; then
    echo ">>> 激活虚拟环境 (.venv)..."
    # shellcheck disable=SC1090
    source .venv/bin/activate
fi

# ---------- 检测 Python ----------
if command -v python >/dev/null 2>&1; then
    PY=python
elif command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    echo ">>> 错误: 未找到 python 或 python3" >&2
    exit 1
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo ">>> 启动 AI Provider..."
echo "    地址: http://${HOST}:${PORT}"
echo "    文档: http://${HOST}:${PORT}/docs"
echo ""

# 通过 run.py 启动，保证 DATABASE_URL / LOG_DIR 等可移植路径与 start.bat 一致
# 启动前清空 .pyc 缓存，避免 WSL 等环境加载旧字节码导致行为不一致
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"
$PY run.py
