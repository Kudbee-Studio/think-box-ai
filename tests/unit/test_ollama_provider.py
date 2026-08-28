"""Unit tests for core.providers.ollama."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

import urllib.error

from core.foundation.errors import ProviderError, ProviderUnavailableError
from core.providers.base import Message, ProviderCapabilities
from core.providers.ollama import OllamaProvider


class TestOllamaProviderInit(unittest.TestCase):
    def test_config_precedence_over_env(self) -> None:
        import os
        os.environ["THINKBOX_OLLAMA_BASE_URL"] = "http://env-host:11434"
        os.environ["THINKBOX_OLLAMA_MODEL"] = "env-model"
        try:
            provider = OllamaProvider({
                "base_url": "http://config-host:11434",
                "model": "config-model",
            })
            self.assertEqual(provider._base_url, "http://config-host:11434")
            self.assertEqual(provider._model, "config-model")
        finally:
            del os.environ["THINKBOX_OLLAMA_BASE_URL"]
            del os.environ["THINKBOX_OLLAMA_MODEL"]

    def test_env_vars_used_when_no_config(self) -> None:
        import os
        os.environ["THINKBOX_OLLAMA_BASE_URL"] = "http://env-host:11434"
        os.environ["THINKBOX_OLLAMA_MODEL"] = "env-model"
        try:
            provider = OllamaProvider()
            self.assertEqual(provider._base_url, "http://env-host:11434")
            self.assertEqual(provider._model, "env-model")
        finally:
            del os.environ["THINKBOX_OLLAMA_BASE_URL"]
            del os.environ["THINKBOX_OLLAMA_MODEL"]

    def test_defaults_when_no_config_no_env(self) -> None:
        import os
        os.environ.pop("THINKBOX_OLLAMA_BASE_URL", None)
        os.environ.pop("THINKBOX_OLLAMA_MODEL", None)
        provider = OllamaProvider()
        self.assertEqual(provider._base_url, "http://localhost:11434")
        self.assertEqual(provider._model, "llama3")

    def test_capabilities(self) -> None:
        provider = OllamaProvider({"model": "llama3"})
        caps = provider.capabilities
        self.assertTrue(caps.completion)
        self.assertTrue(caps.streaming)
        self.assertFalse(caps.embedding)
        self.assertTrue(caps.supports_system_prompt)


class TestOllamaProviderComplete(unittest.TestCase):
    def test_complete_success(self) -> None:
        provider = OllamaProvider({"base_url": "http://localhost:11434", "model": "llama3"})

        mock_response = {
            "model": "llama3",
            "message": {"role": "assistant", "content": "Hello from Ollama!"},
            "done": True,
            "prompt_eval_count": 10,
            "eval_count": 5,
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_context.status = 200
            mock_urlopen.return_value = mock_context

            import asyncio
            messages = [Message(role="user", content="Hi")]
            completion = asyncio.run(provider.complete(messages))

            self.assertEqual(completion.content, "Hello from Ollama!")
            self.assertEqual(completion.model, "llama3")
            self.assertEqual(completion.usage["prompt_eval_count"], 10)
            self.assertEqual(completion.usage["eval_count"], 5)

    def test_complete_non_200_status(self) -> None:
        provider = OllamaProvider({"base_url": "http://localhost:11434", "model": "llama3"})

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.status = 500
            mock_context.read.return_value = b"Internal Server Error"
            mock_urlopen.return_value = mock_context

            import asyncio
            messages = [Message(role="user", content="Hi")]
            with self.assertRaises(ProviderUnavailableError):
                asyncio.run(provider.complete(messages))

    def test_complete_http_error(self) -> None:
        provider = OllamaProvider({"base_url": "http://localhost:11434", "model": "llama3"})

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "http://localhost:11434/api/chat",
                404,
                "Not Found",
                {},
                None,
            )

            import asyncio
            messages = [Message(role="user", content="Hi")]
            with self.assertRaises(ProviderUnavailableError):
                asyncio.run(provider.complete(messages))

    def test_complete_connection_error(self) -> None:
        provider = OllamaProvider({"base_url": "http://localhost:11434", "model": "llama3"})

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            import asyncio
            messages = [Message(role="user", content="Hi")]
            with self.assertRaises(ProviderUnavailableError):
                asyncio.run(provider.complete(messages))


class TestOllamaProviderStream(unittest.TestCase):
    def test_stream_ndjson_tokens(self) -> None:
        provider = OllamaProvider({"base_url": "http://localhost:11434", "model": "llama3"})

        ndjson_data = (
            b'{"model":"llama3","message":{"content":"Hello"},"done":false}\n'
            b'{"model":"llama3","message":{"content":" world"},"done":false}\n'
            b'{"model":"llama3","message":{"content":"!"},"done":true}\n'
        )

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.status = 200
            mock_context.__iter__ = MagicMock(return_value=iter(ndjson_data.split(b"\n")))
            mock_urlopen.return_value = mock_context

            import asyncio
            messages = [Message(role="user", content="Hi")]

            async def collect():
                tokens = []
                async for token in provider.stream(messages):
                    tokens.append(token)
                return tokens

            tokens = asyncio.run(collect())
            self.assertEqual(tokens, ["Hello", " world", "!"])

    def test_stream_non_200_status(self) -> None:
        provider = OllamaProvider({"base_url": "http://localhost:11434", "model": "llama3"})

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.status = 503
            mock_urlopen.return_value = mock_context

            import asyncio
            messages = [Message(role="user", content="Hi")]

            async def collect():
                tokens = []
                async for token in provider.stream(messages):
                    tokens.append(token)
                return tokens

            with self.assertRaises(ProviderUnavailableError):
                asyncio.run(collect())

    def test_stream_connection_error(self) -> None:
        provider = OllamaProvider({"base_url": "http://localhost:11434", "model": "llama3"})

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            import asyncio
            messages = [Message(role="user", content="Hi")]

            async def collect():
                tokens = []
                async for token in provider.stream(messages):
                    tokens.append(token)
                return tokens

            with self.assertRaises(ProviderUnavailableError):
                asyncio.run(collect())


class TestOllamaProviderEmbed(unittest.TestCase):
    def test_embed_raises_not_implemented(self) -> None:
        provider = OllamaProvider({"model": "llama3"})
        import asyncio
        with self.assertRaises(NotImplementedError):
            asyncio.run(provider.embed(["test text"]))


class TestOllamaProviderListModels(unittest.TestCase):
    def test_list_models_success(self) -> None:
        provider = OllamaProvider({"base_url": "http://localhost:11434", "model": "llama3"})

        mock_response = {
            "models": [
                {"name": "llama3:latest", "size": 3825819519},
                {"name": "mistral:latest", "size": 4108917719},
            ]
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_context.status = 200
            mock_urlopen.return_value = mock_context

            import asyncio
            models = asyncio.run(provider.list_models())
            self.assertEqual(len(models), 2)
            self.assertEqual(models[0]["name"], "llama3:latest")

    def test_list_models_non_200_raises(self) -> None:
        provider = OllamaProvider({"base_url": "http://localhost:11434", "model": "llama3"})

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.status = 500
            mock_urlopen.return_value = mock_context

            import asyncio
            with self.assertRaises(ProviderUnavailableError):
                asyncio.run(provider.list_models())

    def test_list_models_connection_error_raises(self) -> None:
        provider = OllamaProvider({"base_url": "http://localhost:11434", "model": "llama3"})

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            import asyncio
            with self.assertRaises(ProviderUnavailableError):
                asyncio.run(provider.list_models())


if __name__ == "__main__":
    unittest.main()
