"""Configuration commands."""

from __future__ import annotations

import json
from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, yellow
from ..utils.output import is_json_mode, output_json

CONFIG_DIR = Path(".thinkbox")
CONFIG_FILE = CONFIG_DIR / "config.json"
PROFILES_DIR = CONFIG_DIR / "profiles"

DEFAULT_CONFIG = {
    "default_provider": "openai_compat",
    "default_model": "gpt-4o-mini",
    "max_think_box_depth": 2,
    "audit_log_retention_days": 90,
    "theme": "dark",
    "output_format": "auto",
}

PROFILES = {
    "local": {
        "default_provider": "ollama",
        "default_model": "llama3.1:8b",
    },
    "cloud": {
        "default_provider": "openai_compat",
        "default_model": "gpt-4o-mini",
    },
    "research": {
        "default_provider": "openai_compat",
        "default_model": "gpt-4o",
        "max_think_box_depth": 3,
    },
    "fast": {
        "default_provider": "openai_compat",
        "default_model": "gpt-4o-mini",
        "max_think_box_depth": 1,
    },
}


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return {**DEFAULT_CONFIG, **json.loads(CONFIG_FILE.read_text())}
        except (json.JSONDecodeError, OSError):
            pass
    return {**DEFAULT_CONFIG}


def _save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def handle_config_command(args) -> None:
    sub = args.config_command

    if sub == "show":
        _config_show(args)
    elif sub == "set":
        _config_set(args)
    elif sub == "profile":
        _config_profile(args)
    else:
        print("Usage: thinkbox config {show|set|profile}")


def _config_show(args) -> None:
    config = _load_config()

    if is_json_mode():
        output_json(config)
        return

    print(bold("\n  Configuration:"))
    print(dim("  " + "─" * 40))
    for key, value in config.items():
        print(f"  {bold(key):30} {cyan(str(value))}")

    print(f"\n  {bold('Available Profiles:')}")
    for name, profile in PROFILES.items():
        print(f"    {cyan(name):15} {dim(json.dumps(profile))}")


def _config_set(args) -> None:
    config = _load_config()
    key = args.key
    value = args.value

    if key not in config and key not in DEFAULT_CONFIG:
        print(yellow(f"  Unknown config key: {key}"))
        print(dim(f"  Valid keys: {', '.join(DEFAULT_CONFIG.keys())}"))
        return

    try:
        value = type(config.get(key, str))(value)
    except (ValueError, TypeError):
        pass

    config[key] = value
    _save_config(config)

    if is_json_mode():
        output_json({"status": "set", "key": key, "value": value})
        return

    print(green(f"  Set {key} = {value}"))


def _config_profile(args) -> None:
    name = args.name
    if name not in PROFILES:
        print(yellow(f"  Unknown profile: {name}"))
        print(dim(f"  Available: {', '.join(PROFILES.keys())}"))
        return

    config = {**_load_config(), **PROFILES[name]}
    _save_config(config)

    if is_json_mode():
        output_json({"profile": name, "config": config})
        return

    print(green(f"  Loaded profile: {name}"))
    for key, value in PROFILES[name].items():
        print(f"    {bold(key)} = {cyan(str(value))}")
