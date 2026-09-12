"""Unit tests for thinkbox/factcards.py — coverage scheduler."""

import unittest

from thinkbox.factcards import FactCardRegistry


class TestFactCardRegistry(unittest.TestCase):
    def test_add_and_get(self):
        registry = FactCardRegistry()
        card = registry.add("fc_1", "geo", "What is the capital of France?", "Paris")
        self.assertEqual(registry.get("fc_1"), card)
        self.assertEqual(len(registry.all()), 1)

    def test_record_use(self):
        registry = FactCardRegistry()
        registry.add("fc_1", "geo", "q", "Paris")
        self.assertTrue(registry.record_use("fc_1"))
        self.assertEqual(registry.get("fc_1").uses, 1)

    def test_record_use_missing(self):
        registry = FactCardRegistry()
        self.assertFalse(registry.record_use("missing"))

    def test_next_batch_least_used_first(self):
        registry = FactCardRegistry()
        registry.add("fc_1", "a", "q1", "t1")
        registry.add("fc_2", "b", "q2", "t2")
        registry.add("fc_3", "c", "q3", "t3")
        registry.record_use("fc_1", times=5)
        registry.record_use("fc_2", times=2)
        batch = registry.next_batch(2)
        self.assertEqual([c.card_id for c in batch], ["fc_3", "fc_2"])

    def test_next_batch_bounded(self):
        registry = FactCardRegistry()
        registry.add("fc_1", "a", "q", "t")
        self.assertEqual(len(registry.next_batch(10)), 1)

    def test_coverage(self):
        registry = FactCardRegistry()
        registry.add("fc_1", "geo", "q", "t")
        registry.record_use("fc_1")
        self.assertEqual(registry.coverage(), {"geo": 1})

    def test_from_mapping(self):
        registry = FactCardRegistry.from_mapping({"What is 2+2?": "fact_arith: 2+2=4"})
        card = registry.all()[0]
        self.assertEqual(card.concept, "fact_arith")
        self.assertEqual(card.text, "2+2=4")
        self.assertEqual(card.prompt, "What is 2+2?")


if __name__ == "__main__":
    unittest.main()