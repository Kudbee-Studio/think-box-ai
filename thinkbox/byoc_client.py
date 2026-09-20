"""Mercury-2 OpenAI-compatible client with timeouts + fail-closed."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, AsyncGenerator

from thinkbox.byoc_config import ByocConfig

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_MODEL = "mercury-2"
DEFAULT_BASE_URL = "https://api.inceptionlabs.ai/v1"


@dataclass(frozen=True)
class MercuryCall:
    prompt: str
    model: str = DEFAULT_MODEL
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout: int = DEFAULT_TIMEOUT


class MercuryClient:
    """Async OpenAI-compatible client for Mercury-2.

    Fail-closed: raises on any HTTP or network error.
    Never returns a synthetic/fallback response.
    """

    def __init__(self, config: ByocConfig | None = None) -> None:
        self._config = config or ByocConfig.load()
        if not self._config.api_key:
            raise RuntimeError("INCEPTION_API_KEY or THINKBOX_OPENAI_COMPAT_API_KEY required")
        if not self._config.base_url:
            raise RuntimeError("THINKBOX_OPENAI_COMPAT_BASE_URL required")
        self._api_key = self._config.api_key
        self._base_url = self._config.base_url.rstrip("/")
        self._model = self._config.model
        self._timeout = DEFAULT_TIMEOUT

    @property
    def redacted_config(self) -> dict[str, Any]:
        return self._config.redacted()

    async def complete(self, prompt: str, **kwargs: Any) -> str:
        call = MercuryCall(prompt=prompt, **{k: v for k, v in kwargs.items() if k in ("model", "temperature", "max_tokens")})
        return await self._fetch(call)

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncGenerator[str, None]:
        call = MercuryCall(prompt=prompt, **{k: v for k, v in kwargs.items() if k in ("model", "temperature", "max_tokens")})
        async for chunk in self._fetch_stream(call):
            yield chunk

    async def _fetch(self, call: MercuryCall) -> str:
        import asyncio

        def _do() -> str:
            payload = {
                "model": call.model,
                "messages": [{"role": "user", "content": call.prompt}],
                "stream": False,
                "temperature": call.temperature,
                "max_tokens": call.max_tokens,
            }
            req = urllib.request.Request(
                f"{self._base_url}/chat/completions",
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=call.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as e:
                body = e.read().decode() if hasattr(e, "read") else ""
                raise RuntimeError(f"Mercury-2 HTTP {e.code}: {body}") from e
            except urllib.error.URLError as e:
                raise RuntimeError(f"Mercury-2 unreachable: {e.reason}") from e

        return await asyncio.to_thread(_do)

    async def _fetch_stream(self, call: MercuryCall) -> AsyncGenerator[str, None]:
        import asyncio

        def _gen() -> AsyncGenerator[str, None]:
            payload = {
                "model": call.model,
                "messages": [{"role": "user", "content": call.prompt}],
                "stream": True,
                "temperature": call.temperature,
                "max_tokens": call.max_tokens,
            }
            req = urllib.request.Request(
                f"{self._base_url}/chat/completions",
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=call.timeout) as resp:
                    for line in resp:
                        if line.startswith(b"data: "):
                            try:
                                chunk = json.loads(line[6:])
                                content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
            except urllib.error.HTTPError as e:
                body = e.read().decode() if hasattr(e, "read") else ""
                raise RuntimeError(f"Mercury-2 stream HTTP {e.code}: {body}") from e
            except urllib.error.URLError as e:
                raise RuntimeError(f"Mercury-2 stream unreachable: {e.reason}") from e

        async def _runner() -> AsyncGenerator[str, None]:
            queue: asyncio.Queue[str] = asyncio.Queue()
            stop = asyncio.Event()

            def _produce() -> None:
                for item in _gen():
                    if stop.is_set():
                        break
                    queue.put_nowait(item)
                queue.put_nowait("__DONE__")

            asyncio.get_event_loop().run_in_executor(None, _produce)
            while True:
                item = await queue.get()
                if item == "__DONE__":
                    break
                yield item

        async for item in _runner():
            yield item