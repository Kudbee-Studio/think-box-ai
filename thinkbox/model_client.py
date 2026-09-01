"""Async model client for ThinkBox AI.

Supports async streaming requests for local inference backends
(Ollama native and vLLM/OpenAI-compatible endpoints).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncGenerator


@dataclass
class ModelConfig:
    base_url: str = "http://localhost:11434"
    model: str = "llama3.1:8b"
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 120
    api_type: str = "ollama"


class AsyncModelClient:
    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        if self.config.api_type == "ollama":
            return await self._ollama_generate(prompt, **kwargs)
        return await self._openai_generate(prompt, **kwargs)

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncGenerator[str, None]:
        if self.config.api_type == "ollama":
            async for token in self._ollama_stream(prompt, **kwargs):
                yield token
        else:
            async for token in self._openai_stream(prompt, **kwargs):
                yield token

    async def _ollama_generate(self, prompt: str, **kwargs: Any) -> str:
        import urllib.request
        import urllib.error

        url = f"{self.config.base_url}/api/generate"
        data = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                result = json.loads(resp.read())
                return result.get("response", "")
        except Exception as e:
            return f"[Error: {e}]"

    async def _ollama_stream(self, prompt: str, **kwargs: Any) -> AsyncGenerator[str, None]:
        import urllib.request
        import urllib.error

        url = f"{self.config.base_url}/api/generate"
        data = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": True,
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                for line in resp:
                    if line:
                        try:
                            chunk = json.loads(line)
                            if chunk.get("response"):
                                yield chunk["response"]
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"[Error: {e}]"

    async def _openai_generate(self, prompt: str, **kwargs: Any) -> str:
        import urllib.request
        import urllib.error

        url = f"{self.config.base_url}/v1/chat/completions"
        data = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                result = json.loads(resp.read())
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            return f"[Error: {e}]"

    async def _openai_stream(self, prompt: str, **kwargs: Any) -> AsyncGenerator[str, None]:
        import urllib.request
        import urllib.error

        url = f"{self.config.base_url}/v1/chat/completions"
        data = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                for line in resp:
                    if line.startswith(b"data: "):
                        try:
                            chunk = json.loads(line[6:])
                            content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"[Error: {e}]"
