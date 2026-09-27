"""Unit tests for PR #162 era close helpers."""

from __future__ import annotations

import unittest

from thinkbox.receipt_chain_end_link_era_close import (
    ERA_GATE_SPECS,
    load_era_consolidated_pack,
    validate_era_consolidated_154_161_pack,
)


class TestReceiptChainEndLinkEraClose(unittest.TestCase):
    def test_consolidated_pack_valid(self) -> None:
        pack = load_era_consolidated_pack()
        violations = validate_era_consolidated_154_161_pack(pack)
        self.assertEqual(violations, [])
        self.assertEqual(len(pack["gates"]), len(ERA_GATE_SPECS))

    def test_rejects_live_verified(self) -> None:
        pack = load_era_consolidated_pack()
        bad = dict(pack)
        bad["live_verified"] = True
        violations = validate_era_consolidated_154_161_pack(bad)
        self.assertTrue(any(v.code == "era_live_verified" for v in violations))


if __name__ == "__main__":
    unittest.main()
