"""Unit tests for thinkbox/legendary.py — 10 legendary features."""

import time
import unittest
from thinkbox.legendary import (
    CausalReasoningEngine,
    TemporalMemory,
    AgentEvolution,
    QuantumSuperposition,
    MetaCognition,
    StigmergicSwarm,
    ZeroKnowledgeProof,
    AffectiveComputing,
    InterventionEngine,
    InfiniteContext,
)


class TestCausalReasoningEngine(unittest.TestCase):
    def test_record_and_query_causes(self):
        engine = CausalReasoningEngine()
        engine.record_link("cause_1", "effect_1", strength=0.9, confidence=0.8)
        engine.record_link("cause_2", "effect_1", strength=0.4, confidence=0.3)
        causes = engine.get_causes("effect_1")
        self.assertEqual(len(causes), 2)
        high = [c for c in causes if c.confidence >= 0.5]
        self.assertEqual(len(high), 1)

    def test_get_effects(self):
        engine = CausalReasoningEngine()
        engine.record_link("cause_1", "effect_1", strength=1.0, confidence=1.0)
        engine.record_link("cause_1", "effect_2", strength=0.5, confidence=0.5)
        effects = engine.get_effects("cause_1")
        self.assertEqual(len(effects), 2)

    def test_intervention(self):
        engine = CausalReasoningEngine()
        engine.record_link("action", "result", strength=0.8, confidence=0.9)
        outcome = engine.intervene("action", 42.0, observe_effect=lambda: 100.0)
        self.assertIn("baseline", outcome)
        self.assertIn("observed", outcome)
        self.assertIn("delta", outcome)

    def test_empty_engine(self):
        engine = CausalReasoningEngine()
        self.assertEqual(engine.get_causes("missing"), [])
        self.assertEqual(engine.get_effects("missing"), [])


class TestTemporalMemory(unittest.TestCase):
    def test_save_and_restore(self):
        mem = TemporalMemory()
        state = {"count": 1, "name": "alpha"}
        snap = mem.save(state, label="init")
        restored = mem.restore(snap.snapshot_id)
        self.assertEqual(restored, state)

    def test_undo(self):
        mem = TemporalMemory()
        mem.save({"x": 1})
        mem.save({"x": 2})
        undone = mem.undo({"x": 3})
        self.assertEqual(undone["x"], 2)

    def test_query_by_label(self):
        mem = TemporalMemory()
        mem.save({"step": 1}, label="start")
        mem.save({"step": 2}, label="middle")
        mem.save({"step": 3}, label="end")
        results = mem.query(label="middle")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].label, "middle")

    def test_empty_memory(self):
        mem = TemporalMemory()
        self.assertIsNone(mem.restore("missing"))
        self.assertEqual(mem.undo({"a": 1}), {"a": 1})


class TestAgentEvolution(unittest.TestCase):
    def test_initialize_and_evolve(self):
        evo = AgentEvolution(population_size=10, mutation_rate=0.5)
        seeds = ["x=1", "x=2", "x=3"]
        evo.initialize(seeds)
        self.assertEqual(len(evo._population), 3)

        def fitness_fn(code: str) -> float:
            try:
                return float(code.split("=")[1])
            except Exception:
                return 0.0

        population = evo.evolve(fitness_fn)
        self.assertGreater(len(population), 0)
        best = evo.best()
        self.assertIsNotNone(best)
        self.assertGreaterEqual(best.fitness, 0.0)

    def test_evaluate_updates_fitness(self):
        evo = AgentEvolution()
        evo.initialize(["code=0"])
        evo.evaluate("code=0", 5.0)
        best = evo.best()
        self.assertEqual(best.fitness, 5.0)


class TestQuantumSuperposition(unittest.TestCase):
    def test_add_and_collapse(self):
        qs = QuantumSuperposition(max_paths=4)
        qs.add_path({"result": "A"}, amplitude=1 + 0j)
        qs.add_path({"result": "B"}, amplitude=1 + 0j)
        result = qs.collapse(evaluator=lambda s: 1.0 if s.get("result") == "A" else 0.5)
        self.assertIn(result, [{"result": "A"}, {"result": "B"}])

    def test_measure_all(self):
        qs = QuantumSuperposition()
        qs.add_path({"id": 1})
        qs.add_path({"id": 2})
        all_paths = qs.measure_all()
        self.assertEqual(len(all_paths), 2)

    def test_empty_collapse(self):
        qs = QuantumSuperposition()
        self.assertIsNone(qs.collapse(lambda s: 1.0))


class TestMetaCognition(unittest.TestCase):
    def test_think_and_calibrate(self):
        mc = MetaCognition()
        t1 = mc.think("First thought", confidence=0.7, reasoning="Because")
        t2 = mc.think("Second thought", confidence=0.4, reasoning="Because")
        self.assertEqual(len(mc._traces), 2)
        stats = mc.calibrate()
        self.assertAlmostEqual(stats["mean_confidence"], 0.55, places=2)

    def test_reflection(self):
        mc = MetaCognition()
        for i in range(5):
            mc.think(f"Thought {i}", confidence=0.5)
        reflection = mc.reflect()
        self.assertIn("Meta-cognitive reflection", reflection)

    def test_empty_calibrate(self):
        mc = MetaCognition()
        stats = mc.calibrate()
        self.assertEqual(stats["mean_confidence"], 0.0)


