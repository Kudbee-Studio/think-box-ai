"""Every KILO gate is evaluated once per call (thinkbox/kilo_eval_scope.py).

Before: one spine_contract_summary() executed 376,591 gate functions for 176 distinct ones (evaluate_env_matrix alone
54,426 times) and took 120 to 200 s, so every spine test hit its timeout. After: 319 executions, about 0.6 s.
"""

from __future__ import annotations

import ast
import cProfile
import collections
import importlib
import re
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
GATE = re.compile(r"^(hermetic_.*_check|evaluate_.*|.*_contract_summary|.*_gate_closed)$")


def _gate_functions() -> list[tuple[Path, ast.FunctionDef]]:
    found = []
    for path in sorted((ROOT / "thinkbox").glob("kilo_*.py")):
        if path.name == "kilo_eval_scope.py":
            continue
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.FunctionDef) and GATE.match(node.name):
                found.append((path, node))
    return found


class TestEveryGateIsEvaluatedOnce(unittest.TestCase):
    def test_every_gate_function_is_decorated(self) -> None:
        # A gate added without @evaluated_once would bring the exponential re-evaluation back.
        missing = [
            f"{path.name}:{node.name}"
            for path, node in _gate_functions()
            if "evaluated_once" not in {getattr(d, "id", getattr(d, "attr", None)) for d in node.decorator_list}
        ]
        self.assertEqual(missing, [], f"{len(missing)} gate functions are not @evaluated_once")

    def test_a_spine_summary_runs_each_gate_a_bounded_number_of_times(self) -> None:
        from thinkbox.kilo_live_proof_readiness import spine_contract_summary

        profile = cProfile.Profile()
        profile.enable()
        spine_contract_summary(fast=True)
        profile.disable()
        runs: collections.Counter[tuple[str, str]] = collections.Counter()
        for entry in profile.getstats():
            code = entry.code
            filename = getattr(code, "co_filename", "")
            if "/thinkbox/kilo_" in filename.replace("\\", "/") and GATE.match(code.co_name):
                runs[(Path(filename).name, code.co_name)] += entry.callcount
        (worst_gate, worst), total = runs.most_common(1)[0], sum(runs.values())
        self.assertGreaterEqual(len(runs), 150, "the profile should have seen the whole chain")
        self.assertLessEqual(worst, 16, f"{worst_gate} ran {worst} times in one summary (was 54,426 before)")
        self.assertLessEqual(total, 800, f"{total} gate executions in one summary (was 376,591 before)")


class TestMemoizedResultsEqualDirectEvaluation(unittest.TestCase):
    """The early gates, evaluated through the cache and directly (the cache disabled), give the same summary."""

    GATES = (
        ("kilo_env_matrix", "env_matrix_contract_summary"),
        ("kilo_substrate_checklist", "substrate_checklist_contract_summary"),
        ("kilo_governance_evidence", "governance_evidence_contract_summary"),
        ("kilo_mercury_hermetic", "mercury_hermetic_contract_summary"),
        ("kilo_swarm_instrumentation", "swarm_instrumentation_contract_summary"),
        ("kilo_proof_schema", "proof_schema_contract_summary"),
        ("kilo_dashboard_slots", "dashboard_slots_contract_summary"),
        ("kilo_live_proof_exec", "live_proof_exec_contract_summary"),
    )

    def test_summaries_match(self) -> None:
        for module_name, function_name in self.GATES:
            summary = getattr(importlib.import_module(f"thinkbox.{module_name}"), function_name)
            cached = summary()
            with mock.patch("thinkbox.kilo_eval_scope._key", side_effect=TypeError):  # every call is evaluated directly
                direct = summary()
            self.assertEqual(cached, direct, f"{function_name}: the cached summary differs from direct evaluation")


if __name__ == "__main__":
    unittest.main()
