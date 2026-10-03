"""A KILO gate evaluates what is on disk now, not what an earlier call in the process saw.

kilo_hermetic_gate_memo kept one process-wide dict keyed by gate id and environment, "unless cleared", and only one test
file cleared it. A gate evaluated twice in a process, with the repository changed in between, answered the second call
from the first. Gate results are now shared only inside one outermost call (kilo_eval_scope).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from thinkbox import kilo_pr169_combined_post168_lane as pr169

ROOT = Path(__file__).resolve().parents[1].parent


class TestNoStaleGateResults(unittest.TestCase):
    def test_a_gate_sees_the_repository_change_made_between_two_calls(self) -> None:
        env = pr169.minimal_pr169_combined_environ()
        first = pr169.hermetic_pr169_combined_post168_lane_check(env)
        self.assertTrue(first.ok, msg=first.violations)
        with tempfile.TemporaryDirectory() as empty, mock.patch.object(pr169, "REPO_ROOT", Path(empty)):
            second = pr169.hermetic_pr169_combined_post168_lane_check(env)
        self.assertFalse(second.ok, "the checklist and audit files are gone; a cached verdict hid that")
        self.assertIn("checklist", {v.code for v in second.violations})
        third = pr169.hermetic_pr169_combined_post168_lane_check(env)
        self.assertTrue(third.ok, "the original repository is back")

    def test_no_gate_module_keeps_a_process_wide_result_cache(self) -> None:
        offenders = []
        for path in sorted((ROOT / "thinkbox").glob("kilo_*.py")):
            text = path.read_text(encoding="utf-8")
            if "memoized_hermetic_check" in text or "_MEMO:" in text or "_MEMO =" in text:
                offenders.append(path.name)
        self.assertEqual(offenders, [])
        self.assertFalse((ROOT / "thinkbox" / "kilo_hermetic_gate_memo.py").exists())


if __name__ == "__main__":
    unittest.main()
