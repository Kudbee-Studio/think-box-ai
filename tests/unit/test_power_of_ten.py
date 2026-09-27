"""Tests for the JPL Power of 10 auditor, plus the repo-wide ratchet."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from thinkbox.power_of_ten import (
    MAX_FUNCTION_LINES,
    RULE_MAP,
    audit_source,
    audit_tree,
    baseline_from,
    load_baseline,
    ratchet,
    write_baseline,
)

REPO = Path(__file__).resolve().parents[2]
BASELINE = REPO / "data" / "thinkboxmd" / "artifacts" / "power_of_ten_baseline.json"


def _rules(source: str) -> list[str]:
    return sorted(f.rule for f in audit_source(textwrap.dedent(source), "toy.py"))


class TestRecursion(unittest.TestCase):
    def test_direct_recursion_flagged(self) -> None:
        self.assertEqual(_rules("def f(n):\n    return f(n - 1) if n else 0\n"), ["P1"])

    def test_method_self_recursion_flagged(self) -> None:
        src = """
        class A:
            def walk(self, x):
                return self.walk(x)
        """
        self.assertEqual(_rules(src), ["P1"])

    def test_calling_a_different_objects_same_named_method_is_not_recursion(self) -> None:
        src = """
        class A:
            def close(self):
                self.conn.close()
        """
        self.assertEqual(_rules(src), [])


class TestUnboundedLoops(unittest.TestCase):
    def test_while_true_without_exit_flagged(self) -> None:
        self.assertEqual(_rules("def f():\n    while True:\n        tick()\n"), ["P2"])

    def test_while_true_with_break_return_or_raise_ok(self) -> None:
        for exit_stmt in ("break", "return 1", "raise StopIteration"):
            src = f"def f():\n    while True:\n        if done():\n            {exit_stmt}\n"
            self.assertEqual(_rules(src), [], exit_stmt)

    def test_break_of_inner_loop_does_not_bound_outer(self) -> None:
        src = """
        def f(xs):
            while True:
                for x in xs:
                    break
        """
        self.assertEqual(_rules(src), ["P2"])

    def test_return_in_nested_function_does_not_bound_loop(self) -> None:
        src = """
        def f():
            while True:
                def g():
                    return 1
        """
        self.assertEqual(_rules(src), ["P2"])

    def test_conditional_while_not_flagged(self) -> None:
        self.assertEqual(_rules("def f(n):\n    while n > 0:\n        n -= 1\n"), [])


class TestFunctionLength(unittest.TestCase):
    def test_boundary(self) -> None:
        body = "    x = 1\n" * (MAX_FUNCTION_LINES - 1)
        self.assertEqual(_rules("def ok():\n" + body), [])
        self.assertEqual(_rules("def long():\n" + body + "    x = 1\n"), ["P4"])


class TestSwallowedExceptions(unittest.TestCase):
    def test_bare_except_flagged_even_if_handled(self) -> None:
        self.assertEqual(_rules("try:\n    f()\nexcept:\n    log()\n"), ["P7"])

    def test_silent_broad_except_flagged(self) -> None:
        for handler in ("except Exception:", "except BaseException:", "except (ValueError, Exception):"):
            for body in ("pass", "continue", "..."):
                src = f"for _ in x:\n    try:\n        f()\n    {handler}\n        {body}\n"
                self.assertEqual(_rules(src), ["P7"], f"{handler} {body}")

    def test_handled_or_specific_except_ok(self) -> None:
        self.assertEqual(_rules("try:\n    f()\nexcept Exception:\n    log()\n    raise\n"), [])
        self.assertEqual(_rules("try:\n    f()\nexcept KeyError:\n    pass\n"), [])


class TestReportShape(unittest.TestCase):
    def test_unparseable_file_is_a_finding_not_a_crash(self) -> None:
        self.assertEqual(_rules("def (:\n"), ["PARSE"])

    def test_key_is_line_independent(self) -> None:
        a = audit_source("def f():\n    return f()\n", "m.py")[0]
        b = audit_source("\n\n\ndef f():\n    return f()\n", "m.py")[0]
        self.assertNotEqual(a.lineno, b.lineno)
        self.assertEqual(a.key, b.key)

    def test_every_jpl_rule_is_mapped(self) -> None:
        self.assertEqual(sorted(RULE_MAP, key=int), [str(i) for i in range(1, 11)])


class TestRatchet(unittest.TestCase):
    def test_new_violation_fails_and_fix_is_reported(self) -> None:
        old = audit_source("def f():\n    return f()\n", "m.py")
        base = baseline_from(old)
        self.assertTrue(ratchet(old, base)["passed"])

        worse = old + audit_source("def g():\n    return g()\n", "m.py")
        result = ratchet(worse, base)
        self.assertFalse(result["passed"])
        self.assertEqual([f["qualname"] for f in result["new"]], ["g"])

        fixed = ratchet([], base)
        self.assertTrue(fixed["passed"])
        self.assertEqual(fixed["fixed"], {"P1|m.py|f": 1})

    def test_second_violation_in_same_function_is_new(self) -> None:
        one = audit_source("try:\n    f()\nexcept:\n    pass\n", "m.py")
        two = audit_source("try:\n    f()\nexcept:\n    pass\ntry:\n    g()\nexcept:\n    pass\n", "m.py")
        self.assertFalse(ratchet(two, baseline_from(one))["passed"])


class TestMutationSurvivorsKilled(unittest.TestCase):
    """Gaps found by running scripts/mutation_test.py on this auditor."""

    def test_fixed_counts_only_keys_that_went_down(self) -> None:
        f = audit_source("def f():\n    return f()\n", "m.py")
        g = audit_source("def g():\n    return g()\n", "m.py")
        base = baseline_from(f + f + g)
        self.assertEqual(ratchet(f + g, base)["fixed"], {"P1|m.py|f": 1})

    def test_parse_finding_carries_the_error_line(self) -> None:
        self.assertEqual(audit_source("x = 1\ndef (:\n", "m.py")[0].lineno, 2)

    def test_findings_are_immutable(self) -> None:
        f = audit_source("def f():\n    return f()\n", "m.py")[0]
        with self.assertRaises(AttributeError):
            f.rule = "P2"  # type: ignore[misc]

    def test_tree_skips_pycache_and_baseline_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pkg" / "__pycache__").mkdir(parents=True)
            (root / "pkg" / "a.py").write_text("def f():\n    return f()\n", encoding="utf-8")
            (root / "pkg" / "__pycache__" / "b.py").write_text("def g():\n    return g()\n", encoding="utf-8")
            findings = audit_tree(root, ["pkg"])
            self.assertEqual([f.path for f in findings], ["pkg/a.py"])

            out = root / "new" / "nested" / "baseline.json"
            write_baseline(out, findings)
            self.assertEqual(load_baseline(out), {"P1|pkg/a.py|f": 1})
            write_baseline(out, findings)  # rewriting an existing baseline works


class TestRepoRatchet(unittest.TestCase):
    """No new Power of 10 violations in thinkbox/, core/ or backend/."""

    def test_no_new_violations(self) -> None:
        findings = audit_tree(REPO, ("thinkbox", "core", "backend"))
        result = ratchet(findings, load_baseline(BASELINE))
        msg = "\n".join(f"{f['rule']} {f['path']}:{f['lineno']} {f['qualname']}: {f['detail']}"
                        for f in result["new"])
        self.assertTrue(result["passed"], "new Power of 10 violations:\n" + msg)

    def test_auditor_passes_its_own_audit(self) -> None:
        path = REPO / "thinkbox" / "power_of_ten.py"
        self.assertEqual(audit_source(path.read_text(encoding="utf-8"), "power_of_ten.py"), [])


if __name__ == "__main__":
    unittest.main()
