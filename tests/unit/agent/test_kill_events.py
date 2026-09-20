"""Tests for kill-switch durable events."""

import unittest
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.kill_events import KillSwitch


class TestKillEvents(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ActionReceiptStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_kill_creates_event(self) -> None:
        ks = KillSwitch(self.store)
        event = ks.kill("agent-1", reason="test")
        self.assertTrue(event.event_id.startswith("kill_agent-1_"))
        self.assertEqual(event.event_type, "kill")

    def test_quarantine_creates_event(self) -> None:
        ks = KillSwitch(self.store)
        event = ks.quarantine("agent-2")
        self.assertTrue(event.event_id.startswith("quar_agent-2_"))
        self.assertEqual(event.event_type, "quarantine")

    def test_query_by_agent(self) -> None:
        ks = KillSwitch(self.store)
        ks.kill("a1", reason="r1")
        ks.kill("a2", reason="r2")
        events = ks.query_events(agent_id="a1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["agent_id"], "a1")

    def test_query_by_type(self) -> None:
        ks = KillSwitch(self.store)
        ks.kill("a1")
        ks.quarantine("a1")
        kills = ks.query_events(event_type="kill")
        self.assertEqual(len(kills), 1)
        self.assertEqual(kills[0]["event_type"], "kill")

    def test_query_all(self) -> None:
        ks = KillSwitch(self.store)
        ks.kill("a1")
        ks.quarantine("a1")
        ks.kill("a2")
        events = ks.query_events()
        self.assertEqual(len(events), 3)

    def test_events_durable_via_store(self) -> None:
        ks = KillSwitch(self.store)
        ks.kill("a1")
        ks.quarantine("a2")
        self.assertTrue(self.store.verify())
        self.assertEqual(self.store.count(), 2)

    def test_events_after_close_reopen(self) -> None:
        import tempfile, os
        path = os.path.join(tempfile.mkdtemp(), "kill.db")
        store = ActionReceiptStore(path)
        ks = KillSwitch(store)
        ks.kill("a1", reason="persistent")
        store.close()
        reopened = ActionReceiptStore(path)
        try:
            self.assertTrue(reopened.verify())
            self.assertGreaterEqual(reopened.count(), 1)
        finally:
            reopened.close()
