"""Test which models in the database are actually accessible.

⚠️ SECURITY: 此脚本以前在源码中硬编码了真实 ModelScope API Key。
这些 Key 已经泄露，应当被轮换（revoke/重新生成）。

现在账户信息一律从环境变量读取，源码中不再包含任何明文凭据：

    export MODELSCOPE_ACCOUNTS_JSON='[
      {"id": "acc1", "name": "ms.cn", "key": "YOUR_KEY_HERE",
       "base": "https://api-inference.modelscope.cn/v1"},
      {"id": "acc2", "name": "ms.ai", "key": "YOUR_KEY_HERE",
       "base": "https://api-inference.modelscope.ai/v1"}
    ]'

如果没有设置该变量，脚本会直接退出并提示如何配置，不会用假 Key 发起请求。
"""
import asyncio
import json
import os
import sys
import aiohttp

# === CONFIG ===
# 账户信息从环境变量读取，避免把真实凭据写进源码 / 版本库。
_raw_accounts = os.getenv("MODELSCOPE_ACCOUNTS_JSON")
if not _raw_accounts:
    print(
        "未设置 MODELSCOPE_ACCOUNTS_JSON 环境变量，无法运行模型可用性测试。\n"
        "请按以下格式提供账户信息（key 替换为你的真实 Key）：\n\n"
        'export MODELSCOPE_ACCOUNTS_JSON=\'[{"id":"acc1","name":"ms.cn",'
        '"key":"YOUR_KEY_HERE","base":"https://api-inference.modelscope.cn/v1"}]\'\n',
        file=sys.stderr,
    )
    sys.exit(1)

try:
    ACCOUNTS = json.loads(_raw_accounts)
except json.JSONDecodeError as exc:
    print(f"MODELSCOPE_ACCOUNTS_JSON 不是合法 JSON：{exc}", file=sys.stderr)
    sys.exit(1)

if not isinstance(ACCOUNTS, list) or not ACCOUNTS:
    print("MODELSCOPE_ACCOUNTS_JSON 必须是非空数组。", file=sys.stderr)
    sys.exit(1)

MODELS = [
    "Qwen/Qwen3.5-397B-A17B",
    "Tencent-Hunyuan/Hy3",
    "ZhipuAI/GLM-5.2",
    "deepseek-ai/DeepSeek-V3.2",
    "deepseek-ai/DeepSeek-V4-Pro",
    "moonshotai/Kimi-K2.7-Code",
    "zai-org/GLM-5.1",
    "zai-org/GLM-5.2",
]


async def test_model(session, account, model):
    """Test a single account+model combination (streaming)."""
    url = f"{account['base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {account['key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True,
    }

    try:
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            status = resp.status
            # Read first chunk to detect error
            text = ""
            async for line in resp.content:
                line = line.decode("utf-8", errors="replace")
                text += line
                if len(text) > 2000:
                    break

            # Parse
            body_preview = text[:500].replace("\n", " ").strip()
            return status, body_preview

    except asyncio.TimeoutError:
        return -1, "TIMEOUT"
    except Exception as e:
        return -2, str(e)[:200]


async def main():
    # Use shared connector for reuse
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        results = []
        tasks = []
        for acc in ACCOUNTS:
            for model in MODELS:
                tasks.append(test_model(session, acc, model))
        all_results = await asyncio.gather(*tasks)

        for (acc, model), (status, body) in zip(
            [(a, m) for a in ACCOUNTS for m in MODELS], all_results
        ):
            ok = status == 200
            err = "" if ok else f" [{status}] {body[:200]}"
            results.append((acc["name"], model, status, body[:200]))

        # === TABLE OUTPUT ===
        # Header
        print(f"\n{'MODEL':<38} ", end="")
        for acc in ACCOUNTS:
            print(f"{acc['name'][:10]:<12}", end="")
        print()
        print("-" * 38 + "-" * 12 * len(ACCOUNTS))

        for model in MODELS:
            print(f"{model:<38} ", end="")
            for acc in ACCOUNTS:
                for name, m, status, body in results:
                    if name == acc["name"] and m == model:
                        if status == 200:
                            # Check if choices is null (pseudo-success)
                            if "choices:null" in body or 'choices":null' in body:
                                print("⚠️ pseudo   ", end="")
                            else:
                                print("✅ OK      ", end="")
                        else:
                            print(f"❌ {status}   ", end="")
                        break
            print()

        print("\n\n=== DETAILED ERRORS ===")
        for name, model, status, body in results:
            if status != 200:
                print(f"\n{name} | {model} | HTTP {status}")
                print(f"  {body}")


if __name__ == "__main__":
    asyncio.run(main())
