"""Unit tests for PR #154–#164 era chronicle pack (PR #165 theme D)."""

from __future__ import annotations

import unittest

from thinkbox.pr165_era_chronicle import (
    load_era_154_164_chronicle_pack,
    validate_era_154_164_chronicle_pack,
)


class TestPr165EraChronicle(unittest.TestCase):
    def test_pack_loads_and_validates(self) -> None:
        pack = load_era_154_164_chronicle_pack()
        violations = validate_era_154_164_chronicle_pack(pack)
        self.assertEqual(violations, [])
        self.assertFalse(pack["live_verified"])
        self.assertFalse(pack["live_api_called"])


if __name__ == "__main__":
    unittest.main()
