#!/usr/bin/env python3
"""Fetch public pages from doggy.market. Save raw. No login."""
import asyncio
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw" / "doggy"

PAGES = [
    ("dogi", "https://doggy.market/token/dogi"),
    ("dbit", "https://doggy.market/token/dbit"),
    ("dogx", "https://doggy.market/token/dogx"),
]


def fetch(url: str) -> tuple:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ThinkBoxAI-Research/0.2"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            return resp.status, body, None
    except Exception as e:
        return None, None, str(e)


def save(name: str, body: bytes, ext: str = "html") -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(body).hexdigest()[:12]
    path = RAW_DIR / f"{name}_{h}.{ext}"
    path.write_bytes(body)
    return path


async def main():
    results = {}
    for name, url in PAGES:
        status, body, err = fetch(url)
        if status == 200 and body:
            path = save(name, body)
            print(f"OK {name}: {status} -> {path.name} ({len(body)} bytes)")
            results[name] = {"status": status, "path": str(path), "size": len(body)}
        else:
            print(f"FAIL {name}: {status} err={err}")
            results[name] = {"status": status, "error": str(err)[:100]}

    # Save manifest
    manifest_path = RAW_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2))
    print(f"\nManifest: {manifest_path}")
    return results


if __name__ == "__main__":
    asyncio.run(main())
