"""Test which models in the database are actually accessible."""
import asyncio
import json
import sys
import aiohttp

# === CONFIG ===
ACCOUNTS = [
    {
        "id": "0f72278e5e894a45a9b2c8c139580680",
        "name": "ms.cn(tk)",
        "key": "ms-ef15676c-7ad4-49b5-8b55-2c2ae7101b8c",
        "base": "https://api-inference.modelscope.cn/v1",
    },
    {
        "id": "e796c040eb5643149b45faf682992178",
        "name": "ms.cn(nico)",
        "key": "ms-115faeda-7f55-4c98-9520-21b37a0c18f3",
        "base": "https://api-inference.modelscope.cn/v1",
    },
    {
        "id": "90f8e8f226ff41a8a51f186a8d8410db",
        "name": "ms.ai(nico)",
        "key": "ms-ff949c01-ac4f-4854-b7ba-9c43b0c02c53",
        "base": "https://api-inference.modelscope.ai/v1",
    },
]

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
