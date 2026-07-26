#!/usr/bin/env bash
# start.sh — 启动 ModelScope Proxy 服务
# 用法: bash start.sh

set -e

cd "$(dirname "$0")"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo ">>> 启动 ModelScope Proxy..."
echo "    地址: http://${HOST}:${PORT}"
echo "    文档: http://${HOST}:${PORT}/docs"
echo ""

python -m uvicorn main:app --host "$HOST" --port "$PORT" --reload
