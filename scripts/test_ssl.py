#!/usr/bin/env python3
"""Test various SSL/TLS approaches for box environment."""
import ssl
import urllib.request
import json

API_KEY = "sk_63c907f6e5c65a4fd03d1bafcd81e895"
HOST = "api.inception.ai"

# Approach 1: Custom context with SNI disabled
print("=== Approach 1: SSL with SNI callback ===")
try:
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED

    def sni_callback(sock, server_hostname, initial_context):
        print(f"  SNI callback: connecting to {server_hostname}")

    ctx.sni_callback = sni_callback

    req = urllib.request.Request(
        f"https://{HOST}/v1/chat/completions",
        data=json.dumps({"model": "mercury-2", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10}).encode(),
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        print(f"  OK: {resp.read().decode()[:200]}")
except Exception as e:
    print(f"  FAIL: {e}")

# Approach 2: Try with explicit SNI hostname
print("\n=== Approach 2: Direct socket with SNI ===")
import socket
try:
    sock = socket.create_connection((HOST, 443), timeout=10)
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    ssock = ctx.wrap_socket(sock, server_hostname=HOST)
    print(f"  Connected! Cipher: {ssock.cipher()}")
    ssock.close()
except Exception as e:
    print(f"  FAIL: {e}")

# Approach 3: Try without SNI (some servers accept this)
print("\n=== Approach 3: No SNI ===")
try:
    sock = socket.create_connection((HOST, 443), timeout=10)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ssock = ctx.wrap_socket(sock)  # No server_hostname = no SNI
    print(f"  Connected without SNI! Cipher: {ssock.cipher()}")
    ssock.close()
except Exception as e:
    print(f"  FAIL: {e}")

# Approach 4: Try HTTP/1.1 upgrade
print("\n=== Approach 4: HTTP upgrade ===")
try:
    import http.client
    conn = http.client.HTTPSConnection(HOST, timeout=10, context=ssl.create_default_context())
    conn.request("GET", "/v1/models", headers={"Authorization": f"Bearer {API_KEY}"})
    resp = conn.getresponse()
    print(f"  Status: {resp.status}")
    print(f"  Body: {resp.read().decode()[:200]}")
    conn.close()
except Exception as e:
    print(f"  FAIL: {e}")
