"""LongCat 2.0 provider for Think Box AI.

LongCat 2.0 is Meituan's flagship AI model:
- 1.6 trillion parameters (MoE, ~48B active per token)
- 1M token context window
- 128K max output tokens
- OpenAI-compatible API format
- Optimized for agentic coding, long-context tasks, tool use
"""

from __future__ import annotations

from typing import Any

from core.providers.base import CompletionResponse, Message, ModelProvider, ProviderCapabilities, ProviderRegistry

LONGCAT_BASE_URL = "https://api.longcat.chat/openai"
LONGCAT_MODEL = "LongCat-2.0"


@ProviderRegistry.register("longcat")
class LongCatProvider:
    """LongCat 2.0 provider - Meituan's flagship MoE model."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._api_key = config.get("api_key", "")
        self._model = config.get("model", LONGCAT_MODEL)
        self._base_url = config.get("base_url", LONGCAT_BASE_URL)
        self._capabilities = ProviderCapabilities(
            completion=True,
            streaming=True,
            embedding=False,
            supports_system_prompt=True,
        )

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse:
        """Get completion from LongCat 2.0."""
        import json
        import urllib.request
        import urllib.error

        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
        }
        # Pass through standard params
        for param in ["temperature", "max_tokens", "top_p", "stop", "tools", "tool_choice"]:
            if param in kwargs:
                payload[param] = kwargs[param]
        # LongCat-specific: enable thinking mode
        if kwargs.get("thinking", True):
            payload["thinking"] = {"type": "enabled"}

        req = urllib.request.Request(
            f"{self._base_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )

        def _fetch() -> CompletionResponse:
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    choice = data["choices"][0]["message"]
                    usage = data.get("usage", {})
                    return CompletionResponse(
                        content=choice.get("content", ""),
                        model=data.get("model", self._model),
                        usage={
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "reasoning_tokens": usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0),
                        },
                        metadata={
                            "reasoning_content": choice.get("reasoning_content"),
                            "finish_reason": data["choices"][0].get("finish_reason"),
                        },
                    )
            except urllib.error.HTTPError as e:
                error_body = e.read().decode() if e.fp else ""
                if e.code == 429:
                    from core.foundation.errors import ProviderRateLimitError
                    raise ProviderRateLimitError() from e
                elif e.code == 401:
                    from core.foundation.errors import ProviderAuthError
                    raise ProviderAuthError() from e
                elif e.code == 402:
                    from core.foundation.errors import ProviderPaymentRequiredError
                    raise ProviderPaymentRequiredError() from e
                else:
                    from core.foundation.errors import ProviderError
                    raise ProviderError() from e

        return await __import__("asyncio").to_thread(_fetch)

    async def stream(self, messages: list[Message], **kwargs: Any):
        """Stream completion tokens from LongCat 2.0."""
        import json
        import urllib.request
        import urllib.error

        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        for param in ["temperature", "max_tokens", "top_p"]:
            if param in kwargs:
                payload[param] = kwargs[param]
        if kwargs.get("thinking", True):
            payload["thinking"] = {"type": "enabled"}

        req = urllib.request.Request(
            f"{self._base_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )

        def _stream():
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    for line in resp:
                        line = line.decode("utf-8").strip()
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            return
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                yield token
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    from core.foundation.errors import ProviderRateLimitError
                    raise ProviderRateLimitError() from e
                raise

        for token in _stream():
            yield token

    def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        raise NotImplementedError("Embedding not supported by LongCatProvider")
