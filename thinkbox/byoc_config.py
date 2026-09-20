"""BYOC config loader for Mercury-2 + Upstash — no secret logging."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ByocConfig:
    """Loaded from environment. Secrets are NEVER logged or repr'd."""

    api_key: str = ""
    base_url: str = "https://api.inceptionlabs.ai/v1"
    model: str = "mercury-2"
    vector_url: str = ""
    vector_token: str = ""
    demo_mode: str = "mock"

    @classmethod
    def load(cls, **overrides: str) -> "ByocConfig":
        api_key = overrides.get("api_key") or os.environ.get("INCEPTION_API_KEY") or os.environ.get("THINKBOX_OPENAI_COMPAT_API_KEY", "")
        base_url = overrides.get("base_url") or os.environ.get("THINKBOX_OPENAI_COMPAT_BASE_URL", "https://api.inceptionlabs.ai/v1")
        model = overrides.get("model") or os.environ.get("THINKBOX_DEFAULT_MODEL", "mercury-2")
        vector_url = overrides.get("vector_url") or os.environ.get("UPSTASH_VECTOR_REST_URL", "")
        vector_token = overrides.get("vector_token") or os.environ.get("UPSTASH_VECTOR_REST_TOKEN", "")
        demo_mode = overrides.get("demo_mode") or os.environ.get("DEMO_MODE", "mock")
        return cls(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            model=model,
            vector_url=vector_url,
            vector_token=vector_token,
            demo_mode=demo_mode,
        )

    @property
    def is_live(self) -> bool:
        return self.demo_mode == "byoc" and bool(self.api_key and self.vector_url and self.vector_token)

    @property
    def is_mock(self) -> bool:
        return self.demo_mode == "mock"

    def redacted(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "model": self.model,
            "demo_mode": self.demo_mode,
            "is_live": self.is_live,
            "has_api_key": bool(self.api_key),
            "has_vector_creds": bool(self.vector_url and self.vector_token),
            "vector_url": self.vector_url or None,
        }
