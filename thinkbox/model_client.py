"""Async model client for ThinkBox AI.

Supports Ollama native and OpenAI-compatible endpoints (OpenAI, Groq,
Inception Mercury-2, vLLM). Failures raise ``ModelCallError``; a failed call
is never returned as if it were model output.

Uses httpx with connection pooling and exponential backoff for resilience.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

INCEPTION_BASE_URL = "https://api.inceptionlabs.ai/v1"
INCEPTION_DEFAULT_MODEL = "mercury-2"
# Mercury-2 is a reasoning model: below ~3500 tokens the reasoning consumes the
# budget and ``content`` comes back null.
INCEPTION_MIN_MAX_TOKENS = 3500

PROVIDER_OLLAMA = "ollama"
PROVIDER_OPENAI_COMPAT = "openai_compat"
PROVIDER_INCEPTION = "inception"
SUPPORTED_PROVIDERS = (PROVIDER_OLLAMA, PROVIDER_OPENAI_COMPAT, PROVIDER_INCEPTION)


class ModelCallError(RuntimeError):
    """A model call did not produce usable output."""

    def __init__(self, message: str, *, provider: str, model: str, retryable: bool) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.retryable = retryable


@dataclass
class ModelConfig:
    base_url: str = "http://localhost:11434"
    model: str = "llama3.1:8b"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 120
    api_type: str = PROVIDER_OLLAMA
    api_key: str = field(default="", repr=False)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None, **overrides: Any) -> "ModelConfig":
        """Build a config from ``THINKBOX_*`` / ``INCEPTION_API_KEY`` env vars.

        ``THINKBOX_DEFAULT_PROVIDER`` selects ``ollama`` (default),
        ``openai_compat`` or ``inception``. Explicit non-None overrides win.
        """
        env = dict(os.environ) if env is None else env
        provider = (overrides.pop("api_type", None) or env.get("THINKBOX_DEFAULT_PROVIDER") or PROVIDER_OLLAMA).strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"unsupported provider {provider!r}; expected one of {SUPPORTED_PROVIDERS}")
        model_env = env.get("THINKBOX_DEFAULT_MODEL", "").strip()

        if provider == PROVIDER_INCEPTION:
            cfg = cls(
                base_url=env.get("INCEPTION_BASE_URL", "").strip() or INCEPTION_BASE_URL,
                model=model_env or INCEPTION_DEFAULT_MODEL,
                max_tokens=INCEPTION_MIN_MAX_TOKENS,
                api_type=PROVIDER_OPENAI_COMPAT,
                api_key=env.get("INCEPTION_API_KEY", "").strip(),
            )
        elif provider == PROVIDER_OPENAI_COMPAT:
            cfg = cls(
                base_url=env.get("THINKBOX_OPENAI_COMPAT_BASE_URL", "").strip() or "https://api.openai.com/v1",
                model=model_env or "gpt-4o-mini",
                api_type=PROVIDER_OPENAI_COMPAT,
                api_key=env.get("THINKBOX_OPENAI_COMPAT_API_KEY", "").strip(),
            )
        else:
            cfg = cls(
                base_url=(env.get("THINKBOX_OLLAMA_BASE_URL") or env.get("OLLAMA_HOST") or "http://localhost:11434").strip(),
                model=model_env or "llama3.1:8b",
                api_type=PROVIDER_OLLAMA,
            )
        if not cfg.base_url.startswith(("http://", "https://")):
            cfg.base_url = f"http://{cfg.base_url}"
        for key, value in overrides.items():
            if value is not None:
                setattr(cfg, key, value)
        return cfg

    @property
    def provider_label(self) -> str:
        return self.api_type

    def chat_completions_url(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"


class AsyncModelClient:
    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()
        # Connection pool: max 500 connections, 20 keepalive
        self._client: httpx.AsyncClient | None = None
        self._use_pool = os.environ.get("ASYNC_PROVIDER_POOL", "true").lower() != "false"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async client with pooling."""
        if self._client is None and self._use_pool:
            limits = httpx.Limits(max_connections=500, max_keepalive_connections=20)
            self._client = httpx.AsyncClient(limits=limits, timeout=self.config.timeout)
        return self._client or httpx.AsyncClient(timeout=self.config.timeout)

    async def close(self) -> None:
        """Close the client connection pool."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Return the model's text. Raises ``ModelCallError`` on any failure."""
        if self.config.api_type == PROVIDER_OLLAMA:
            return await self._ollama_generate(prompt, **kwargs)
        return await self._openai_generate(prompt, **kwargs)

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncGenerator[str, None]:
        if self.config.api_type == PROVIDER_OLLAMA:
            async for token in self._ollama_stream(prompt, **kwargs):
                yield token
        else:
            async for token in self._openai_stream(prompt, **kwargs):
                yield token

    def _error(self, message: str, retryable: bool) -> ModelCallError:
        return ModelCallError(
            f"{self.config.api_type}:{self.config.model} {message}",
            provider=self.config.api_type,
            model=self.config.model,
            retryable=retryable,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    async def _post_json_with_backoff(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST JSON with exponential backoff on transient errors."""
        backoff = 2.0  # Start at 2s
        max_backoff = 32.0
        max_attempts = 5
        attempt = 0

        while attempt < max_attempts:
            try:
                client = await self._get_client()
                resp = await client.post(url, json=payload, headers=self._headers())
                resp.raise_for_status()
                try:
                    return resp.json()
                except json.JSONDecodeError as e:
                    raise self._error(f"non-JSON response: {resp.text[:200]!r}", retryable=True) from e
            except httpx.HTTPStatusError as e:
                is_transient = e.response.status_code in (408, 429) or e.response.status_code >= 500
                body = e.response.text[:300]
                error_msg = f"HTTP {e.response.status_code}: {body}"

                if is_transient and attempt < max_attempts - 1:
                    # Apply jitter: ±20%
                    jitter = backoff * 0.2 * (2 * random.random() - 1)
                    sleep_time = max(0.1, backoff + jitter)
                    logger.warning(
                        f"[{self.config.api_type}] transient error {e.response.status_code}; "
                        f"backoff {sleep_time:.1f}s (attempt {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(sleep_time)
                    backoff = min(backoff * 2, max_backoff)
                    attempt += 1
                    continue

                raise self._error(error_msg, retryable=is_transient) from e
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                if attempt < max_attempts - 1:
                    jitter = backoff * 0.2 * (2 * random.random() - 1)
                    sleep_time = max(0.1, backoff + jitter)
                    logger.warning(
                        f"[{self.config.api_type}] network error ({type(e).__name__}); "
                        f"backoff {sleep_time:.1f}s (attempt {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(sleep_time)
                    backoff = min(backoff * 2, max_backoff)
                    attempt += 1
                    continue

                raise self._error(f"unreachable at {url}: {e}", retryable=True) from e

        raise self._error(f"max retries exceeded for {url}", retryable=True)

    def _ollama_payload(self, prompt: str, stream: bool, **kwargs: Any) -> dict[str, Any]:
        return {
            "model": self.config.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            },
        }

    def _openai_payload(self, prompt: str, stream: bool, **kwargs: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }
        if stream:
            payload["stream"] = True
        return payload

    async def _ollama_generate(self, prompt: str, **kwargs: Any) -> str:
        url = f"{self.config.base_url.rstrip('/')}/api/generate"
        result = await self._post_json_with_backoff(url, self._ollama_payload(prompt, False, **kwargs))
        if result.get("error"):
            raise self._error(f"error: {result['error']}", retryable=False)
        text = result.get("response") or ""
        if not text.strip():
            raise self._error("returned an empty response", retryable=True)
        return text

    async def _openai_generate(self, prompt: str, **kwargs: Any) -> str:
        url = self.config.chat_completions_url()
        result = await self._post_json_with_backoff(url, self._openai_payload(prompt, False, **kwargs))
        choices = result.get("choices") or []
        message = (choices[0] or {}).get("message", {}) if choices else {}
        text = message.get("content") or ""
        if not text.strip():
            reason = (choices[0] or {}).get("finish_reason") if choices else "no choices"
            raise self._error(f"returned empty content (finish_reason={reason})", retryable=True)
        return text

    async def _iter_lines(self, url: str, payload: dict[str, Any]) -> AsyncGenerator[bytes, None]:
        """Stream lines from provider with httpx."""
        client = await self._get_client()
        try:
            async with client.stream("POST", url, json=payload, headers=self._headers()) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line:
                        yield line.encode() if isinstance(line, str) else line
        except httpx.HTTPStatusError as e:
            is_transient = e.response.status_code in (408, 429) or e.response.status_code >= 500
            body = e.response.text[:300]
            raise self._error(f"HTTP {e.response.status_code}: {body}", retryable=is_transient) from e
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
            raise self._error(f"stream error: {e}", retryable=True) from e

    async def _ollama_stream(self, prompt: str, **kwargs: Any) -> AsyncGenerator[str, None]:
        url = f"{self.config.base_url.rstrip('/')}/api/generate"
        async for line in self._iter_lines(url, self._ollama_payload(prompt, True, **kwargs)):
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            if chunk.get("error"):
                raise self._error(f"stream error: {chunk['error']}", retryable=False)
            if chunk.get("response"):
                yield chunk["response"]

    async def _openai_stream(self, prompt: str, **kwargs: Any) -> AsyncGenerator[str, None]:
        url = self.config.chat_completions_url()
        async for line in self._iter_lines(url, self._openai_payload(prompt, True, **kwargs)):
            if not line.startswith(b"data: ") or line.strip() == b"data: [DONE]":
                continue
            try:
                chunk = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            content = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content", "")
            if content:
                yield content
