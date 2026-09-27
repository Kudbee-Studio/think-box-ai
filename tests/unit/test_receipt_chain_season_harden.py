"""Unit tests for receipt-chain season harden (PR #165 theme C)."""

from __future__ import annotations

import unittest

from thinkbox.receipt_chain_end_link_season_harden import (
    end_link_etag_token_valid,
    validate_end_link_etag_pairs,
)


class TestReceiptChainSeasonHarden(unittest.TestCase):
    def test_etag_token_valid(self) -> None:
        self.assertTrue(end_link_etag_token_valid("a1b2c3d4e5f67890"))
        self.assertFalse(end_link_etag_token_valid(""))

    def test_pair_length_mismatch(self) -> None:
        v = validate_end_link_etag_pairs(["a"], [])
        self.assertTrue(any(x.code == "length_mismatch" for x in v))


if __name__ == "__main__":
    unittest.main()
