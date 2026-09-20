"""Tests for pipeline PR state machine hardening."""

from __future__ import annotations

import unittest

from thinkbox.pipeline_state_machine import (
    PipelinePRState,
    infer_state_from_receipts,
    state_machine_report,
    validate_transition,
)


class TestPipelineStateMachine(unittest.TestCase):
    def test_infer_from_newest_receipt(self) -> None:
        rows = [
            {"to_state": "LEARN", "from_state": "EXECUTE", "action": "learn"},
            {"to_state": "EXECUTE", "from_state": "IDENTIFY", "action": "run"},
        ]
        self.assertEqual(infer_state_from_receipts(rows), "LEARN")

    def test_terminal_exit_blocked(self) -> None:
        ok, reason = validate_transition("LEARN", "EXECUTE", "resume")
        self.assertFalse(ok)
        self.assertIn("illegal_exit", reason)

    def test_quarantine_from_receipt(self) -> None:
        rows = [
            {
                "action": "pipeline_quarantine",
                "evidence": {"quarantined": True},
                "to_state": "QUARANTINED",
            }
        ]
        self.assertEqual(infer_state_from_receipts(rows), PipelinePRState.QUARANTINED.value)

    def test_report_shape(self) -> None:
        report = state_machine_report([])
        self.assertEqual(report["current_state"], PipelinePRState.UNKNOWN.value)


if __name__ == "__main__":
    unittest.main()
