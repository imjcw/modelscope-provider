"""Regression tests: per-key (api_key_id) stats aggregation.

之前 query_stats_model_aggregate_by_key_batch 的关键 bug 是：
1. `if key_id:` 把主 key（key_id=0）当 falsy 跳过 → 非 None 判断
2. 按 days>0 才覆盖 token 用量 → 改为 key_id is not None 时覆盖

查询本身使用 actual_model_id（解析后的上游模型名，与目录模型名一致）分组
是正确的，因为 request_logs.model 可能是客户端传来的别名，不匹配目录名。
"""

import uuid
from datetime import datetime, timezone as _tz

import pytest

from provider.repositories.log_repository import LogRepository
from core.timezone import today_range


@pytest.fixture(autouse=True)
def _clean(database):
    with database.get_connection() as conn:
        conn.execute("DELETE FROM request_logs")
    yield


def _now_utc():
    return datetime.now(_tz.utc).strftime("%Y-%m-%d %H:%M:%S.") + "000"


def _log(repo, model, api_key_id, in_tok, out_tok, account_id="a1"):
    """Insert with catalog=actual_model_id (no alias, common case)."""
    repo.create(
        str(uuid.uuid4()), model, model, account_id, "A", 200,
        input_tokens=in_tok, output_tokens=out_tok,
        api_key_id=api_key_id, timestamp=_now_utc(),
    )


def test_by_key_aggregate_scoped_to_key_and_model(database):
    """不同 key 的同模型应返回各自独立的用量。"""
    repo = LogRepository(database)
    # key 1: m1=10/20, m2=1/2
    _log(repo, "m1", 1, 10, 20)
    _log(repo, "m2", 1, 1, 2)
    # key 2: m1=100/200（与 key 1 明显不同）
    _log(repo, "m1", 2, 100, 200)

    start, end = today_range()

    res1 = repo.query_stats_model_aggregate_by_key_batch("a1", ["m1", "m2"], key_id=1, start=start, end=end)
    res2 = repo.query_stats_model_aggregate_by_key_batch("a1", ["m1", "m2"], key_id=2, start=start, end=end)

    # key 1
    assert res1["m1"] == (10, 20, 0, 1, 1)
    assert res1["m2"] == (1, 2, 0, 1, 1)
    # key 2 只有 m1，且用量与 key 1 不同 → 证明按 key 区分
    assert res2["m1"] == (100, 200, 0, 1, 1)
    assert res2["m2"] == (0, 0, 0, 0, 0)


def test_by_key_aggregate_uses_actual_model_id(database):
    """查询用 actual_model_id 过滤和分组（而非 client 端 model 别名）。"""
    repo = LogRepository(database)
    # 客户端传别名 "gpt-4"，实际解析为 "gpt-4-0613"
    repo.create(
        str(uuid.uuid4()),
        model="gpt-4",           # 客户端传的别名
        actual_model_id="gpt-4-0613",  # 解析后的目录模型名
        account_id="a1", account_name="A", status_code=200,
        input_tokens=7, output_tokens=8,
        api_key_id=3, timestamp=_now_utc(),
    )

    start, end = today_range()
    # get_model_quotas 传入的是目录模型名 ["gpt-4-0613"]
    res = repo.query_stats_model_aggregate_by_key_batch(
        "a1", ["gpt-4-0613"], key_id=3, start=start, end=end,
    )

    # 若按 client 端 model 列（"gpt-4"）分组，则键是 "gpt-4"，
    # 按目录名 "gpt-4-0613" 查不到 → 返回全 0。
    # 正确实现按 actual_model_id 分组，键是 "gpt-4-0613" → 命中。
    assert res["gpt-4-0613"] == (7, 8, 0, 1, 1)
