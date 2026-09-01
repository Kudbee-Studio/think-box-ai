"""Configuration management for Think Box AI.

Supports: environment variables, .env files, and vault integration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Config:
    """Application configuration."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Provider
    default_provider: str = "ollama"
    default_model: str = "llama3.1:8b"

    # Security
    api_key_required: bool = False
    rate_limit: int = 100
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    allowed_hosts: list[str] = field(default_factory=lambda: ["*"])

    # Database
    db_path: str = "data/thinkbox.db"
    memory_db_path: str = "data/thinkbox_memory.db"

    # Redis (optional)
    redis_url: str | None = None

    # Email (optional)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""

    # Storage
    data_dir: str = "data"
    jobs_dir: str = "jobs"
    max_upload_size: int = 10 * 1024 * 1024  # 10MB

    @classmethod
    def from_env(cls) -> "Config":
        """Load config from environment variables."""
        return cls(
            host=os.environ.get("THINKBOX_HOST", "0.0.0.0"),
            port=int(os.environ.get("THINKBOX_PORT", "8000")),
            debug=os.environ.get("THINKBOX_DEBUG", "").lower() == "true",
            default_provider=os.environ.get("THINKBOX_DEFAULT_PROVIDER", "ollama"),
            default_model=os.environ.get("THINKBOX_DEFAULT_MODEL", "llama3.1:8b"),
            api_key_required=os.environ.get("API_KEY_REQUIRED", "").lower() == "true",
            rate_limit=int(os.environ.get("RATE_LIMIT", "100")),
            cors_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
            allowed_hosts=os.environ.get("ALLOWED_HOSTS", "*").split(","),
            db_path=os.environ.get("DB_PATH", "data/thinkbox.db"),
            redis_url=os.environ.get("REDIS_URL"),
            smtp_host=os.environ.get("SMTP_HOST", ""),
            smtp_port=int(os.environ.get("SMTP_PORT", "587")),
            smtp_user=os.environ.get("SMTP_USER", ""),
            smtp_password=os.environ.get("SMTP_PASSWORD", ""),
            email_from=os.environ.get("EMAIL_FROM", ""),
        )

    @classmethod
    def from_file(cls, path: str = ".env") -> "Config":
        """Load config from .env file."""
        config = cls()
        env_path = Path(path)
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
        return cls.from_env()


# Global config
config = Config.from_env()
