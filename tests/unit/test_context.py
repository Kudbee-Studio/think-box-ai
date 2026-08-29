"""Tests for context window management and LRU cache."""

from __future__ import annotations

import time
import unittest

from core.providers.base import Message
from core.memory.context import ContextManager, ContextWindow, LRUCache


class TestLRUCache(unittest.TestCase):
    def test_put_and_get(self):
        cache = LRUCache(max_size=3, ttl_seconds=60)
        cache.put("a", 1)
        self.assertEqual(cache.get("a"), 1)

    def test_eviction(self):
        cache = LRUCache(max_size=2, ttl_seconds=60)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)  # Evicts "a"
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.get("b"), 2)
        self.assertEqual(cache.get("c"), 3)

    def test_ttl_expiry(self):
        cache = LRUCache(max_size=10, ttl_seconds=0.01)
        cache.put("a", 1)
        time.sleep(0.02)
        self.assertIsNone(cache.get("a"))

    def test_invalidate(self):
        cache = LRUCache(max_size=10, ttl_seconds=60)
        cache.put("a", 1)
        cache.invalidate("a")
        self.assertIsNone(cache.get("a"))

    def test_clear(self):
        cache = LRUCache(max_size=10, ttl_seconds=60)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.clear()
        self.assertEqual(cache.size, 0)


class TestContextWindow(unittest.TestCase):
    def test_add_message(self):
        w = ContextWindow(session_id="s1", max_tokens=1000)
        w.add_message("user", "hello")
        self.assertEqual(len(w.messages), 1)

    def test_trim_to_limit(self):
        w = ContextWindow(session_id="s1", max_tokens=10)
        for i in range(20):
            w.add_message("user", "x" * 10)
        self.assertLessEqual(w._estimate_tokens(), 10)

    def test_summary(self):
        w = ContextWindow(session_id="s1", max_tokens=1000)
        w.add_message("user", "hello")
        s = w.summary()
        self.assertEqual(s["session_id"], "s1")
        self.assertEqual(s["message_count"], 1)


class TestContextManager(unittest.TestCase):
    def test_get_or_create(self):
        mgr = ContextManager(max_sessions=10)
        w = mgr.get_or_create("s1")
        self.assertIsNotNone(w)
        self.assertEqual(w.session_id, "s1")

    def test_add_message(self):
        mgr = ContextManager(max_sessions=10)
        w = mgr.add_message("s1", "user", "hello")
        self.assertEqual(len(w.messages), 1)

    def test_session_eviction(self):
        mgr = ContextManager(max_sessions=2)
        mgr.get_or_create("s1")
        mgr.get_or_create("s2")
        mgr.get_or_create("s3")  # Evicts s1
        self.assertNotIn("s1", mgr._windows)

    def test_cache_response(self):
        mgr = ContextManager()
        mgr.cache_response("hash1", {"result": "ok"})
        cached = mgr.get_cached_response("hash1")
        self.assertEqual(cached["result"], "ok")

    def test_hash_prompt(self):
        mgr = ContextManager()
        messages = [Message(role="user", content="hello")]
        h1 = mgr.hash_prompt(messages)
        h2 = mgr.hash_prompt(messages)
        self.assertEqual(h1, h2)  # Deterministic


if __name__ == "__main__":
    unittest.main()
