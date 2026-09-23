"""Unit tests for read_cache (PR #135)."""

from __future__ import annotations

import unittest

from thinkbox.read_cache import (
    RevisionCounter,
    TtlSnapshotCache,
    etag_matches,
    reset_read_caches_for_tests,
    weak_etag_from_payload,
)


class TestEtag(unittest.TestCase):
    def test_weak_etag_stable(self) -> None:
        a = weak_etag_from_payload({"x": 1})
        b = weak_etag_from_payload({"x": 1})
        self.assertEqual(a, b)
        self.assertTrue(etag_matches(a, a))

    def test_etag_star(self) -> None:
        self.assertTrue(etag_matches("*", 'W/"abc"'))

    def test_oversized_if_none_match_rejected(self) -> None:
        self.assertFalse(etag_matches("x" * 5000, 'W/"abc"'))


class TestTtlCache(unittest.TestCase):
    def test_invalidate_prefix(self) -> None:
        cache = TtlSnapshotCache[int](ttl_seconds=60.0)
        cache.set("prefix:a", 1)
        cache.set("prefix:b", 2)
        cache.set("other:c", 3)
        cache.invalidate_prefix("prefix:")
        self.assertIsNone(cache.get("prefix:a"))
        self.assertIsNotNone(cache.get("other:c"))

    def test_get_or_load_once(self) -> None:
        cache = TtlSnapshotCache[dict](ttl_seconds=60.0)
        calls = {"n": 0}

        def loader() -> dict:
            calls["n"] += 1
            return {"v": 1}

        v1, _ = cache.get_or_load("k", loader)
        v2, _ = cache.get_or_load("k", loader)
        self.assertEqual(v1, v2)
        self.assertEqual(calls["n"], 1)


class TestRevision(unittest.TestCase):
    def test_bump_increments(self) -> None:
        rev = RevisionCounter()
        self.assertEqual(rev.value, 0)
        rev.bump()
        self.assertEqual(rev.value, 1)
        self.assertIn("rev-", rev.etag())


class TestReset(unittest.TestCase):
    def test_reset_clears_receipt_cache(self) -> None:
        from thinkbox.read_cache import receipt_cache

        receipt_cache().set("receipt:r1", {"ok": True})
        reset_read_caches_for_tests()
        self.assertIsNone(receipt_cache().get("receipt:r1"))


if __name__ == "__main__":
    unittest.main()
