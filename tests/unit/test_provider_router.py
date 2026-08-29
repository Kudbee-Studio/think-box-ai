"""Tests for provider router and snapshot hashing."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from core.providers.base import CompletionResponse, Message, ProviderRegistry
from core.providers.router import ProviderRouter
from core.providers.snapshot import snapshot_hash


class TestSnapshotHash(unittest.TestCase):
    def test_deterministic(self):
        h1 = snapshot_hash([{"role": "user", "content": "hello"}])
        h2 = snapshot_hash([{"role": "user", "content": "hello"}])
        self.assertEqual(h1, h2)

    def test_different_inputs(self):
        h1 = snapshot_hash([{"role": "user", "content": "hello"}])
        h2 = snapshot_hash([{"role": "user", "content": "world"}])
        self.assertNotEqual(h1, h2)

    def test_kwargs_affect_hash(self):
        h1 = snapshot_hash([{"role": "user", "content": "hi"}], temperature=0.5)
        h2 = snapshot_hash([{"role": "user", "content": "hi"}], temperature=0.9)
        self.assertNotEqual(h1, h2)


class TestProviderRouter(unittest.TestCase):
    def test_unknown_provider_raises(self):
        router = ProviderRouter({
            "providers": [{"name": "nonexistent"}],
            "order": ["nonexistent"],
        })
        with self.assertRaises(ValueError):
            router._get_provider("nonexistent")

    @patch.object(ProviderRegistry, "get")
    def test_first_provider_wins(self, mock_get):
        mock_provider = AsyncMock()
        mock_provider.complete.return_value = CompletionResponse("ok", "test")
        mock_get.return_value = lambda config: mock_provider

        router = ProviderRouter({
            "providers": [{"name": "first"}, {"name": "second"}],
            "order": ["first", "second"],
        })

        import asyncio
        msgs = [Message(role="user", content="hello")]
        result = asyncio.run(router.complete(msgs))

        self.assertEqual(result.content, "ok")
        mock_provider.complete.assert_called_once()

    @patch.object(ProviderRegistry, "get")
    def test_failover_on_error(self, mock_get):
        failing = AsyncMock()
        failing.complete.side_effect = RuntimeError("fail")
        succeeding = AsyncMock()
        succeeding.complete.return_value = CompletionResponse("recovered", "backup")

        def factory(name):
            return lambda config: failing if name == "first" else succeeding

        mock_get.side_effect = factory

        router = ProviderRouter({
            "providers": [{"name": "first"}, {"name": "second"}],
            "order": ["first", "second"],
        })

        import asyncio
        msgs = [Message(role="user", content="hello")]
        result = asyncio.run(router.complete(msgs))

        self.assertEqual(result.content, "recovered")

    @patch.object(ProviderRegistry, "get")
    def test_snapshot_cache_skips_duplicate(self, mock_get):
        mock_provider = AsyncMock()
        mock_provider.complete.return_value = CompletionResponse("cached", "test")
        mock_get.return_value = lambda config: mock_provider

        router = ProviderRouter({
            "providers": [{"name": "p1"}],
            "order": ["p1"],
            "snapshot_cache": True,
        })

        import asyncio
        msgs = [Message(role="user", content="hello")]

        r1 = asyncio.run(router.complete(msgs))
        r2 = asyncio.run(router.complete(msgs))

        self.assertEqual(r1.content, "cached")
        self.assertEqual(r2.content, "cached")
        self.assertEqual(mock_provider.complete.call_count, 1)

    def test_list_available_filters_unknown(self):
        router = ProviderRouter({
            "providers": [{"name": "openai_compat"}, {"name": "nonexistent"}],
            "order": ["openai_compat", "nonexistent"],
        })
        available = router.list_available()
        self.assertIn("openai_compat", available)
        self.assertNotIn("nonexistent", available)

    def test_clear_cache(self):
        router = ProviderRouter({
            "providers": [{"name": "p1"}],
            "snapshot_cache": True,
        })
        router._cache["abc"] = CompletionResponse("x", "y")
        router.clear_cache()
        self.assertEqual(len(router._cache), 0)


if __name__ == "__main__":
    unittest.main()
