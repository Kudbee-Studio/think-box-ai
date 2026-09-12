"""Unit tests for thinkbox/disruptor.py — disruptor pass framework."""

import unittest

from thinkbox.disruptor import DisruptorPass, DisruptorSuite


def _pass(name: str = "p1", category: str = "token", should_pass=lambda o: True) -> DisruptorPass:
    return DisruptorPass(
        name=name,
        category=category,
        description="fake pass",
        setup=lambda ctx: ctx.setdefault("setup_count", 0) or ctx.update(setup_count=ctx["setup_count"] + 1),
        attack=lambda ctx: {"saw": ctx.get("setup_count", 0)},
        should_pass=should_pass,
    )


class TestDisruptorSuite(unittest.TestCase):
    def test_add_and_len(self):
        suite = DisruptorSuite()
        suite.add(_pass())
        suite.add_many([_pass("a"), _pass("b")])
        self.assertEqual(len(suite), 3)

    def test_run_all_executes_in_order(self):
        suite = DisruptorSuite()
        suite.add_many([_pass(f"p{i}") for i in range(3)])
        results = suite.run_all({})
        self.assertEqual([r.name for r in results], ["p0", "p1", "p2"])
        self.assertEqual(len(results), 3)

    def test_setup_runs_before_attack(self):
        suite = DisruptorSuite()
        suite.add(_pass())
        results = suite.run_all({})
        self.assertEqual(results[0].outcome, {"saw": 1})

    def test_should_pass_evaluated(self):
        suite = DisruptorSuite()
        suite.add(_pass(should_pass=lambda o: o.get("saw") == 1))
        results = suite.run_all({})
        self.assertTrue(results[0].passed)

    def test_failing_predicate(self):
        suite = DisruptorSuite()
        suite.add(_pass(should_pass=lambda o: False))
        results = suite.run_all({})
        self.assertFalse(results[0].passed)

    def test_result_carries_metadata(self):
        suite = DisruptorSuite(name="unit-suite")
        suite.add(_pass(name="abc", category="mesh"))
        results = suite.run_all({})
        r = results[0]
        self.assertEqual(r.name, "abc")
        self.assertEqual(r.category, "mesh")
        self.assertTrue(r.timestamp)

    def test_passes_property_returns_copy(self):
        suite = DisruptorSuite()
        suite.add(_pass())
        snapshot = suite.passes
        snapshot.append(_pass("extra"))
        self.assertEqual(len(suite), 1)


if __name__ == "__main__":
    unittest.main()