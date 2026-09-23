"""Unit tests for read_cache ETag helpers (PR #155)."""

from __future__ import annotations

import unittest

from thinkbox.read_cache import (
    etag_matches,
    normalize_etag_token,
    parse_entity_tags,
    strong_etag_from_payload,
    weak_etag_from_payload,
)


class TestReadCacheEtagPr155(unittest.TestCase):
    def test_weak_and_strong_differ(self) -> None:
        payload = {"n": 1}
        weak = weak_etag_from_payload(payload)
        strong = strong_etag_from_payload(payload)
        self.assertTrue(weak.startswith('W/"'))
        self.assertTrue(strong.startswith('"'))
        self.assertNotEqual(weak, strong)

    def test_weak_match_normalizes(self) -> None:
        tag = weak_etag_from_payload({"a": 1})
        inner = normalize_etag_token(tag)
        self.assertTrue(etag_matches(inner, tag))
        self.assertTrue(etag_matches(tag, tag))

    def test_parse_entity_tags_star(self) -> None:
        self.assertEqual(parse_entity_tags("*"), ("*",))

    def test_parse_entity_tags_list(self) -> None:
        tags = parse_entity_tags('W/"abc", "def"')
        self.assertEqual(len(tags), 2)

    def test_etag_matches_rejects_oversized(self) -> None:
        self.assertFalse(etag_matches("x" * 5000, 'W/"abc"'))


if __name__ == "__main__":
    unittest.main()
