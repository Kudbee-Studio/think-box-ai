"""Session Tracking Engine for ThinkBox AI.

Manages session lifecycle, context propagation, and Upstash Vector metadata sync.
"""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

SESSION_CONTEXT_VAR: contextvars.ContextVar["SessionContext | None"] = contextvars.ContextVar(
    "thinkbox_session_context", default=None
)


@dataclass
class SessionContext:
    session_id: str
    environment: str
    model_backend: str
    actor: str
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "environment": self.environment,
            "model_backend": self.model_backend,
            "actor": self.actor,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


def generate_session_id() -> str:
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d%H%M%S")
    hex_part = secrets.token_hex(4)
    return f"tb_sess_{timestamp}_{hex_part}"


def get_environment() -> str:
    box_url = os.environ.get("UPSTASH_PUBLIC_BOX_URL", "")
    if box_url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(box_url)
            return parsed.hostname or "unknown-box"
        except Exception:
            return "upstash-box"
    return "local"


def get_model_backend() -> str:
    model = os.environ.get("THINKBOX_DEFAULT_MODEL", "ollama")
    if "vllm" in model.lower():
        return "vLLM"
    elif "ollama" in model.lower() or model.startswith("llama") or model.startswith("deepseek"):
        return "Ollama"
    return "OpenAI-compat"


def get_actor() -> str:
    return os.environ.get("THINKBOX_ACTOR", os.environ.get("USER", "system"))


def create_session(
    environment: str | None = None,
    model_backend: str | None = None,
    actor: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SessionContext:
    session = SessionContext(
        session_id=generate_session_id(),
        environment=environment or get_environment(),
        model_backend=model_backend or get_model_backend(),
        actor=actor or get_actor(),
        created_at=datetime.now(timezone.utc).isoformat(),
        metadata=metadata or {},
    )
    SESSION_CONTEXT_VAR.set(session)
    return session


def get_current_session() -> SessionContext | None:
    return SESSION_CONTEXT_VAR.get()


def set_session(session: SessionContext) -> None:
    SESSION_CONTEXT_VAR.set(session)


def clear_session() -> None:
    SESSION_CONTEXT_VAR.set(None)


class UpstashVectorSync:
    def __init__(self) -> None:
        self._url = os.environ.get("UPSTASH_VECTOR_REST_URL", "")
        self._token = os.environ.get("UPSTASH_VECTOR_REST_TOKEN", "")
        self._enabled = bool(self._url and self._token)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def url(self) -> str:
        return self._url

    async def upsert(self, session: SessionContext, status: str = "RUNNING") -> bool:
        if not self._enabled:
            return False

        payload = {
            "id": session.session_id,
            "metadata": {
                "session_id": session.session_id,
                "box_url": os.environ.get("UPSTASH_PUBLIC_BOX_URL", ""),
                "environment": session.environment,
                "model_backend": session.model_backend,
                "actor": session.actor,
                "execution_status": status,
                "created_at": session.created_at,
                **session.metadata,
            },
        }

        try:
            import urllib.request
            import urllib.error

            url = f"{self._url}/upsert"
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10))
            return True
        except Exception:
            return False

    async def query(self, session_id: str) -> dict[str, Any] | None:
        if not self._enabled:
            return None

        try:
            import urllib.request

            url = f"{self._url}/get/{session_id}"
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {self._token}"},
            )
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10))
            return json.loads(response.read())
        except Exception:
            return None


import json


_session_sync: UpstashVectorSync | None = None


def get_session_sync() -> UpstashVectorSync:
    global _session_sync
    if _session_sync is None:
        _session_sync = UpstashVectorSync()
    return _session_sync


async def sync_session(session: SessionContext, status: str = "RUNNING") -> bool:
    sync = get_session_sync()
    return await sync.upsert(session, status)
