import unittest
from thinkbox.dashboard_state import get_dashboard_state, AutonomousLoopEntry
from thinkbox.dashboard_state import LoopActionEntry


def _reset_dashboard():
    from thinkbox.dashboard_state import DashboardState
    DashboardState._instance = None
    import thinkbox.dashboard_state as ds_mod
    ds_mod._dashboard_state = None


class TestAutonomousLoopControlActions(unittest.TestCase):
    def setUp(self) -> None:
        _reset_dashboard()
        self.state = get_dashboard_state()
        # Insert a loop entry
        self.state.upsert_autonomous_loop(AutonomousLoopEntry(loop_id="loopA"))

    def tearDown(self) -> None:
        _reset_dashboard()

    def test_record_action_updates_last_action(self) -> None:
        entry = self.state.record_loop_action("loopA", "start", result={"msg": "started"})
        self.assertIsInstance(entry, LoopActionEntry)
        self.assertEqual(entry.loop_id, "loopA")
        self.assertEqual(entry.action, "start")
        # Verify loop entry last_action updated
        loop = self.state.autonomous_loops["loopA"]
        self.assertEqual(loop.last_action, "start")

    def test_get_actions_per_loop(self) -> None:
        self.state.record_loop_action("loopA", "start")
        self.state.record_loop_action("loopA", "run")
        actions = self.state.get_loop_actions("loopA")
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0].action, "start")
        self.assertEqual(actions[1].action, "run")

    def test_get_all_actions_aggregates(self) -> None:
        # Add actions to two loops
        self.state.upsert_autonomous_loop(AutonomousLoopEntry(loop_id="loopB"))
        self.state.record_loop_action("loopA", "start")
        self.state.record_loop_action("loopB", "reset")
        all_actions = self.state.get_all_loop_actions()
        self.assertEqual(len(all_actions), 2)
        actions_by_loop = {a.loop_id: a.action for a in all_actions}
        self.assertEqual(actions_by_loop["loopA"], "start")
        self.assertEqual(actions_by_loop["loopB"], "reset")
