"""Ollama client for kudbEE — streaming model inference."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

import aiohttp

OLLAMA_BASE_URL = "http://localhost:11434"


async def list_models() -> list[dict[str, Any]]:
    """List available Ollama models."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{OLLAMA_BASE_URL}/api/tags") as resp:
                data = await resp.json()
                return data.get("models", [])
    except Exception:
        return []


async def stream_chat(
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """Stream chat completion tokens from Ollama."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        continue
                    try:
                        data = json.loads(line_str)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        yield f"[Error: {str(e)}]"


async def chat_completion(
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Non-streaming chat completion."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                data = await resp.json()
                return data.get("message", {}).get("content", "")
    except Exception as e:
        return f"[Error: {str(e)}]"
