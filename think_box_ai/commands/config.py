"""Config commands for Think Box CLI."""

from __future__ import annotations

import os
from pathlib import Path

from ..ui.colors import bold
from ..ui.table import render_key_value

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


def show_config() -> None:
    """Show current configuration."""
    provider = os.environ.get("THINKBOX_DEFAULT_PROVIDER", "ollama")
    model = os.environ.get("THINKBOX_DEFAULT_MODEL", "llama3.1:8b")
    box_id = os.environ.get("UPSTASH_BOX_ID", "wanted-tuna-71803")

    print(bold("\nCurrent configuration:"))
    render_key_value({
        "provider": provider,
        "model": model,
        "box_id": box_id,
    })
    print()
    print("Providers: ollama, openai_compat, freetoken")


def set_config(key: str, value: str) -> None:
    """Set a config value in .env."""
    valid_keys = ["provider", "model"]
    env_map = {
        "provider": "THINKBOX_DEFAULT_PROVIDER",
        "model": "THINKBOX_DEFAULT_MODEL",
    }

    if key not in valid_keys:
        print(f"Invalid key. Choose from: {', '.join(valid_keys)}")
        return

    env_key = env_map[key]
    lines = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text().splitlines()

    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{env_key}="):
            lines[i] = f"{env_key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{env_key}={value}")

    ENV_FILE.write_text("\n".join(lines) + "\n")
    print(f"Set {key} = {value}")
    print(f"Updated: {ENV_FILE}")


def use_profile(profile: str) -> None:
    """Load a profile from .env.<profile>."""
    from pathlib import Path
    profile_file = Path(__file__).resolve().parent.parent.parent / f".env.{profile}"
    if not profile_file.exists():
        print(f"Profile not found: {profile}")
        print("Available: ollama, freetoken")
        return

    lines = profile_file.read_text().splitlines()
    if ENV_FILE.exists():
        existing = ENV_FILE.read_text().splitlines()
    else:
        existing = []

    for line in lines:
        if "=" in line and not line.startswith("#"):
            key = line.split("=")[0]
            # Remove existing entry
            existing = [l for l in existing if not l.startswith(f"{key}=")]
            existing.append(line)

    ENV_FILE.write_text("\n".join(existing) + "\n")
    print(f"Loaded profile: {profile}")
    print(f"Updated: {ENV_FILE}")
