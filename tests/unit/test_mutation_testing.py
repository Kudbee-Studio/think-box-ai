"""Tests for the mutation-testing harness, on a throwaway package whose
test gaps are known in advance."""

from __future__ import annotations

import ast
import tempfile
import textwrap
import unittest
from pathlib import Path

from thinkbox.mutation_testing import (
    MutationCampaignError,
    apply_mutant,
    enumerate_mutants,
    run_campaign,
)

TOY_SOURCE = textwrap.dedent('''
    def is_adult(age):
        return age >= 18


    def total(a, b):
        return a + b


    def both(x, y):
        return x and y
''')

# Deliberate gap: no test at age == 18, so ">=" -> ">" must survive.
TOY_TESTS = textwrap.dedent('''
    import unittest
    from toypkg.calc import both, is_adult, total

    class T(unittest.TestCase):
        def test_adult(self):
            self.assertTrue(is_adult(30))
            self.assertFalse(is_adult(10))

        def test_total(self):
            self.assertEqual(total(2, 3), 5)

        def test_both(self):
            self.assertTrue(both(True, True))
            self.assertFalse(both(True, False))
''')

LOOP_SOURCE = textwrap.dedent('''
    def countdown(n):
        while n > 0:
            n = n - 1
        return n
''')

LOOP_TESTS = textwrap.dedent('''
    import unittest
    from toypkg.calc import countdown

    class T(unittest.TestCase):
        def test_countdown(self):
            self.assertEqual(countdown(3), 0)
''')


def _make_pkg(root: Path, source: str, tests: str) -> None:
    (root / "toypkg").mkdir()
    (root / "toypkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "toypkg" / "calc.py").write_text(source, encoding="utf-8")
    (root / "toytests").mkdir()
    (root / "toytests" / "__init__.py").write_text("", encoding="utf-8")
    (root / "toytests" / "test_calc.py").write_text(tests, encoding="utf-8")


class TestEnumerateAndApply(unittest.TestCase):
    def test_finds_each_mutation_kind(self) -> None:
        kinds = sorted(m.kind for m in enumerate_mutants(TOY_SOURCE))
        self.assertEqual(kinds, ["arithmetic", "boolean", "compare"])

    def test_enumeration_is_deterministic(self) -> None:
        self.assertEqual(enumerate_mutants(TOY_SOURCE), enumerate_mutants(TOY_SOURCE))

    def test_apply_changes_exactly_one_site(self) -> None:
        for m in enumerate_mutants(TOY_SOURCE):
            mutated = apply_mutant(TOY_SOURCE, m)
            ast.parse(mutated)  # still valid Python
            self.assertNotEqual(ast.dump(ast.parse(mutated)), ast.dump(ast.parse(TOY_SOURCE)))

    def test_compare_boundary_swap(self) -> None:
        m = next(m for m in enumerate_mutants(TOY_SOURCE) if m.kind == "compare")
        self.assertEqual((m.original, m.replacement), (">=", ">"))
        self.assertIn("age > 18", apply_mutant(TOY_SOURCE, m))

    def test_negation_and_constant_mutants(self) -> None:
        src = "def f(x):\n    flag = True\n    return not x\n"
        mutants = {m.kind: m for m in enumerate_mutants(src)}
        self.assertIn("return x", apply_mutant(src, mutants["negation"]))
        self.assertIn("flag = False", apply_mutant(src, mutants["constant"]))

    def test_unknown_mutant_id_fails_closed(self) -> None:
        bogus = enumerate_mutants(TOY_SOURCE)[0].__class__("m9999", 0, 0, "compare", "", "")
        with self.assertRaises(MutationCampaignError):
            apply_mutant(TOY_SOURCE, bogus)


class TestCampaign(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_known_gap_survives_and_covered_sites_are_killed(self) -> None:
        _make_pkg(self.root, TOY_SOURCE, TOY_TESTS)
        report = run_campaign(
            self.root / "toypkg" / "calc.py", "toypkg.calc", "toytests.test_calc", self.root,
            timeout=30,
        )
        self.assertEqual(report["total"], 3)
        self.assertEqual(report["killed"], 2)
        self.assertEqual(report["survived"], 1)
        survivor = report["survivors"][0]
        self.assertEqual((survivor["original"], survivor["replacement"]), (">=", ">"))
        self.assertEqual(survivor["line"], "return age >= 18")
        self.assertAlmostEqual(report["score"], 2 / 3, places=3)
        self.assertEqual(len(report["module_sha256"]), 64)

    def test_infinite_loop_mutant_counts_as_killed_by_timeout(self) -> None:
        _make_pkg(self.root, LOOP_SOURCE, LOOP_TESTS)
        report = run_campaign(
            self.root / "toypkg" / "calc.py", "toypkg.calc", "toytests.test_calc", self.root,
            timeout=3,
        )
        # "n - 1" -> "n + 1" never terminates for n > 0.
        self.assertGreaterEqual(report["killed_by_timeout"], 1)
        self.assertEqual(report["survived"], 0)

    def test_red_baseline_refuses_to_score(self) -> None:
        broken = TOY_TESTS.replace("assertEqual(total(2, 3), 5)", "assertEqual(total(2, 3), 6)")
        _make_pkg(self.root, TOY_SOURCE, broken)
        with self.assertRaises(MutationCampaignError) as ctx:
            run_campaign(
                self.root / "toypkg" / "calc.py", "toypkg.calc", "toytests.test_calc", self.root,
                timeout=30,
            )
        self.assertIn("baseline", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
