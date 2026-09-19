"""Unit tests for thinkbox.intelligence — Knowledge Graph, Self-Healing, Reputation, Security."""

from __future__ import annotations

import time
import unittest
from datetime import datetime, timezone

from thinkbox.intelligence import (
    ConceptEdge,
    ConceptNode,
    ConceptExtractor,
    GraphIndexer,
    SemanticSearch,
    KnowledgeDecay,
    MemoryConsolidation,
    AutoBugPatcher,
    RegressionDetector,
    SelfOptimizer,
    CircuitBreaker,
    RecoveryOrchestrator,
    ReputationScore,
    ProofOfWork,
    SybilResistance,
    TrustNetwork,
    ReputationStaking,
    ModelAggregation,
    GradientCompression,
    DifferentialPrivacy,
    ByzantineTolerance,
    PersonalizationLayer,
    KyberKeyExchange,
    DilithiumSignatures,
    HybridHandshake,
    KeyRotationPolicy,
    ZeroKnowledgeProofs,
)


class TestConceptExtractor(unittest.TestCase):
    def test_extract_functions(self) -> None:
        text = "def foo(): pass\ndef bar(): pass"
        concepts = ConceptExtractor().extract(text)
        types = [c.concept_type for c in concepts]
        self.assertIn("function", types)

    def test_extract_classes(self) -> None:
        text = "class Foo:\n class Bar:"
        concepts = ConceptExtractor().extract(text)
        types = [c.concept_type for c in concepts]
        self.assertIn("class", types)

    def test_extract_no_duplicates(self) -> None:
        text = "def foo(): pass\ndef foo(): pass"
        concepts = ConceptExtractor().extract(text)
        names = [c.name for c in concepts]
        self.assertEqual(len(names), len(set(names)))

    def test_extract_empty(self) -> None:
        concepts = ConceptExtractor().extract("")
        self.assertEqual(len(concepts), 0)


class TestGraphIndexer(unittest.TestCase):
    def test_add_and_query(self) -> None:
        idx = GraphIndexer()
        node = ConceptNode("c1", "foo", "function")
        idx.add_concept(node)
        results = idx.query(name="foo")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].concept_id, "c1")

    def test_query_by_type(self) -> None:
        idx = GraphIndexer()
        idx.add_concept(ConceptNode("c1", "foo", "function"))
        idx.add_concept(ConceptNode("c2", "Bar", "class"))
        results = idx.query(concept_type="class")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Bar")

    def test_add_edge_and_neighbors(self) -> None:
        idx = GraphIndexer()
        idx.add_concept(ConceptNode("c1", "a", "function"))
        idx.add_concept(ConceptNode("c2", "b", "function"))
        idx.add_edge("c1", "c2", "calls")
        neighbors = idx.get_neighbors("c1")
        self.assertEqual(len(neighbors), 1)
        self.assertEqual(neighbors[0].concept_id, "c2")


class TestSemanticSearch(unittest.TestCase):
    def test_index_and_search(self) -> None:
        ss = SemanticSearch()
        ss.index("d1", "machine learning deep neural network")
        ss.index("d2", "cooking recipe food")
        results = ss.search("machine learning")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "d1")


class TestKnowledgeDecay(unittest.TestCase):
    def test_recent_has_high_relevance(self) -> None:
        kd = KnowledgeDecay(half_life_days=30)
        score = kd.relevance_score(
            (datetime.now(timezone.utc)).isoformat(), access_count=0
        )
        self.assertGreater(score, 0.5)

    def test_access_bonus(self) -> None:
        kd = KnowledgeDecay(half_life_days=30)
        old = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=10)).isoformat()
        score_0 = kd.relevance_score(old, access_count=0)
        score_5 = kd.relevance_score(old, access_count=5)
        self.assertGreater(score_5, score_0)


class TestMemoryConsolidation(unittest.TestCase):
    def test_consolidation(self) -> None:
        mc = MemoryConsolidation()
        mc.add_memory({"id": "m1", "category": "general"})
        mc.add_memory({"id": "m2", "category": "general"})
        consolidated = mc.consolidate()
        self.assertEqual(len(consolidated), 1)
        self.assertEqual(consolidated[0]["category"], "general")
        self.assertEqual(consolidated[0]["count"], 2)


class TestAutoBugPatcher(unittest.TestCase):
    def test_fix_syntax_error(self) -> None:
        patcher = AutoBugPatcher()
        patched = patcher.generate_patch(
            "SyntaxError: invalid syntax at line 2",
            "if True\n  pass\nprint('ok')",
        )
        self.assertIsNotNone(patched)
        self.assertIn(":", patched)

    def test_fix_name_error(self) -> None:
        patcher = AutoBugPatcher()
        patched = patcher.generate_patch(
            "NameError: name 'x' is not defined",
            "print(x)",
        )
        self.assertIsNotNone(patched)
        self.assertIn("x = None", patched)

    def test_fix_import_error(self) -> None:
        patcher = AutoBugPatcher()
        patched = patcher.generate_patch(
            "ImportError: No module named 'os'",
            "print(os.getcwd())",
        )
        self.assertIsNotNone(patched)
        self.assertIn("import os", patched)

    def test_unknown_error(self) -> None:
        patcher = AutoBugPatcher()
        patched = patcher.generate_patch("RuntimeError: something", "pass")
        self.assertIsNone(patched)


