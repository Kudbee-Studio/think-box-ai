"""Control-plane receipt store singleton (PR #155)."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_receipt_store import (
    get_control_plane_receipt_store,
    reset_control_plane_receipt_store,
)


class TestControlPlaneReceiptStore(unittest.TestCase):
    def tearDown(self) -> None:
        reset_control_plane_receipt_store()

    def test_singleton_persists(self) -> None:
        a = get_control_plane_receipt_store()
        a.append("x", "ok", "r", "simulated")
        b = get_control_plane_receipt_store()
        self.assertEqual(b.count(), 1)

    def test_reset_clears(self) -> None:
        get_control_plane_receipt_store().append("x", "ok", "r", "simulated")
        reset_control_plane_receipt_store()
        self.assertEqual(get_control_plane_receipt_store().count(), 0)


if __name__ == "__main__":
    unittest.main()
