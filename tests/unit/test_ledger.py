"""Unit tests for thinkbox/ledger.py — tamper-evident action ledger."""

import tempfile
import unittest
from pathlib import Path

from thinkbox.ledger import ActionLedger


class TestActionLedger(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger = ActionLedger(Path(self._tmp.name) / "ledger.db")

    def tearDown(self) -> None:
        self.ledger.close()
        self._tmp.cleanup()

    def test_append_and_verify(self):
        self.ledger.append("a1", "file:read", "read_file", True, "admitted")
        self.ledger.append("a2", "net:http", "fetch", False, "token_invalid")
        self.assertTrue(self.ledger.verify())

    def test_entries_filtered(self):
        self.ledger.append("a1", "cap:x", "act", True, "ok")
        self.ledger.append("a2", "cap:y", "act", True, "ok")
        entries = self.ledger.entries(agent_id="a1")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["agent_id"], "a1")

    def test_tamper_detected(self):
        self.ledger.append("a1", "cap:x", "act", True, "ok")
        self.ledger.append("a2", "cap:y", "act", True, "ok")
        with self.ledger._lock:
            self.ledger._conn.execute(
                "UPDATE ledger SET allowed = 0 WHERE agent_id = 'a2'"
            )
            self.ledger._conn.commit()
        self.assertFalse(self.ledger.verify())

    def test_empty_ledger_verifies(self):
        self.assertTrue(self.ledger.verify())
        self.assertEqual(self.ledger.entries(), [])


if __name__ == "__main__":
    unittest.main()