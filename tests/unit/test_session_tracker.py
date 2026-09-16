"""Unit tests for ThinkBox Session Tracking, Coalition, Consensus, Economy, Intelligence."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if "fastapi" not in sys.modules:
    sys.modules["fastapi"] = MagicMock()
    sys.modules["pydantic"] = MagicMock()


class TestSessionTracking(unittest.TestCase):
    def test_session_id_format(self):
        from thinkbox.session import generate_session_id
        sid = generate_session_id()
        self.assertTrue(sid.startswith("tb_sess_"))
        self.assertEqual(len(sid.split("_")), 4)

    def test_session_id_uniqueness(self):
        from thinkbox.session import generate_session_id
        ids = {generate_session_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)

    def test_create_session(self):
        from thinkbox.session import create_session, get_current_session, clear_session
        clear_session()
        session = create_session(environment="test", model_backend="Ollama", actor="test-user")
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.environment, "test")
        self.assertEqual(session.model_backend, "Ollama")
        self.assertEqual(session.actor, "test-user")
        current = get_current_session()
        self.assertEqual(current.session_id, session.session_id)
        clear_session()

    def test_session_context_vars(self):
        from thinkbox.session import create_session, get_current_session, clear_session, SESSION_CONTEXT_VAR
        clear_session()
        self.assertIsNone(SESSION_CONTEXT_VAR.get())
        session = create_session(environment="test")
        self.assertEqual(SESSION_CONTEXT_VAR.get().session_id, session.session_id)
        clear_session()
        self.assertIsNone(SESSION_CONTEXT_VAR.get())

    def test_get_environment_local(self):
        from thinkbox.session import get_environment
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_environment(), "local")

    def test_get_environment_box(self):
        from thinkbox.session import get_environment
        with patch.dict(os.environ, {"UPSTASH_PUBLIC_BOX_URL": "https://my-box.preview.box.upstash.com/"}):
            self.assertEqual(get_environment(), "my-box.preview.box.upstash.com")

    def test_session_to_dict(self):
        from thinkbox.session import SessionContext
        session = SessionContext(
            session_id="test_123",
            environment="test",
            model_backend="Ollama",
            actor="user",
        )
        d = session.to_dict()
        self.assertEqual(d["session_id"], "test_123")
        self.assertEqual(d["environment"], "test")


class TestCoalitionProtocol(unittest.TestCase):
    def test_crdt_set_get(self):
        from thinkbox.coalition import CrdtSharedMemory
        mem = CrdtSharedMemory()
        mem.set("key1", "value1", agent_id="agent_1")
        self.assertEqual(mem.get("key1"), "value1")

    def test_crdt_merge(self):
        from thinkbox.coalition import CrdtSharedMemory
        mem = CrdtSharedMemory()
        mem.set("key1", {"a": 1}, agent_id="agent_1")
        mem.set("key1", {"b": 2}, agent_id="agent_2")
        result = mem.get("key1")
        self.assertIn("a", result)
        self.assertIn("b", result)

    def test_task_market(self):
        from thinkbox.coalition import TaskDelegationMarket
        market = TaskDelegationMarket()
        market.list_task("task_1", "Test task", reward=100)
        self.assertTrue(market.place_bid("task_1", "agent_1", 50, 1.0, 100.0))
        winner = market.select_winner("task_1")
        self.assertEqual(winner, "agent_1")

    def test_shared_bus(self):
        from thinkbox.coalition import SharedContextBus
        bus = SharedContextBus()
        received = []
        bus.subscribe("test_topic", lambda msg: received.append(msg))
        bus.publish("test_topic", {"data": "test"})
        self.assertEqual(len(received), 1)

    def test_capability_registry(self):
        from thinkbox.coalition import AgentCapabilityRegistry
        reg = AgentCapabilityRegistry()
        reg.register("agent_1", "coding")
        best = reg.find_best_agent("coding")
        self.assertEqual(best, "agent_1")

    def test_governance(self):
        from thinkbox.coalition import CoalitionGovernance
        gov = CoalitionGovernance()
        pid = gov.propose("Test proposal", "Description", "agent_1")
        gov.vote(pid, "agent_1", True)
        gov.vote(pid, "agent_2", True)
        status = gov.tally(pid, 2)
        self.assertEqual(status, "passed")


class TestConsensus(unittest.TestCase):
    def test_single_model(self):
        from thinkbox.consensus import MultiModelVoting, ModelOutput
        voting = MultiModelVoting()
        result = voting.vote("task_1", [ModelOutput(model_id="m1", output="test")])
        self.assertEqual(result.method, "single_model")
        self.assertEqual(result.winning_model, "m1")

    def test_weighted_vote(self):
        from thinkbox.consensus import MultiModelVoting, ModelOutput
        voting = MultiModelVoting()
        voting.register_model("m1", 0.9)
        voting.register_model("m2", 0.5)
        outputs = [
            ModelOutput(model_id="m1", output="def foo(): pass"),
            ModelOutput(model_id="m2", output="x"),
        ]
        result = voting.vote("task_1", outputs)
        self.assertEqual(result.method, "weighted_vote")

    def test_confidence_scorer(self):
        from thinkbox.consensus import ConfidenceScorer
        conf = ConfidenceScorer.bayes_confidence("def foo(): pass", 0.9)
        self.assertGreater(conf, 0.5)

    def test_disagreement_resolver(self):
        from thinkbox.consensus import DisagreementResolver
        resolver = DisagreementResolver(consensus_threshold=0.6)
        self.assertTrue(True)  # Placeholder


class TestEconomy(unittest.TestCase):
    def test_token_transfer(self):
        from thinkbox.economy import AgentTokenEconomy
        econ = AgentTokenEconomy()
        econ.create_account("agent_1", 100)
        econ.create_account("agent_2", 50)
        self.assertTrue(econ.transfer("agent_1", "agent_2", 30))
        self.assertEqual(econ.get_balance("agent_1"), 70)
        self.assertEqual(econ.get_balance("agent_2"), 80)

    def test_contribution_mining(self):
        from thinkbox.economy import AgentTokenEconomy, ContributionMining
        econ = AgentTokenEconomy()
        econ.create_account("treasury", 10000)
        mining = ContributionMining(econ)
        reward = mining.mine("agent_1", "task_complete")
        self.assertGreater(reward, 0)

    def test_staking(self):
        from thinkbox.economy import AgentTokenEconomy, StakingMechanism
        econ = AgentTokenEconomy()
        econ.create_account("agent_1", 100)
        staking = StakingMechanism(econ)
        self.assertTrue(staking.stake("agent_1", "task_1", 50))


class TestIntelligence(unittest.TestCase):
    def test_concept_extraction(self):
        from thinkbox.intelligence import ConceptExtractor
        extractor = ConceptExtractor()
        concepts = extractor.extract("def foo(): pass\nimport os")
        self.assertGreater(len(concepts), 0)

    def test_semantic_search(self):
        from thinkbox.intelligence import SemanticSearch
        search = SemanticSearch()
        search.index("doc_1", "python machine learning")
        search.index("doc_2", "javascript web development")
        results = search.search("python")
        self.assertGreater(len(results), 0)

    def test_circuit_breaker(self):
        from thinkbox.intelligence import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3)
        self.assertTrue(cb.can_execute())
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        self.assertFalse(cb.can_execute())

    def test_auto_bug_patcher(self):
        from thinkbox.intelligence import AutoBugPatcher
        patcher = AutoBugPatcher()
        error_msg = "NameError: name 'foo' is not defined"
        source = "print(foo)"
        patch_result = patcher.generate_patch(error_msg, source)
        self.assertIsNotNone(patch_result)

    def test_proof_of_work(self):
        from thinkbox.intelligence import ProofOfWork
        challenge = ProofOfWork.generate_challenge()
        hash_result, nonce = ProofOfWork.solve(challenge, difficulty=1)
        self.assertTrue(ProofOfWork.verify(challenge, hash_result, nonce, difficulty=1))

    def test_kyber_key_exchange(self):
        from thinkbox.intelligence import KyberKeyExchange
        kyber = KyberKeyExchange(security_level=32)
        pub, priv = kyber.generate_keypair()
        ciphertext, shared = kyber.encapsulate(pub)
        self.assertEqual(len(shared), 32)

    def test_zero_knowledge_proof(self):
        from thinkbox.intelligence import ZeroKnowledgeProofs
        proof = ZeroKnowledgeProofs.create_proof("secret", "challenge")
        self.assertIn("commitment", proof)
        self.assertTrue(ZeroKnowledgeProofs.verify_proof(proof, "challenge"))


class TestEmbedder(unittest.TestCase):
    def test_openai_compat_embed_happy_path(self):
        from thinkbox.embedder import OpenAICompatEmbedder
        embedder = OpenAICompatEmbedder(
            api_key="test-key",
            base_url="https://api.inceptionlabs.ai/v1",
        )
        embedding = [0.5] * 1536
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "data": [{"embedding": embedding, "index": 0}]
        }).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        with patch("urllib.request.urlopen", return_value=mock_resp):
            vectors = embedder.embed(["hello world"])
            self.assertEqual(len(vectors), 1)
            self.assertEqual(len(vectors[0]), 1536)
            self.assertTrue(all(isinstance(v, float) for v in vectors[0]))

    def test_openai_compat_embed_no_api_key(self):
        from thinkbox.embedder import OpenAICompatEmbedder, EmbeddingError
        embedder = OpenAICompatEmbedder(api_key="", base_url="https://example.com")
        with self.assertRaises(EmbeddingError):
            embedder.embed(["hello"])

    def test_openai_compat_embed_empty_texts(self):
        from thinkbox.embedder import OpenAICompatEmbedder
        embedder = OpenAICompatEmbedder(api_key="test-key", base_url="https://example.com")
        result = embedder.embed([])
        self.assertEqual(result, [])

    def test_deterministic_embedder_stable(self):
        from thinkbox.embedder import DeterministicEmbedder
        embedder = DeterministicEmbedder()
        v1 = embedder.embed(["test text"])
        v2 = embedder.embed(["test text"])
        self.assertEqual(v1, v2)
        self.assertEqual(len(v1[0]), 1536)

    def test_deterministic_embedder_multiple(self):
        from thinkbox.embedder import DeterministicEmbedder
        embedder = DeterministicEmbedder()
        vectors = embedder.embed(["a", "b"])
        self.assertEqual(len(vectors), 2)
        self.assertNotEqual(vectors[0], vectors[1])

    def test_deterministic_embedder_empty(self):
        from thinkbox.embedder import DeterministicEmbedder
        embedder = DeterministicEmbedder()
        result = embedder.embed([])
        self.assertEqual(result, [])

    def test_embedding_error_str(self):
        from thinkbox.embedder import EmbeddingError
        err = EmbeddingError(message="test failure")
        self.assertIn("test failure", str(err))


class TestUpstashVectorSyncEmbedder(unittest.TestCase):
    def test_upsert_raises_when_no_embedder(self):
        from thinkbox.session import UpstashVectorSync, EmbeddingError, SessionContext
        with patch.dict(os.environ, {
            "UPSTASH_VECTOR_REST_URL": "https://vec.upstash.io/",
            "UPSTASH_VECTOR_REST_TOKEN": "t",
            "THINKBOX_OPENAI_COMPAT_API_KEY": "",
            "THINKBOX_OPENAI_COMPAT_BASE_URL": "",
        }, clear=True):
            sync = UpstashVectorSync()
            session = SessionContext(
                session_id="test_sess_1",
                environment="local",
                model_backend="Ollama",
                actor="test",
            )
            import asyncio
            with self.assertRaises(EmbeddingError) as cm:
                asyncio.run(
                    sync.upsert(session)
                )
            self.assertIn("No embedder available", str(cm.exception))

    def test_upsert_raises_when_embedder_fails(self):
        from thinkbox.session import UpstashVectorSync, EmbeddingError, SessionContext
        from thinkbox.embedder import Embedder

        class FailingEmbedder(Embedder):
            @property
            def dimension(self) -> int:
                return 1536
            def embed(self, texts):
                raise EmbeddingError(message="embedder down")

        with patch.dict(os.environ, {
            "UPSTASH_VECTOR_REST_URL": "https://vec.upstash.io/",
            "UPSTASH_VECTOR_REST_TOKEN": "t",
        }, clear=True):
            sync = UpstashVectorSync(embedder=FailingEmbedder())
            session = SessionContext(
                session_id="test_sess_2",
                environment="local",
                model_backend="Ollama",
                actor="test",
            )
            import asyncio
            with self.assertRaises(EmbeddingError) as cm:
                asyncio.run(
                    sync.upsert(session)
                )
            self.assertIn("Embedder failed", str(cm.exception))

    def test_upsert_sends_vector_in_payload(self):
        from thinkbox.session import UpstashVectorSync, SessionContext
        from thinkbox.embedder import DeterministicEmbedder

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"result":"Success"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with patch.dict(os.environ, {
            "UPSTASH_VECTOR_REST_URL": "https://vec.upstash.io/",
            "UPSTASH_VECTOR_REST_TOKEN": "t",
        }, clear=True):
            sync = UpstashVectorSync(embedder=DeterministicEmbedder())
            session = SessionContext(
                session_id="test_sess_3",
                environment="local",
                model_backend="Ollama",
                actor="test",
            )
            with patch("urllib.request.urlopen", return_value=mock_resp) as m:
                import asyncio
                result = asyncio.run(
                    sync.upsert(session)
                )
                self.assertTrue(result)
                payload = json.loads(m.call_args.args[0].data)
                self.assertIn("vector", payload)
                self.assertIsInstance(payload["vector"], list)
                self.assertEqual(len(payload["vector"]), 1536)
                self.assertIn("id", payload)
                self.assertEqual(payload["id"], "test_sess_3")
                self.assertIn("metadata", payload)
                self.assertEqual(payload["metadata"]["session_id"], "test_sess_3")

    def test_upsert_payload_shape_matches_dense_index(self):
        from thinkbox.session import UpstashVectorSync, SessionContext
        from thinkbox.embedder import DeterministicEmbedder

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"result":"Success"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        with patch.dict(os.environ, {
            "UPSTASH_VECTOR_REST_URL": "https://vec.upstash.io/",
            "UPSTASH_VECTOR_REST_TOKEN": "t",
        }, clear=True):
            sync = UpstashVectorSync(embedder=DeterministicEmbedder())
            session = SessionContext(
                session_id="test_sess_4",
                environment="test",
                model_backend="Ollama",
                actor="user",
                metadata={"key": "value"},
            )
            with patch("urllib.request.urlopen", return_value=mock_resp) as m:
                import asyncio
                asyncio.run(
                    sync.upsert(session)
                )
                payload = json.loads(m.call_args.args[0].data)
                self.assertIn("vector", payload)
                self.assertEqual(len(payload["vector"]), 1536)
                self.assertIn("id", payload)
                self.assertIn("metadata", payload)
                self.assertIn("execution_status", payload["metadata"])
                self.assertEqual(payload["metadata"]["execution_status"], "RUNNING")
                self.assertEqual(payload["metadata"]["key"], "value")

    def test_upsert_raises_on_http_error(self):
        from thinkbox.session import UpstashVectorSync, EmbeddingError, SessionContext
        from thinkbox.embedder import DeterministicEmbedder

        with patch.dict(os.environ, {
            "UPSTASH_VECTOR_REST_URL": "https://vec.upstash.io/",
            "UPSTASH_VECTOR_REST_TOKEN": "t",
        }, clear=True):
            sync = UpstashVectorSync(embedder=DeterministicEmbedder())
            session = SessionContext(
                session_id="test_sess_5",
                environment="local",
                model_backend="Ollama",
                actor="test",
            )
            import urllib.error
            with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
                "http://vec.upstash.io/upsert", 422, "Bad", {}, None
            )):
                import asyncio
                with self.assertRaises(EmbeddingError) as cm:
                    asyncio.run(
                        sync.upsert(session)
                    )
                self.assertIn("422", str(cm.exception))

    def test_default_embedder_none_when_env_missing(self):
        from thinkbox.session import UpstashVectorSync
        with patch.dict(os.environ, {
            "UPSTASH_VECTOR_REST_URL": "https://vec.upstash.io/",
            "UPSTASH_VECTOR_REST_TOKEN": "t",
            "THINKBOX_OPENAI_COMPAT_API_KEY": "",
            "THINKBOX_OPENAI_COMPAT_BASE_URL": "",
        }, clear=True):
            sync = UpstashVectorSync()
            self.assertIsNone(sync._embedder)

    def test_default_embedder_created_when_env_present(self):
        from thinkbox.session import UpstashVectorSync
        with patch.dict(os.environ, {
            "UPSTASH_VECTOR_REST_URL": "https://vec.upstash.io/",
            "UPSTASH_VECTOR_REST_TOKEN": "t",
            "THINKBOX_OPENAI_COMPAT_API_KEY": "sk-test",
            "THINKBOX_OPENAI_COMPAT_BASE_URL": "https://api.inceptionlabs.ai/v1",
        }, clear=True):
            sync = UpstashVectorSync()
            self.assertIsNotNone(sync._embedder)

    def test_upsert_disabled_without_env(self):
        from thinkbox.session import UpstashVectorSync, SessionContext
        import asyncio
        with patch.dict(os.environ, {}, clear=True):
            sync = UpstashVectorSync()
            self.assertFalse(sync.enabled)
            result = asyncio.run(
                sync.upsert(SessionContext("id", "local", "Ollama", "a"))
            )
            self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
