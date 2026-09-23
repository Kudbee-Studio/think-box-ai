"""Unit tests for proprietary END LINK API helpers (PR #156)."""

from __future__ import annotations

import unittest

from thinkbox.end_link_api import (
    END_LINK_API_LABEL,
    EndLinkViolation,
    build_end_link_batch_path,
    build_end_link_path,
    merge_end_link_deepen_fields,
    normalize_end_link_receipt_id,
    parse_end_link_envelope,
)


class TestEndLinkApi(unittest.TestCase):
    def test_build_path(self) -> None:
        path = build_end_link_path("rcpt_abc")
        self.assertIn("/receipts/rcpt_abc/validate", path)
        self.assertEqual(END_LINK_API_LABEL, "END_LINK")

    def test_normalize_rejects_empty(self) -> None:
        with self.assertRaises(EndLinkViolation):
            normalize_end_link_receipt_id("  ")

    def test_parse_envelope(self) -> None:
        env = {
            "data": {
                "receipt_id": "r1",
                "valid": True,
                "live_api_called": False,
                "link_integrity": "ok",
            },
        }
        result = parse_end_link_envelope(env, receipt_id="r1", http_status=200, etag='W/"x"')
        self.assertTrue(result.valid)
        self.assertFalse(result.live_api_called)
        self.assertEqual(result.link_integrity, "ok")

    def test_batch_path(self) -> None:
        self.assertIn("/validate/batch", build_end_link_batch_path())

    def test_merge_deepen_fields(self) -> None:
        merged = merge_end_link_deepen_fields(
            {"receipt_id": "r1", "valid": True},
            {"link_integrity": "ok", "prev_receipt_id": "p0"},
        )
        self.assertEqual(merged["link_integrity"], "ok")


if __name__ == "__main__":
    unittest.main()
