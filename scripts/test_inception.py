#!/usr/bin/env python3
"""Test Inception API with SSL bypass."""
import urllib.request
import json
import ssl

# Disable SSL verification for box environment
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

API_KEY = "REDACTED_API_KEY"
BASE_URL = "https://api.inception.ai/v1"

models = ["mercury-2", "mercury-1", "mercury", "inception-mercury-2"]
for model in models:
    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Say hello in one word."}],
            "max_tokens": 50,
            "stream": False
        }
        req = urllib.request.Request(
            f"{BASE_URL}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"SUCCESS with model '{model}': {content}")
            break
    except Exception as e:
        print(f"FAILED model '{model}': {e}")
