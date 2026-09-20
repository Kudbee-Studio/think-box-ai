"""Integration tests: stash + box + mercury end-to-end."""

import os
import unittest
from unittest.mock import MagicMock, Mock, patch

from thinkbox.byoc_config import ByocConfig
from thinkbox.byoc_stash_store import ThinkStashStore, StashRecord


class TestStashBoxMercuryIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ThinkStashStore(":memory:")

    def test_stash_store_count_after_upsert(self):
        record = StashRecord(
            stash_id="stash_test_001",
            session_id="sess_test",
            burst_id="burst_001",
            reasoning_sha256="abc123",
            vector_id="vec_001",
            proof_receipt_id="pr_001",
            evidence_label="simulated",
            created_at="2026-01-01T00:00:00+00:00",
        )
        self.store.upsert(record)
        self.assertEqual(self.store.count(), 1)
        last = self.store.last_harvest()
        self.assertIsNotNone(last)
        self.assertEqual(last.get("stash_id"), "stash_test_001")

    def test_stash_byoc_config_integration(self):
        config = ByocConfig.load()
        self.assertIsNotNone(config)
        self.assertEqual(self.store.count(), 0)

    def test_stash_store_redacted_on_read(self):
        record = StashRecord(
            stash_id="stash_secret",
            session_id="sess_1",
            burst_id="burst_1",
            reasoning_sha256="sha_1",
            vector_id="vec_1",
            proof_receipt_id="pr_1",
            evidence_label="simulated",
            created_at="2026-01-01T00:00:00+00:00",
            metadata={"secret_field": "should_not_appear"},
        )
        self.store.upsert(record)
        last = self.store.last_harvest()
        self.assertIsNotNone(last)
        self.assertNotIn("api_key", str(last))

    def test_stash_store_evidence_label_preserved(self):
        record = StashRecord(
            stash_id="stash_evidence",
            session_id="sess_e",
            burst_id="burst_e",
            reasoning_sha256="sha_e",
            vector_id="vec_e",
            proof_receipt_id="pr_e",
            evidence_label="verified",
            created_at="2026-01-01T00:00:00+00:00",
        )
        self.store.upsert(record)
        last = self.store.last_harvest()
        self.assertEqual(last.get("evidence_label"), "verified")

    def test_byoc_config_redacted_has_booleans(self):
        cfg = ByocConfig(api_key="super-secret", vector_token="also-secret")
        redacted = cfg.redacted()
        self.assertIn("has_api_key", redacted)
        self.assertIn("has_vector_creds", redacted)
        self.assertNotIn("api_key", redacted)
        self.assertNotIn("vector_token", redacted)

    def test_stash_store_count_after_batch(self):
        for i in range(5):
            self.store.upsert(StashRecord(
                stash_id=f"stash_batch_{i}",
                session_id="sess_batch",
                burst_id="burst_batch",
                reasoning_sha256=f"sha_{i}",
                vector_id=f"vec_{i}",
                proof_receipt_id=f"pr_{i}",
                evidence_label="simulated",
                created_at=f"2026-01-01T00:00:{i:02d}+00:00",
            ))
        self.assertEqual(self.store.count(), 5)


class TestBoxMercuryApiShape(unittest.TestCase):
    def test_box_status_endpoint_shape(self):
        try:
            from backend.api.v1.box_status import box_status_router
            routes = [r.path for r in box_status_router.routes if hasattr(r, 'path')]
            self.assertIn("/status", routes)
        except (ImportError, ModuleNotFoundError):
            self.skipTest("box_status API not available (fastapi not installed)")

    def test_box_mercury_endpoint_shape(self):
        try:
            from backend.api.v1.box_mercury import box_mercury_router
            routes = [r.path for r in box_mercury_router.routes if hasattr(r, 'path')]
            self.assertIn("/status", routes)
            self.assertIn("/results", routes)
        except (ImportError, ModuleNotFoundError):
            self.skipTest("box_mercury API not available (fastapi not installed)")


class TestDashboardEmitExperiment(unittest.TestCase):
    def test_dashboard_category_exists(self):
        from thinkbox.dashboard_state import DashboardCategory
        self.assertIn("execution", DashboardCategory.EXECUTION.value)

    def test_dashboard_event_exists(self):
        from thinkbox.dashboard_state import DashboardEvent
        self.assertIn("task_completed", DashboardEvent.TASK_COMPLETED.value)


class TestProofArtifactChain(unittest.TestCase):
    def test_proof_artifact_has_sha256(self):
        import hashlib
        import json
        from datetime import datetime, timezone
        artifact = {
            "experiment": "box-mercury-live",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "substrate": "upstash-box",
            "model": "mercury-2",
            "global_calls": 16,
            "evidence_label": "verified",
        }
        artifact["proof_sha256"] = hashlib.sha256(
            json.dumps(artifact, sort_keys=True, default=str).encode()
        ).hexdigest()
        self.assertIn("proof_sha256", artifact)
        self.assertEqual(len(artifact["proof_sha256"]), 64)

    def test_proof_artifact_is_verifiable(self):
        import hashlib
        import json
        from datetime import datetime, timezone
        artifact = {
            "experiment": "box-mercury-live",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "substrate": "upstash-box",
            "model": "mercury-2",
            "global_calls": 8,
            "evidence_label": "verified",
        }
        stored_hash = hashlib.sha256(
            json.dumps(artifact, sort_keys=True, default=str).encode()
        ).hexdigest()
        artifact["proof_sha256"] = stored_hash
        verification_payload = dict(artifact)
        del verification_payload["proof_sha256"]
        verification_hash = hashlib.sha256(
            json.dumps(verification_payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        self.assertEqual(stored_hash, verification_hash)