class TestStigmergicSwarm(unittest.TestCase):
    def test_deposit_and_sense(self):
        swarm = StigmergicSwarm(decay_rate=0.0)
        swarm.deposit("loc_1", "agent_A", strength=1.0)
        swarm.deposit("loc_1", "agent_B", strength=0.5)
        trails = swarm.sense("loc_1")
        self.assertEqual(len(trails), 2)

    def test_strongest(self):
        swarm = StigmergicSwarm(decay_rate=0.0)
        swarm.deposit("loc_1", "agent_A", strength=0.3)
        swarm.deposit("loc_1", "agent_B", strength=0.8)
        strongest = swarm.strongest("loc_1")
        self.assertIsNotNone(strongest)
        self.assertEqual(strongest.agent_id, "agent_B")

    def test_decay(self):
        swarm = StigmergicSwarm(decay_rate=1.0)
        swarm.deposit("loc_1", "agent_A", strength=1.0)
        time.sleep(0.6)
        swarm.decay()
        remaining = swarm.sense("loc_1")
        self.assertTrue(all(t.strength < 0.5 for t in remaining))


class TestZeroKnowledgeProof(unittest.TestCase):
    def test_commit_and_verify(self):
        zk = ZeroKnowledgeProof("prover_1")
        commitment = zk.commit("secret_value")
        self.assertTrue(zk.verify(commitment))

    def test_prove_success(self):
        zk = ZeroKnowledgeProof("prover_1")
        commitment = zk.commit("my_secret")
        self.assertTrue(zk.prove("my_secret", commitment))

    def test_prove_failure_wrong_secret(self):
        zk = ZeroKnowledgeProof("prover_1")
        commitment = zk.commit("my_secret")
        self.assertFalse(zk.prove("wrong_secret", commitment))

    def test_verify_missing_commitment(self):
        zk = ZeroKnowledgeProof("prover_1")
        self.assertFalse(zk.verify("missing"))


class TestAffectiveComputing(unittest.TestCase):
    def test_success_emotion(self):
        ac = AffectiveComputing()
        state = ac.update("Task completed successfully", intensity=1.0)
        self.assertGreater(state.valence, 0.0)
        self.assertIn("joy", state.emotions)

    def test_failure_emotion(self):
        ac = AffectiveComputing()
        state = ac.update("Task failed with error", intensity=0.8)
        self.assertLess(state.valence, 0.0)
        self.assertIn("frustration", state.emotions)

    def test_neutral_emotion(self):
        ac = AffectiveComputing()
        state = ac.update("Neutral event", intensity=0.5)
        self.assertEqual(state.valence, 0.0)

    def test_current_state(self):
        ac = AffectiveComputing()
        self.assertIsNone(ac.current_state())
        ac.update("Something happened")
        self.assertIsNotNone(ac.current_state())


class TestInterventionEngine(unittest.TestCase):
    def test_propose_and_test(self):
        engine = InterventionEngine()
        hyp = engine.propose("increase_workers", "throughput_increases", confidence=0.7)
        result = engine.test(hyp.hypothesis_id, "throughput_increases")
        self.assertTrue(result["success"])
        self.assertGreater(result["updated_confidence"], 0.7)

    def test_test_failure_decreases_confidence(self):
        engine = InterventionEngine()
        hyp = engine.propose("increase_workers", "throughput_increases", confidence=0.7)
        result = engine.test(hyp.hypothesis_id, "throughput_decreases")
        self.assertFalse(result["success"])
        self.assertLess(result["updated_confidence"], 0.7)

    def test_missing_hypothesis(self):
        engine = InterventionEngine()
        result = engine.test("missing", "outcome")
        self.assertIn("error", result)


class TestInfiniteContext(unittest.TestCase):
    def test_compress_short_text(self):
        ctx = InfiniteContext()
        chunk = ctx.compress("This is a test.")
        self.assertEqual(chunk.summary, "This is a test.")

    def test_compress_long_text(self):
        ctx = InfiniteContext()
        long_text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
        chunk = ctx.compress(long_text)
        self.assertIn("Sentence one", chunk.summary)
        self.assertLessEqual(chunk.token_count, chunk.original_length)

    def test_expand_retrieves_relevant(self):
        ctx = InfiniteContext()
        ctx.compress("Alpha beta gamma delta")
        ctx.compress("Epsilon zeta eta theta")
        result = ctx.expand("alpha beta", max_chunks=1)
        self.assertIn("Alpha", result)

    def test_expand_empty(self):
        ctx = InfiniteContext()
        result = ctx.expand("query")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