class TestRegressionDetector(unittest.TestCase):
    def test_detect_regression(self) -> None:
        rd = RegressionDetector(window_size=5)
        for i in range(5):
            rd.record("latency", 10.0 + i * 0.1)
        rd.record("latency", 50.0)
        result = rd.detect_regression("latency")
        self.assertIsNotNone(result)
        self.assertTrue(result["is_regression"])

    def test_no_regression_yet(self) -> None:
        rd = RegressionDetector(window_size=5)
        rd.record("latency", 10.0)
        result = rd.detect_regression("latency")
        self.assertIsNone(result)


class TestSelfOptimizer(unittest.TestCase):
    def test_optimize(self) -> None:
        opt = SelfOptimizer()
        opt.set_parameter("learning_rate", 0.5)
        result = opt.optimize("learning_rate", target=1.0)
        self.assertGreater(result["new_value"], result["previous"])
        self.assertEqual(result["parameter"], "learning_rate")


class TestCircuitBreaker(unittest.TestCase):
    def test_closes_on_success(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_success()
        self.assertEqual(cb.state, "closed")
        self.assertTrue(cb.can_execute())

    def test_opens_after_failures(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        self.assertEqual(cb.state, "open")
        self.assertFalse(cb.can_execute())

    def test_half_open_after_timeout(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        for _ in range(2):
            cb.record_failure()
        time.sleep(0.02)
        self.assertEqual(cb.state, "half-open")


class TestRecoveryOrchestrator(unittest.TestCase):
    def test_initiate_recovery(self) -> None:
        ro = RecoveryOrchestrator()
        ro.register_procedure("db_error", ["check_connection", "reconnect"])
        steps = ro.initiate_recovery("db_error")
        self.assertEqual(steps, ["check_connection", "reconnect"])
        self.assertEqual(ro.status, "recovering")

    def test_complete_recovery(self) -> None:
        ro = RecoveryOrchestrator()
        ro.initiate_recovery("db_error")
        ro.complete_recovery()
        self.assertEqual(ro.status, "healthy")

    def test_default_steps(self) -> None:
        ro = RecoveryOrchestrator()
        steps = ro.initiate_recovery("unknown")
        self.assertEqual(steps, ["restart_service"])


class TestReputationScore(unittest.TestCase):
    def test_update_and_get(self) -> None:
        rs = ReputationScore()
        rs.update("agent1", 0.5)
        self.assertAlmostEqual(rs.get_score("agent1"), 1.5)

    def test_clamp_zero(self) -> None:
        rs = ReputationScore()
        rs.update("agent1", -5.0)
        self.assertEqual(rs.get_score("agent1"), 0.0)

    def test_clamp_ten(self) -> None:
        rs = ReputationScore()
        rs.update("agent1", 20.0)
        self.assertEqual(rs.get_score("agent1"), 10.0)

    def test_default_score(self) -> None:
        rs = ReputationScore()
        self.assertEqual(rs.get_score("unknown"), 1.0)


class TestProofOfWork(unittest.TestCase):
    def test_generate_and_verify(self) -> None:
        challenge = ProofOfWork.generate_challenge()
        hash_result, nonce = ProofOfWork.solve(challenge, difficulty=2)
        self.assertTrue(ProofOfWork.verify(challenge, hash_result, nonce, difficulty=2))


class TestSybilResistance(unittest.TestCase):
    def test_register_and_verify(self) -> None:
        sr = SybilResistance()
        proof = "test-proof"
        self.assertTrue(sr.register_identity("agent1", proof))
        self.assertTrue(sr.verify_identity("agent1", proof))

    def test_duplicate_registration_fails(self) -> None:
        sr = SybilResistance()
        sr.register_identity("agent1", "proof1")
        self.assertFalse(sr.register_identity("agent1", "proof2"))

    def test_verify_unknown_agent(self) -> None:
        sr = SybilResistance()
        self.assertFalse(sr.verify_identity("unknown", "proof"))


class TestTrustNetwork(unittest.TestCase):
    def test_set_and_get_trust(self) -> None:
        tn = TrustNetwork()
        tn.set_trust("a", "b", 0.8)
        self.assertAlmostEqual(tn.get_trust("a", "b"), 0.8)
        self.assertEqual(tn.get_trust("a", "c"), 0.0)

    def test_get_trusted_neighbors(self) -> None:
        tn = TrustNetwork()
        tn.set_trust("a", "b", 0.8)
        tn.set_trust("a", "c", 0.3)
        neighbors = tn.get_trusted_neighbors("a", threshold=0.5)
        self.assertIn("b", neighbors)
        self.assertNotIn("c", neighbors)


class TestReputationStaking(unittest.TestCase):
    def test_stake_and_voting_power(self) -> None:
        rs = ReputationScore()
        rs.update("agent1", 2.0)
        staking = ReputationStaking(rs)
        power = staking.stake("agent1", 100)
        self.assertEqual(power, 300.0)
        self.assertAlmostEqual(staking.get_voting_power("agent1"), 300.0)


class TestModelAggregation(unittest.TestCase):
    def test_federated_average(self) -> None:
        updates = [
            {"w1": [1.0, 2.0], "w2": [3.0]},
            {"w1": [3.0, 4.0], "w2": [5.0]},
        ]
        result = ModelAggregation.federated_average(updates)
        self.assertAlmostEqual(result["w1"][0], 2.0)
        self.assertAlmostEqual(result["w1"][1], 3.0)
        self.assertAlmostEqual(result["w2"][0], 4.0)

    def test_federated_average_empty(self) -> None:
        self.assertIsNone(ModelAggregation.federated_average([]))


class TestGradientCompression(unittest.TestCase):
    def test_quantize(self) -> None:
        grad = [0.0, 0.5, 1.0]
        q = GradientCompression.quantize(grad, bits=2)
        self.assertEqual(len(q), 3)
        self.assertEqual(q[0], 0)
        self.assertEqual(q[2], 3)

    def test_quantize_empty(self) -> None:
        self.assertEqual(GradientCompression.quantize([]), [])

    def test_decompress(self) -> None:
        q = [0, 1, 3]
        d = GradientCompression.decompress(q, 0.0, 1.0, bits=2)
        self.assertAlmostEqual(d[0], 0.0)
        self.assertAlmostEqual(d[2], 1.0)


class TestDifferentialPrivacy(unittest.TestCase):
    def test_clip_gradient(self) -> None:
        grad = [3.0, 4.0]
        clipped = DifferentialPrivacy.clip_gradient(grad, max_norm=1.0)
        norm = sum(g ** 2 for g in clipped) ** 0.5
        self.assertLessEqual(norm, 1.0)


class TestByzantineTolerance(unittest.TestCase):
    def test_trimmed_mean(self) -> None:
        vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 100.0]
        result = ByzantineTolerance.trimmed_mean(vals, trim_ratio=0.1)
        self.assertLess(result, 10.0)

    def test_median_aggregate(self) -> None:
        updates = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
        result = ByzantineTolerance.median_aggregate(updates)
        self.assertAlmostEqual(result[0], 3.0)
        self.assertAlmostEqual(result[1], 4.0)


class TestPersonalizationLayer(unittest.TestCase):
    def test_get_base(self) -> None:
        base = {"lr": 0.01}
        layer = PersonalizationLayer(base)
        self.assertEqual(layer.get_base(), {"lr": 0.01})

    def test_personalize(self) -> None:
        layer = PersonalizationLayer({"lr": 0.01})
        result = layer.personalize("agent1", {"batch_size": 32})
        self.assertIn("lr", result)
        self.assertIn("batch_size", result)


class TestKyberKeyExchange(unittest.TestCase):
    def test_keypair(self) -> None:
        kx = KyberKeyExchange(security_level=64)
        pub, priv = kx.generate_keypair()
        self.assertEqual(len(pub), 64)
        self.assertEqual(len(priv), 64)


class TestDilithiumSignatures(unittest.TestCase):
    def test_sign_and_verify(self) -> None:
        d = DilithiumSignatures()
        pub, priv = d.generate_keypair()
        msg = b"hello"
        sig = d.sign(msg, priv)
        self.assertTrue(d.verify(msg, sig, priv))
        self.assertFalse(d.verify(b"other", sig, priv))


class TestHybridHandshake(unittest.TestCase):
    def test_key_material(self) -> None:
        hh = HybridHandshake()
        material = hh.generate_key_material()
        self.assertIn("kyber_public", material)
        self.assertIn("dilithium_public", material)
        self.assertIn("kyber_secret", material)
        self.assertIn("dilithium_secret", material)


class TestKeyRotationPolicy(unittest.TestCase):
    def test_generate_and_rotate(self) -> None:
        krp = KeyRotationPolicy(rotation_interval_hours=24)
        key = krp.generate_key("key1")
        self.assertIsNotNone(key)
        self.assertFalse(krp.should_rotate("key1"))


class TestZeroKnowledgeProofs(unittest.TestCase):
    def test_create_and_verify(self) -> None:
        proof = ZeroKnowledgeProofs.create_proof("secret", "challenge")
        self.assertTrue(ZeroKnowledgeProofs.verify_proof(proof, "challenge"))
        self.assertFalse(ZeroKnowledgeProofs.verify_proof(proof, "other"))
