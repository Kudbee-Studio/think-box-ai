"""Configuration management for THINK BOX AI.

Configuration hierarchy (highest precedence wins):
  1. Runtime overrides (CLI flags)
  2. Environment variables (THINKBOX_*)
  3. Project config (pyproject.toml [tool.thinkbox])
  4. System defaults (in code)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any


ENV_PREFIX = "THINKBOX_"


@dataclass
class ThinkBoxConfig:
    """Top-level configuration for the THINK BOX AI runtime."""

    default_provider: str = "openai_compat"
    default_model: str = "gpt-4o-mini"
    max_think_box_depth: int = 2
    max_iterations_per_think_box: int = 20
    max_tokens_per_completion: int = 4096
    memory_db_path: str = "./thinkbox_memory.db"
    audit_log_retention_days: int = 90
    default_approval_policy: str = "manual"
    log_level: str = "INFO"
    data_dir: str = "./thinkbox_data"
    provider_configs: dict[str, dict[str, Any]] = field(default_factory=dict)


def _load_pyproject_config(project_root: Path) -> dict[str, Any]:
    """Load [tool.thinkbox] section from pyproject.toml if it exists."""
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return {}

    config: dict[str, Any] = {}
    in_thinkbox_section = False

    try:
        with open(pyproject, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("[tool.thinkbox]"):
                    in_thinkbox_section = True
                    continue
                if in_thinkbox_section and stripped.startswith("["):
                    break
                if in_thinkbox_section and "=" in stripped and not stripped.startswith("#"):
                    key, _, value = stripped.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if value.isdigit():
                        value = int(value)
                    elif value in ("true", "false"):
                        value = value == "true"
                    config[key] = value
    except Exception:
        pass

    return config


def _load_env_overrides() -> dict[str, Any]:
    """Load THINKBOX_* environment variables."""
    overrides: dict[str, Any] = {}
    for key, value in os.environ.items():
        if key.startswith(ENV_PREFIX):
            config_key = key[len(ENV_PREFIX):].lower()
            if value.isdigit():
                value = int(value)
            elif value in ("true", "false"):
                value = value == "true"
            overrides[config_key] = value
    return overrides


def load_config(project_root: Path | None = None) -> ThinkBoxConfig:
    """Load configuration from all sources with proper precedence."""
    if project_root is None:
        project_root = Path.cwd()

    defaults = {f.name: f.default for f in fields(ThinkBoxConfig) if f.default is not field(default_factory=dict)}
    pyproject_config = _load_pyproject_config(project_root)
    env_overrides = _load_env_overrides()

    merged = {**defaults, **pyproject_config, **env_overrides}
    valid_fields = {f.name for f in fields(ThinkBoxConfig)}
    filtered = {k: v for k, v in merged.items() if k in valid_fields}

    return ThinkBoxConfig(**filtered)
