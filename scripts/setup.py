#!/usr/bin/env python3
"""Setup script for local development."""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
from pathlib import Path


def run(cmd: str, **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {cmd}")
    return subprocess.run(cmd, shell=True, **kwargs)


def main() -> None:
    print("Think Box AI — Local Setup")
    print("=" * 40)

    # 1. Create directories
    print("\n1. Creating directories...")
    dirs = ["data/jobs", "data/findings", "data/raw", "data/fixtures", "data/logs", ".thinkbox"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"   {d}/")

    # 2. Create .env if missing
    print("\n2. Checking .env...")
    if not Path(".env").exists():
        api_key = f"tb_{secrets.token_urlsafe(32)}"
        env_content = f"""# Think Box AI — Local Development
THINKBOX_DEFAULT_PROVIDER=openai_compat
THINKBOX_DEFAULT_MODEL=gpt-4o-mini
THINKBOX_OPENAI_COMPAT_API_KEY=
THINKBOX_OPENAI_COMPAT_BASE_URL=https://api.openai.com/v1
THINKBOX_API_KEY={api_key}
THINKBOX_RATE_LIMIT=100
THINKBOX_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
THINKBOX_LOG_LEVEL=INFO
"""
        Path(".env").write_text(env_content)
        print(f"   Created .env with API key: {api_key}")
    else:
        print("   .env already exists")

    # 3. Install dependencies
    print("\n3. Installing dependencies...")
    run("pip install -e '.[dev]'")

    # 4. Initialize database
    print("\n4. Initializing database...")
    try:
        from core.indexing.database import init_db
        init_db()
        print("   Database initialized")
    except Exception as e:
        print(f"   Warning: {e}")

    # 5. Run doctor
    print("\n5. Running diagnostics...")
    run("python3 -m think_box_ai doctor")

    print("\n" + "=" * 40)
    print("Setup complete!")
    print("\nNext steps:")
    print("  1. Edit .env and add your API keys")
    print("  2. Run: python3 -m think_box_ai serve")
    print("  3. Or:  python3 -m uvicorn backend.main:app --reload")


if __name__ == "__main__":
    main()
