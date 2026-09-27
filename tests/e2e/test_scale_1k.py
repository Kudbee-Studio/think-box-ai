"""E2E test: 1K-agent scale test (CI-safe hermetic variant).

This test runs a reduced-scale version of the 1K-agent swarm in CI,
with mock provider completion to avoid live API calls and timeouts.

Scale factors (CI-safe):
- Primary workers: 100 (vs. 800 in full test)
- Validator workers: 25 (vs. 200 in full test)
- Concurrency: 8 (vs. 32 in full test)
- Uses mock provider (no real API calls)

Expected results:
- Success rate: 100% (mock provider never fails)
- RPS: N/A (no real latency measurement)
- Ledger valid: True
- All memory entries stored correctly

Test timeout: 600 seconds (10 minutes)
"""

from __future__ import annotations

import json
import time
import unittest
from pathlib import Path
from typing import Any

from thinkbox.workspace import WorkspaceRegistry, WorkspaceStore, ThinkBox
from thinkbox.identity import IdentityLedger
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.admission import AdmissionGate
from thinkbox.ledger import ActionLedger
from thinkbox.thinktrace import ThinkTraceCapture
from thinkbox.metrics import MetricsStore, compute_swarm_strength
from thinkbox.swarm_stats import (
    effective_rps,
    latency_percentiles,
    open_action_ledger,
)
from thinkbox.flightrecorder import FlightRecorder, WorkerRecord
from thinkbox.memory_evolution import MemoryEvolution
from thinkbox.reputation import ReputationLedger
from thinkbox.experiments import ExperimentStore, price_tokens
from core.memory.store import MemoryStore
from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer


class MockProvider:
    """Mock provider for CI-safe testing (no real API calls)."""

    def __init__(self) -> None:
        self.call_count = 0
        self.latency_ms = 100  # Simulate 100ms latency

    def complete(self, system: str, user: str, max_tokens: int = 900) -> tuple[str, dict]:
        """Mock provider completion."""
        self.call_count += 1
        time.sleep(self.latency_ms / 1000.0)  # Simulate latency

        # Deterministic tier selection based on claim_id
        if "EVIDENCE" in user.upper():
            tier = "EVIDENCE"
        elif self.call_count % 4 == 0:
            tier = "HYPOTHESIS"
        elif self.call_count % 3 == 0:
            tier = "INFERENCE"
        else:
            tier = "EVIDENCE"

        return tier, {
            "prompt_tokens": 50,
            "completion_tokens": 10,
            "total_tokens": 60,
        }


