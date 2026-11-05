"""Tests for the Think Token learning-benefit evaluation harness (hermetic)."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from thinkbox.think_token_eval import (
    HermeticAgentProvider,
    TrialResult,
    _fisher_exact,
    _LEARNED_ARTIFACT,
    _NAIVE_ARTIFACT,
    build_tool_surface,
    cohens_h,
    evaluate_trials,
    held_out_goals,
    load_accepted_tokens,
    run_control_evaluation,
    run_evaluation,
    run_trial,
    token_context_block,
    verify_artifact,
)


class TestFisherExact(unittest.TestCase):
    def test_all_success_one_arm(self):
        # 5/5 vs 0/5 -> extremely unlikely under null
        p = _fisher_exact([[5, 0], [0, 5]])
        self.assertLess(p, 0.05)

    def test_identical_arms(self):
        p = _fisher_exact([[3, 2], [3, 2]])
        self.assertGreaterEqual(p, 0.05)

    def test_no_difference(self):
        p = _fisher_exact([[2, 3], [2, 3]])
        self.assertGreaterEqual(p, 0.05)


class TestCohensH(unittest.TestCase):
    def test_no_difference(self):
        self.assertAlmostEqual(cohens_h(0.5, 0.5), 0.0, places=6)

    def test_full_difference(self):
        self.assertAlmostEqual(abs(cohens_h(1.0, 0.0)), 3.1415, places=3)


class TestHeldOutGoals(unittest.TestCase):
    def test_five_goals_same_family(self):
        gs = held_out_goals()
        self.assertEqual(len(gs), 5)
        for g in gs:
            self.assertEqual(g["family"], "rest_api")
            self.assertTrue(g["goal_id"].startswith("heldout_"))
            self.assertIn("parameterized", g["must_contain"])

    def test_independent_instances(self):
        ids = [g["goal_id"] for g in held_out_goals()]
        self.assertEqual(len(set(ids)), len(ids))
        # None of the held-out ids may equal the training task ids.
        for tid in ids:
            self.assertNotIn("task_001", tid)
            self.assertNotIn("task_002", tid)


class TestVerifyArtifact(unittest.TestCase):
    def test_naive_fstring_fails(self):
        goal = held_out_goals()[0]
        naive = (
            "from pydantic import BaseModel\n"
            "import sqlite3\n"
            "conn = sqlite3.connect('store.db')\n"
            "# search endpoint: naive implementation\n"
            "def search(term):\n"
            "    # parameterized is NOT used here\n"
            "    cur.execute(f\"SELECT * FROM items WHERE name LIKE '%{term}%'\")\n"
        )
        ok, reason = verify_artifact(goal, naive)
        self.assertFalse(ok, reason)
        self.assertIn("injection", reason.lower())

    def test_parameterized_passes(self):
        goal = held_out_goals()[0]
        learned = (
            "from pydantic import BaseModel\n"
            "import sqlite3\n"
            "conn = sqlite3.connect('store.db')\n"
            "# search endpoint: parameterized queries prevent SQL injection\n"
            "def search(term):\n"
            "    cur.execute('SELECT * FROM items WHERE name LIKE ?', (term,))\n"
        )
        ok, reason = verify_artifact(goal, learned)
        self.assertTrue(ok), reason

    def test_empty_fails(self):
        ok, reason = verify_artifact(held_out_goals()[0], "")
        self.assertFalse(ok)

    def test_learned_constant_passes(self):
        goal = held_out_goals()[0]
        ok, reason = verify_artifact(goal, _LEARNED_ARTIFACT)
        self.assertTrue(ok), reason

    def test_naive_constant_fails(self):
        goal = held_out_goals()[0]
        ok, reason = verify_artifact(goal, _NAIVE_ARTIFACT)
        self.assertFalse(ok), reason


class TestTokenLoading(unittest.TestCase):
    def test_loads_accepted_tokens_from_learned_db(self):
        with mock.patch(
            "thinkbox.think_token_eval.DEFAULT_TOKEN_DB",
            Path("learned.db"),
        ):
            tokens = load_accepted_tokens()
        self.assertGreater(len(tokens), 0)
        self.assertTrue(all(t.accepted for t in tokens))
        self.assertTrue(all(t.content.strip() for t in tokens))

    def test_token_context_block_renders(self):
        block = token_context_block(load_accepted_tokens())
        self.assertIn("Prior accepted Think Tokens", block)


class TestTrialRunner(unittest.TestCase):
    def test_with_tokens_succeeds_without_fails(self):
        goal = held_out_goals()[0]
        tokens = load_accepted_tokens()
        w = run_trial(goal, HermeticAgentProvider(honor_tokens=True), tokens, "with_tokens")
        wo = run_trial(goal, HermeticAgentProvider(honor_tokens=False), tokens, "without_tokens")
        self.assertTrue(w.success)
        self.assertFalse(wo.success)
        self.assertEqual(w.arm, "with_tokens")
        self.assertEqual(wo.arm, "without_tokens")
        self.assertEqual(w.model_calls, 1)
        self.assertEqual(w.tool_calls, 1)
        self.assertTrue(w.reused_token)
        self.assertFalse(wo.reused_token)

    def test_neutral_provider_ignores_tokens(self):
        goal = held_out_goals()[0]
        tokens = load_accepted_tokens()
        w = run_trial(goal, HermeticAgentProvider(honor_tokens=False), tokens, "with_tokens")
        wo = run_trial(goal, HermeticAgentProvider(honor_tokens=False), tokens, "without_tokens")
        self.assertEqual(w.success, wo.success)
        self.assertEqual(w.output, wo.output)


class TestEvaluateTrials(unittest.TestCase):
    def test_detects_full_separation(self):
        n = 5
        w = [TrialResult(f"w{i}", "with_tokens", "", True, 1, 1, True, "") for i in range(n)]
        wo = [TrialResult(f"wo{i}", "without_tokens", "", False, 1, 1, False, "") for i in range(n)]
        stats = evaluate_trials(w, wo)
        self.assertEqual(stats["with_tokens"]["rate"], 1.0)
        self.assertEqual(stats["without_tokens"]["rate"], 0.0)
        self.assertEqual(stats["delta_rate"], 1.0)
        self.assertLess(stats["fisher_exact_one_sided_p"], 0.05)


class TestRunEvaluation(unittest.TestCase):
    def test_full_evaluation_runs(self):
        stats = run_evaluation()
        self.assertIn("verdict", stats)
        self.assertIn("delta_rate", stats)
        self.assertGreater(len(stats["tokens_loaded"]), 0)
        self.assertEqual(len(stats["goals"]), 5)
        self.assertEqual(len(stats["trials"]), 10)

    def test_control_evaluation_is_null(self):
        control = run_control_evaluation()
        self.assertEqual(control["verdict"], "NO_MEASURABLE_IMPROVEMENT")
        self.assertEqual(control["delta_rate"], 0.0)


class TestToolSurface(unittest.TestCase):
    def test_write_and_read(self):
        from thinkbox.think_token_eval import _InMemoryFilesystem
        fs = _InMemoryFilesystem()
        tools = build_tool_surface(fs)
        r = tools["file_write"]("a.py", "print('hi')")
        self.assertTrue(r["success"])
        self.assertEqual(tools["file_read"]("a.py")["content"], "print('hi')")

    def test_read_missing(self):
        from thinkbox.think_token_eval import _InMemoryFilesystem
        fs = _InMemoryFilesystem()
        tools = build_tool_surface(fs)
        self.assertFalse(tools["file_read"]("missing.py")["success"])


if __name__ == "__main__":
    unittest.main()