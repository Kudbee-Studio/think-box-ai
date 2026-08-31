#!/usr/bin/env python3
"""Test Inception API connectivity."""
import urllib.request
import json

API_KEY = "sk_63c907f6e5c65a4fd03d1bafcd81e895"
BASE_URL = "https://api.inception.ai/v1"

# Test 1: List models
try:
    req = urllib.request.Request(
        f"{BASE_URL}/models",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        print(f"Models endpoint: OK")
        if "data" in data:
            for m in data["data"][:5]:
                print(f"  - {m.get('id', 'unknown')}")
except Exception as e:
    print(f"Models endpoint failed: {e}")

# Test 2: Simple completion
try:
    payload = {
        "model": "mercury-2",
        "messages": [{"role": "user", "content": "Say hello in one word."}],
        "max_tokens": 50,
        "stream": False
    }
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"Completion: OK - '{content}'")
except Exception as e:
    print(f"Completion failed: {e}")
