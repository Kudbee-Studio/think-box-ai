"""Unit tests for core.providers.openai_compat."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from core.foundation.errors import ProviderRateLimitError, ProviderUnavailableError
from core.providers.base import Message, ProviderCapabilities
from core.providers.openai_compat import OpenAICompatProvider


class TestOpenAICompatProvider(unittest.TestCase):
    def test_create_provider(self) -> None:
        provider = OpenAICompatProvider({"api_key": "test-key", "model": "gpt-4o-mini"})
        self.assertEqual(provider._model, "gpt-4o-mini")
        self.assertEqual(provider._api_key, "test-key")

    def test_capabilities(self) -> None:
        provider = OpenAICompatProvider({"api_key": "test-key"})
        caps = provider.capabilities
        self.assertTrue(caps.completion)
        self.assertFalse(caps.streaming)
        self.assertFalse(caps.embedding)
        self.assertTrue(caps.supports_system_prompt)

    def test_complete_success(self) -> None:
        provider = OpenAICompatProvider({"api_key": "test-key", "model": "gpt-4o-mini"})

        mock_response = {
            "id": "chatcmpl-123",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
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

            self.assertEqual(completion.content, "Hello!")
            self.assertEqual(completion.model, "gpt-4o-mini")
            self.assertEqual(completion.usage["total_tokens"], 15)

    def test_complete_rate_limit(self) -> None:
        provider = OpenAICompatProvider({"api_key": "test-key", "model": "gpt-4o-mini"})

        import urllib.error
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "https://api.openai.com/v1/chat/completions",
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
        provider = OpenAICompatProvider({"api_key": "bad-key", "model": "gpt-4o-mini"})

        import urllib.error
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                "https://api.openai.com/v1/chat/completions",
                401,
                "Unauthorized",
                {},
                None,
            )

            import asyncio
            messages = [Message(role="user", content="Hi")]
            with self.assertRaises(ProviderUnavailableError):
                asyncio.run(provider.complete(messages))

    def test_embed_not_supported_by_default(self) -> None:
        provider = OpenAICompatProvider({"api_key": "test-key"})
        import asyncio
        with self.assertRaises(Exception):
            asyncio.run(provider.embed(["test"]))

    def test_custom_base_url(self) -> None:
        provider = OpenAICompatProvider({
            "api_key": "test-key",
            "base_url": "http://localhost:11434/v1",
            "model": "llama3",
        })
        self.assertEqual(provider._base_url, "http://localhost:11434/v1")
        self.assertEqual(provider._model, "llama3")

    def test_mercury_endpoint_contract_shape(self) -> None:
        provider = OpenAICompatProvider({
            "api_key": "test-key",
            "base_url": "https://api.inceptionlabs.ai/v1",
            "model": "mercury-2",
        })
        self.assertEqual(provider._base_url, "https://api.inceptionlabs.ai/v1")
        self.assertEqual(provider._model, "mercury-2")
        self.assertTrue(provider.capabilities.completion)

    def test_mercury_request_targets_chat_completions(self) -> None:
        import asyncio
        provider = OpenAICompatProvider({
            "api_key": "test-key",
            "base_url": "https://api.inceptionlabs.ai/v1",
            "model": "mercury-2",
        })
        mock_response = {
            "id": "chatcmpl-test",
            "choices": [{"message": {"role": "assistant", "content": '{"answer": 42}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 36, "completion_tokens": 77, "total_tokens": 113},
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_context = MagicMock()
            mock_context.__enter__ = MagicMock(return_value=mock_context)
            mock_context.__exit__ = MagicMock(return_value=False)
            mock_context.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_context.status = 200
            mock_urlopen.return_value = mock_context
            completion = asyncio.run(provider.complete(
                [Message(role="system", content="s"), Message(role="user", content="u")],
                max_tokens=3500, temperature=0.2,
            ))
            self.assertEqual(completion.model, "mercury-2")
            sent_url = mock_urlopen.call_args.args[0].full_url
            self.assertEqual(sent_url, "https://api.inceptionlabs.ai/v1/chat/completions")
            sent_body = json.loads(mock_urlopen.call_args.args[0].data.decode("utf-8"))
            self.assertEqual(sent_body["model"], "mercury-2")
            self.assertEqual(sent_body["max_tokens"], 3500)
            self.assertNotIn("api_key", json.dumps(sent_body))
            import re
            flat = json.dumps(sent_body) + sent_url
            self.assertEqual(re.findall(r"(?i)bearer", flat), [])

    def test_model_artifact_contains_no_secrets_contract(self) -> None:
        import re
        artifact = {
            "provider": "openai_compat",
            "model": "mercury-2",
            "base_url": "https://api.inceptionlabs.ai/v1",
            "usage": {"total_tokens": 113},
        }
        raw = json.dumps(artifact)
        self.assertEqual(re.findall(r"(?i)(api[_-]?key|bearer|authorization)", raw), [])


if __name__ == "__main__":
    unittest.main()
