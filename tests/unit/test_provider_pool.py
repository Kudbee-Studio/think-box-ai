"""Tests for provider connection pooling."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

import httpx

from thinkbox.model_client import AsyncModelClient, ModelConfig, ModelCallError


class TestConnectionPool(unittest.TestCase):
    """Test connection pooling in AsyncModelClient."""

    def test_client_initialization_with_pool(self):
        """AsyncModelClient initializes with connection pool."""

        async def test():
            config = ModelConfig(api_type="ollama")
            client = AsyncModelClient(config)
            self.assertTrue(client._use_pool)

            # Get client and verify it's created
            http_client = await client._get_client()
            self.assertIsNotNone(http_client)
            self.assertIsInstance(http_client, httpx.AsyncClient)
            await client.close()

        asyncio.run(test())

    @patch.dict("os.environ", {"ASYNC_PROVIDER_POOL": "false"})
    def test_client_disable_pool(self):
        """Connection pool can be disabled via env var."""
        config = ModelConfig(api_type="ollama")
        client = AsyncModelClient(config)
        self.assertFalse(client._use_pool)

    def test_client_reuse(self):
        """AsyncClient is reused across calls."""

        async def test():
            config = ModelConfig(api_type="ollama")
            client = AsyncModelClient(config)

            http_client_1 = await client._get_client()
            http_client_2 = await client._get_client()

            self.assertIs(http_client_1, http_client_2)
            await client.close()

        asyncio.run(test())

    def test_close_closes_pool(self):
        """close() closes the connection pool."""

        async def test():
            config = ModelConfig(api_type="ollama")
            client = AsyncModelClient(config)

            http_client = await client._get_client()
            self.assertIsNotNone(client._client)

            await client.close()
            self.assertIsNone(client._client)

        asyncio.run(test())


class TestHeaders(unittest.TestCase):
    """Test header construction."""

    def test_headers_no_auth(self):
        """Headers without auth key."""
        config = ModelConfig(api_type="ollama")
        client = AsyncModelClient(config)

        headers = client._headers()
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertNotIn("Authorization", headers)

    def test_headers_with_auth(self):
        """Headers with Bearer auth."""
        config = ModelConfig(api_type="openai_compat", api_key="test-key-123")
        client = AsyncModelClient(config)

        headers = client._headers()
        self.assertEqual(headers["Authorization"], "Bearer test-key-123")


class TestPayloadConstruction(unittest.TestCase):
    """Test request payload construction."""

    def test_ollama_payload(self):
        """Ollama payload format."""
        config = ModelConfig(api_type="ollama", model="llama2", temperature=0.5, max_tokens=1024)
        client = AsyncModelClient(config)

        payload = client._ollama_payload("test prompt", stream=False, temperature=0.7)
        self.assertEqual(payload["model"], "llama2")
        self.assertEqual(payload["prompt"], "test prompt")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["options"]["temperature"], 0.7)
        self.assertEqual(payload["options"]["num_predict"], 1024)

    def test_openai_payload(self):
        """OpenAI payload format."""
        config = ModelConfig(api_type="openai_compat", model="gpt-4", temperature=0.5, max_tokens=2048)
        client = AsyncModelClient(config)

        payload = client._openai_payload("test prompt", stream=False, max_tokens=1000)
        self.assertEqual(payload["model"], "gpt-4")
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertEqual(payload["messages"][0]["content"], "test prompt")
        self.assertEqual(payload["temperature"], 0.5)
        self.assertEqual(payload["max_tokens"], 1000)

    def test_openai_payload_with_stream(self):
        """OpenAI payload with streaming."""
        config = ModelConfig(api_type="openai_compat")
        client = AsyncModelClient(config)

        payload = client._openai_payload("test", stream=True)
        self.assertTrue(payload["stream"])


class TestErrorHandling(unittest.TestCase):
    """Test error handling and retryability."""

    def test_model_call_error_creation(self):
        """ModelCallError captures provider info."""
        config = ModelConfig(api_type="openai_compat", model="gpt-4")
        client = AsyncModelClient(config)

        error = client._error("Test error", retryable=True)
        self.assertIsInstance(error, ModelCallError)
        self.assertEqual(error.provider, "openai_compat")
        self.assertEqual(error.model, "gpt-4")
        self.assertTrue(error.retryable)
        self.assertIn("openai_compat:gpt-4", str(error))


if __name__ == "__main__":
    unittest.main()
