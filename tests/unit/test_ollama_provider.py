"""Unit tests for OllamaProvider using urllib mocks."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from core.foundation.errors import ProviderRateLimitError, ProviderUnavailableError
from core.providers.base import Message
from core.providers.ollama import OllamaProvider


class TestOllamaProvider(unittest.TestCase):
    def test_create_provider(self) -> None:
        provider = OllamaProvider({"api_key": "test-key", "model": "llama3"})
        self.assertEqual(provider._model, "llama3")
        self.assertEqual(provider._base_url, "http://localhost:11434")

    def test_custom_base_url(self) -> None:
        provider = OllamaProvider({"base_url": "http://localhost:8000", "model": "custom"})
        self.assertEqual(provider._base_url, "http://localhost:8000")
        self.assertEqual(provider._model, "custom")

    def test_complete_success(self) -> None:
        provider = OllamaProvider({"model": "llama3"})
        mock_response = {
            "model": "llama3",
            "message": {"role": "assistant", "content": "Hello Ollama"},
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
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
            self.assertEqual(completion.content, "Hello Ollama")
            self.assertEqual(completion.model, "llama3")
            self.assertEqual(completion.usage["total_tokens"], 8)

    def test_complete_rate_limit(self) -> None:
        provider = OllamaProvider({})
        import urllib.error
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "http://localhost:11434/api/chat",
                429,
                "Too Many Requests",
                {},
                None,
            )
            import asyncio
            messages = [Message(role="user", content="Hi")]
            with self.assertRaises(ProviderRateLimitError):
                asyncio.run(provider.complete(messages))

    def test_complete_auth_failure(self) -> None:
        provider = OllamaProvider({})
        import urllib.error
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "http://localhost:11434/api/chat",
                401,
                "Unauthorized",
                {},
                None,
            )
            import asyncio
            messages = [Message(role="user", content="Hi")]
            with self.assertRaises(ProviderUnavailableError):
                asyncio.run(provider.complete(messages))

    def test_list_models_success(self) -> None:
        provider = OllamaProvider({})
        mock_response = {"models": [{"name": "model1"}, {"name": "model2"}]}
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_context.status = 200
            mock_urlopen.return_value = mock_context
            import asyncio
            models = asyncio.run(provider.list_models())
            self.assertEqual(models, mock_response["models"])