"""Inception API provider for Think Box AI.

Mercury 2 model via Inception Labs.
NOTE: Only use locally — TLS fails from AWS/Upstash boxes.
"""

from __future__ import annotations

import json
import os
from typing import Any

from core.providers import CompletionResponse, Message, ProviderCapabilities, ProviderRegistry


@ProviderRegistry.register("inception")
class InceptionProvider:
    """Inception Labs Mercury 2 provider.
    
    Config:
        api_key: Inception API key (env: INCEPTION_API_KEY)
        model: mercury-2 (default)
        base_url: https://api.inception.ai/v1
    """

    def __init__(self, config: dict[str, Any]):
        self.api_key = config.get("api_key", os.environ.get("INCEPTION_API_KEY", ""))
        self.model = config.get("model", "mercury-2")
        self.base_url = config.get("base_url", "https://api.inception.ai/v1")
        self.capabilities = ProviderCapabilities(
            completion=True,
            streaming=config.get("streaming", False),
            embedding=False,
            supports_system_prompt=True,
        )

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse:
        import asyncio

        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        def _fetch():
            import urllib.request
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
                choice = data["choices"][0]["message"]
                usage = data.get("usage", {})
                # Track cost
                self._track_usage(usage)
                return CompletionResponse(
                    content=choice.get("content", ""),
                    model=data.get("model", self.model),
                    usage=usage,
                )

        return await asyncio.to_thread(_fetch)

    def _track_usage(self, usage: dict):
        """Track token usage for cost estimation."""
        total_tokens = usage.get("total_tokens", 0)
        # Mercury 2 pricing: ~$0.00001 per token (example)
        cost = total_tokens * 0.00001
        # Store in local tracking file
        import json
        from pathlib import Path
        track_file = Path("data/usage.jsonl")
        track_file.parent.mkdir(parents=True, exist_ok=True)
        with open(track_file, "a") as f:
            f.write(json.dumps({"tokens": total_tokens, "cost": cost, "model": self.model}) + "\n")

    async def stream(self, messages: list[Message], **kwargs: Any):
        raise NotImplementedError("Streaming not yet implemented for Inception")

    async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        raise NotImplementedError("Embeddings not supported by Inception")

    def estimate_cost(self, num_tokens: int) -> float:
        """Estimate cost for a given number of tokens."""
        return num_tokens * 0.00001  # Example pricing
