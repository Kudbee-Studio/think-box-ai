"""Config commands for Think Box CLI."""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


def show_config() -> None:
    """Show current configuration from environment."""
    provider = os.environ.get("THINKBOX_DEFAULT_PROVIDER", "ollama")
    model = os.environ.get("THINKBOX_DEFAULT_MODEL", "llama3.1:8b")
    box_id = os.environ.get("UPSTASH_BOX_ID", "wanted-tuna-71803")

    print("Current configuration:")
    print(f"  Provider: {provider}")
    print(f"  Model: {model}")
    print(f"  Box ID: {box_id}")
    print()
    print("Providers: ollama, openai_compat, freetoken")


def set_provider(name: str) -> None:
    """Set the default provider in .env."""
    valid = ["ollama", "openai_compat", "freetoken"]
    if name not in valid:
        print(f"Invalid provider. Choose from: {', '.join(valid)}")
        return

    lines = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text().splitlines()

    found = False
    for i, line in enumerate(lines):
        if line.startswith("THINKBOX_DEFAULT_PROVIDER="):
            lines[i] = f"THINKBOX_DEFAULT_PROVIDER={name}"
            found = True
            break
    if not found:
        lines.append(f"THINKBOX_DEFAULT_PROVIDER={name}")

    ENV_FILE.write_text("\n".join(lines) + "\n")
    print(f"Provider set to: {name}")
    print(f"Updated: {ENV_FILE}")
