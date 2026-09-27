"""Unit tests for PR #186 run receipt deepen."""

from __future__ import annotations

import unittest

from thinkbox import kilo_pr186_think_job_run_receipt_deepen as pr186
from thinkbox.think_job_run_receipt_deepen.cassette import replay_cassette
from thinkbox.think_job_run_receipt_deepen.f185_pairing import pairing_ok
from thinkbox.think_job_run_receipt_deepen.receipt_schema import validate_receipt_shape


class TestThinkJobRunReceiptDeepen(unittest.TestCase):
    def test_features_manifest(self) -> None:
        ok, violations = pr186.validate_features_manifest()
        self.assertTrue(ok, violations)

    def test_receipt_shape(self) -> None:
        self.assertTrue(
            validate_receipt_shape(
                {"receipt_id": "r", "session_id": "s", "experiment_id": "e"},
            ),
        )

    def test_cassette(self) -> None:
        tape = replay_cassette("receipt_deepen_flow.json")
        self.assertEqual(tape["step_count"], 2)

    def test_f185_pairing(self) -> None:
        self.assertTrue(pairing_ok())


if __name__ == "__main__":
    unittest.main()
