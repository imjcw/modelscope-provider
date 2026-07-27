#!/usr/bin/env bash
# start.sh — 启动 ModelScope Proxy 服务
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

echo ">>> 启动 ModelScope Proxy..."
echo "    地址: http://${HOST}:${PORT}"
echo "    文档: http://${HOST}:${PORT}/docs"
echo ""

$PY -m uvicorn main:app --host "$HOST" --port "$PORT" --reload
