import httpx

BASE_URL = "http://localhost:8000/api"


def test_health_check():
    """Test health check endpoint."""
    response = httpx.get(f"{BASE_URL}/health")
    print(f"Health check: {response.json()}")


def test_chat_completion():
    """Test chat completion endpoint."""
    response = httpx.post(
        f"{BASE_URL}/v1/chat/completions",
        json={
            "model": "hy3",
            "messages": [
                {"role": "user", "content": "Hello, who are you?"}
            ],
            "max_tokens": 100
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"Chat completion: {result['choices'][0]['message']['content']}")
        print(f"Usage: {result['usage']}")
    else:
        print(f"Error: {response.json()}")


if __name__ == "__main__":
    test_health_check()
    print("\n---\n")
    test_chat_completion()