class Scale1KE2E(unittest.TestCase):
    """CI-safe 1K-agent scale test with mock provider."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        import uuid
        import shutil

        # Create unique test directory per test to avoid I/O conflicts
        test_id = uuid.uuid4().hex[:8]
        self.test_dir = Path(__file__).resolve().parent.parent.parent / "data" / f"test_scale_1k_{test_id}"
        self.test_dir.mkdir(parents=True, exist_ok=True)

        self.registry = WorkspaceRegistry()
        self.store = WorkspaceStore(self.test_dir / "workspaces.db")
        self.identities = IdentityLedger()
        self.tokens = GovernanceTokenService(signing_key=f"test-scale-1k-key-{test_id}")
        self.gate = AdmissionGate(self.tokens, self.identities)
        self.ledger, _ = open_action_ledger(self.test_dir / "action_ledger.db", fresh=True)
        self.traces = ThinkTraceCapture()
        self.memory = MemoryStore(self.test_dir / "memory.db")
        self.metrics = MetricsStore(self.test_dir / "metrics.db")
        self.flight = FlightRecorder(self.test_dir / "flight.db")
        self.memory_evo = MemoryEvolution(self.test_dir / "memory_evo.db")
        self.reputation = ReputationLedger(self.test_dir / "reputation.db")
        self.experiments = ExperimentStore(self.test_dir / "experiments.db")

        self.provider = MockProvider()
        self.session_id = f"scale1k_test_{int(time.time())}_{test_id}"
        self.metrics.start_session(
            self.session_id, kind="scale_1k_e2e", model="mock", concurrency=8,
            metadata={"scale": 125, "ci_safe": True},
        )

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_100_primary_workers_mock(self) -> None:
        """Test 100 primary workers with mock provider."""
        primary_n = 100
        results = []

        for i in range(primary_n):
            claim_id = f"TEST-{i:05d}"
            worker_id = f"e2e-worker-{i:05d}"

            # Register and authorize worker
            self.identities.register(worker_id, capabilities=["research:primary"])
            tok = self.tokens.issue(TokenRequest(agent_id=worker_id, capabilities=["research:primary"], ttl_seconds=300))
            decision = self.gate.authorize(tok.token_value, worker_id, "research:primary")

            self.assertTrue(decision.allowed, f"Worker {worker_id} admission failed")

            # Create ThinkBox
            box = self.registry.create(
                owner_id=worker_id,
                capabilities=["research:primary"],
                state={"role": "PRIMARY", "claim_id": claim_id},
            )
            self.store.save(box)

            # Fire the worker
            system = "Reply with ONE tier: EVIDENCE INFERENCE HYPOTHESIS UNVERIFIED"
            user = f"Claim: synthetic test {i}"

            content, usage = self.provider.complete(system, user)

            ok = True
            tier = content if content in ["EVIDENCE", "INFERENCE", "HYPOTHESIS"] else "HYPOTHESIS"

            # Record audit
            self.ledger.append(
                worker_id, "research:primary", "scale1k:test", ok,
                "admitted" if ok else "error",
                {"claim_id": claim_id, "box_id": box.box_id},
            )

            # Capture trace
            trace = self.traces.capture(
                worker_id, content, evidence_refs=[f"claim:{claim_id}"],
                tags=["PRIMARY", "scale1k"], metadata={"box_id": box.box_id},
            )

            # Store memory
            if ok:
                self.memory.put(MemoryEntry(
                    key=f"scale1k:{claim_id}:{trace.trace_id}",
                    layer=MemoryLayer.ORGANIZATIONAL,
                    entry_type=MemoryEntryType.PATTERN,
                    value={"role": "PRIMARY", "tier": tier, "claim_id": claim_id},
                    agent_id=worker_id,
                    task_id="scale_1k_e2e",
                    confidence=0.7,
                ))

            # Record flight recorder
            self.flight.record(WorkerRecord(
                session_id=self.session_id,
                worker_id=worker_id,
                role="PRIMARY",
                model="mock",
                prompt_version="v1",
                trace_id=trace.trace_id,
                box_id=box.box_id,
                claim_id=claim_id,
                capability="research:primary",
                temperature=0.0,
                max_tokens=900,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                reasoning_tokens=0,
                total_tokens=usage.get("total_tokens", 0),
                latency_s=self.provider.latency_ms / 1000.0,
                decision=tier,
                evidence_refs=[f"claim:{claim_id}"],
                outcome="ok" if ok else "error",
                error="",
                cost_usd=0.0,
            ))

            results.append({
                "worker": worker_id,
                "claim": claim_id,
                "ok": ok,
                "tier": tier,
            })

        # Verify results
        self.assertEqual(len(results), primary_n)
        ok_count = sum(1 for r in results if r["ok"])
        self.assertEqual(ok_count, primary_n)

        # Verify ledger
        ledger_entries = self.ledger.entries(limit=10_000)
        self.assertGreater(len(ledger_entries), 0)
        self.assertTrue(self.ledger.verify())

        # Verify traces
        trace_count = self.traces.count()
        self.assertEqual(trace_count, primary_n)

        # Verify memory
        memory_count = self.memory.count()
        self.assertEqual(memory_count, primary_n)

    def test_25_validator_workers_mock(self) -> None:
        """Test 25 validator workers with mock provider."""
        primary_results = []
        validator_n = 25

        # Create 25 primary workers first
        for i in range(validator_n):
            claim_id = f"TEST-PRIM-{i:05d}"
            worker_id = f"e2e-primary-{i:05d}"

            # Register and authorize
            self.identities.register(worker_id, capabilities=["research:primary"])
            tok = self.tokens.issue(TokenRequest(agent_id=worker_id, capabilities=["research:primary"], ttl_seconds=300))
            decision = self.gate.authorize(tok.token_value, worker_id, "research:primary")
            self.assertTrue(decision.allowed)

            # Create box and fire
            box = self.registry.create(
                owner_id=worker_id,
                capabilities=["research:primary"],
                state={"role": "PRIMARY", "claim_id": claim_id},
            )
            self.store.save(box)

            content, _ = self.provider.complete("Reply with tier", "Claim: test")
            tier = content if content in ["EVIDENCE", "INFERENCE", "HYPOTHESIS"] else "HYPOTHESIS"

            primary_results.append({
                "worker_id": worker_id,
                "claim_id": claim_id,
                "tier": tier,
            })

        # Now run validators on them
        validator_count = 0
        for i, primary in enumerate(primary_results):
            validator_id = f"e2e-validator-{i:05d}"

            # Register and authorize validator
            self.identities.register(validator_id, capabilities=["research:validator"])
            tok = self.tokens.issue(TokenRequest(agent_id=validator_id, capabilities=["research:validator"], ttl_seconds=300))
            decision = self.gate.authorize(tok.token_value, validator_id, "research:validator")
            self.assertTrue(decision.allowed)

            # Create box
            box = self.registry.create(
                owner_id=validator_id,
                capabilities=["research:validator"],
                state={"role": "VALIDATOR", "claim_id": primary["claim_id"]},
            )
            self.store.save(box)

            # Fire validator
            content, _ = self.provider.complete(
                "Adversarial review: reply with tier",
                f"Claim: test. Primary tier: {primary['tier']}",
            )
            tier = content if content in ["EVIDENCE", "INFERENCE", "HYPOTHESIS"] else "HYPOTHESIS"

            self.ledger.append(
                validator_id, "research:validator", "scale1k:test", True, "admitted",
                {"claim_id": primary["claim_id"]},
            )

            validator_count += 1

        self.assertEqual(validator_count, validator_n)
        self.assertTrue(self.ledger.verify())

    def test_ledger_verification(self) -> None:
        """Test that ledger verification passes."""
        # Add some test entries
        entry_count = 0
        for i in range(10):
            entry = self.ledger.append(
                f"worker-{i}", "capability", "action", True, "admitted",
                {"test": i},
            )
            self.assertIsNotNone(entry)
            entry_count += 1

        # Verify chain
        self.assertTrue(self.ledger.verify())

        # Verify entry count
        self.assertEqual(entry_count, 10)

    def test_concurrent_admission_checks(self) -> None:
        """Test concurrent admission checks."""
        import concurrent.futures

        def check_admission(worker_id: str) -> bool:
            self.identities.register(worker_id, capabilities=["test"])
            tok = self.tokens.issue(TokenRequest(agent_id=worker_id, capabilities=["test"], ttl_seconds=300))
            decision = self.gate.authorize(tok.token_value, worker_id, "test")
            return decision.allowed

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(check_admission, f"concurrent-{i}")
                for i in range(50)
            ]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(results), 50)
        self.assertTrue(all(results))

    def test_memory_store_scaling(self) -> None:
        """Test memory store can handle many entries."""
        for i in range(100):
            self.memory.put(MemoryEntry(
                key=f"scale_test_{i}",
                layer=MemoryLayer.ORGANIZATIONAL,
                entry_type=MemoryEntryType.PATTERN,
                value={"index": i},
                agent_id=f"agent-{i % 10}",
                task_id="scale_test",
                confidence=0.5 + (i % 50) / 100.0,
            ))

        count = self.memory.count()
        self.assertEqual(count, 100)

        # Verify we can retrieve entries
        retrieved = self.memory.get("scale_test_0")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.value["index"], 0)


if __name__ == "__main__":
    unittest.main(timeout=600)
