"""control_plane_conditional helpers (PR #155)."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_conditional import (
    chain_read_etag,
    etag_for_chain_status,
    record_chain_response_in_store,
    should_return_not_modified,
)


class TestControlPlaneConditional(unittest.TestCase):
    def test_chain_etag_stable(self) -> None:
        status = {"chain_valid": True, "total_receipts": 0, "latest": [], "issues": []}
        a = etag_for_chain_status(status)
        b = etag_for_chain_status(status)
        self.assertEqual(a, b)

    def test_chain_read_etag_uses_explicit(self) -> None:
        block = {"etag": 'W/"fixed"', "chain": {}}
        self.assertEqual(chain_read_etag(block), 'W/"fixed"')

    def test_should_return_not_modified(self) -> None:
        tag = etag_for_chain_status({"x": 1})
        self.assertTrue(should_return_not_modified(tag, tag))

    def test_record_chain_response(self) -> None:
        store: dict = {}
        record_chain_response_in_store(
            store,
            "/api/v1/control-plane/receipts/chain",
            etag='W/"t"',
            body={"ok": True},
        )
        self.assertIn("/api/v1/control-plane/receipts/chain", store)


if __name__ == "__main__":
    unittest.main()
