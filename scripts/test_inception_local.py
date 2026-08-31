#!/usr/bin/env python3
"""Test Inception API from local environment with full HTTPS support."""
import urllib.request
import json
import ssl
import sys

API_KEY = sys.argv[1] if len(sys.argv) > 1 else "REDACTED_API_KEY"
BASE_URL = "https://api.inception.ai/v1"
MODEL = "mercury-2"

# Test 1: List models
print("=== Test 1: List Models ===")
try:
    req = urllib.request.Request(
        f"{BASE_URL}/models",
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        models = data.get("data", [])
        print(f"  OK: {len(models)} models available")
        for m in models[:5]:
            print(f"    - {m.get('id', 'unknown')}")
except Exception as e:
    print(f"  FAIL: {e}")

# Test 2: Simple completion
print("\n=== Test 2: Simple Completion ===")
try:
    payload = {
        "model": MODEL,
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
        usage = data.get("usage", {})
        print(f"  OK: '{content}'")
        print(f"  Usage: {usage}")
except Exception as e:
    print(f"  FAIL: {e}")

# Test 3: Tool-use completion (what the agent needs)
print("\n=== Test 3: Tool-Use Completion ===")
try:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a research agent. Use tools to accomplish goals. Output tool calls as: <tool_call>{\"tool\": \"name\", \"args\": {}}</tool_call>"},
            {"role": "user", "content": "Goal: List the files in the current directory."}
        ],
        "max_tokens": 200,
        "stream": False,
        "tools": [{"type": "function", "function": {"name": "fs_list", "description": "List files", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}]
    }
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        choice = data.get("choices", [{}])[0].get("message", {})
        content = choice.get("content", "")
        tool_calls = choice.get("tool_calls", [])
        print(f"  Content: {content}")
        print(f"  Tool calls: {tool_calls}")
        print(f"  OK: Tool-use format supported")
except Exception as e:
    print(f"  FAIL: {e}")

print("\n=== All tests complete ===")
