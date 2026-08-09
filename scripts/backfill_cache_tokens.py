"""回填历史请求日志的缓存命中 token 数据。

从 request_logs.raw_response 中重新解析 usage，提取
cached_tokens / prompt_partial_cached 并更新数据库。

用法:
    python scripts/backfill_cache_tokens.py [db_path] [--dry-run]

    db_path   数据库文件路径，默认 modelscope_proxy_prod.db
    --dry-run 只打印将要更新的记录，不写库
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

# 允许直接以脚本方式运行时导入 api.routes
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.openai_routes import _extract_cache_usage  # noqa: E402

USAGE_RE = re.compile(r'"usage"\s*:\s*')


def extract_cache_from_raw(raw_response: str, is_stream: bool):
    """从原始响应文本中提取 (cached_tokens, prompt_partial_cached)。

    流式: 遍历所有 SSE data 块, 取最后一个非空 usage。
    非流式: 直接解析 JSON。
    """
    if not raw_response:
        return 0, 0

    decoder = json.JSONDecoder()

    if not is_stream:
        try:
            obj = json.loads(raw_response)
            return _extract_cache_usage(obj.get("usage"))
        except (json.JSONDecodeError, AttributeError):
            return 0, 0

    cached, partial = 0, 0
    for line in raw_response.split("data:"):
        line = line.strip()
        if not line or line == "[DONE]":
            continue
        try:
            obj, _ = decoder.raw_decode(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict):
            continue
        usage = obj.get("usage")
        if not usage:
            continue
        c, p = _extract_cache_usage(usage)
        cached = c or cached
        partial = p or partial
    return cached, partial


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = "--dry-run" in sys.argv
    db_path = args[0] if args else "modelscope_proxy_prod.db"

    if not Path(db_path).exists():
        print(f"数据库不存在: {db_path}")
        sys.exit(1)

    con = sqlite3.connect(db_path)
    rows = con.execute(
        "SELECT id, is_stream, raw_response FROM request_logs "
        "WHERE (cached_tokens IS NULL OR cached_tokens = 0) "
        "AND raw_response IS NOT NULL AND raw_response != ''"
    ).fetchall()

    updated = 0
    for log_id, is_stream, raw in rows:
        cached, partial = extract_cache_from_raw(raw, bool(is_stream))
        if cached or partial:
            print(f"log #{log_id}: cached_tokens={cached}, "
                  f"prompt_partial_cached={partial}")
            if not dry_run:
                con.execute(
                    "UPDATE request_logs SET cached_tokens=?, "
                    "prompt_partial_cached=? WHERE id=?",
                    (cached, partial, log_id),
                )
            updated += 1

    if not dry_run:
        con.commit()
    con.close()
    print(f"共扫描 {len(rows)} 条, {'将' if dry_run else '已'}更新 {updated} 条"
          f"{' (dry-run 未写库)' if dry_run else ''}")


if __name__ == "__main__":
    main()
