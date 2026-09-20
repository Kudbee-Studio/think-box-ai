"""Hermetic BYOC tests — mock Mercury-2 → stash → proof bind → verify."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from thinkbox.byoc_config import ByocConfig
from thinkbox.byoc_resolve import resolve_mercury_byoc
from thinkbox.byoc_stash_store import ThinkStashStore, StashRecord
from thinkbox.byoc_stash_writer import ThinkStashEntry, ThinkStashWriter
from thinkbox.byoc_stash_reader import ThinkStashReader
from thinkbox.byoc_proof_bind import StashProofBinder, StashProofLink


class TestByocConfigMock(unittest.TestCase):
    def test_load_returns_mock_when_no_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            cfg = ByocConfig.load()
        self.assertEqual(cfg.demo_mode, "mock")
        self.assertFalse(cfg.is_live)
        self.assertTrue(cfg.is_mock)

    def test_redacted_never_contains_secrets(self) -> None:
        cfg = ByocConfig(api_key="super-secret", vector_token="also-secret")
        redacted = cfg.redacted()
        self.assertNotIn("api_key", redacted)
        self.assertNotIn("vector_token", redacted)
        self.assertIn("has_api_key", redacted)
        self.assertIn("has_vector_creds", redacted)

    def test_is_live_requires_all_credentials(self) -> None:
        cfg = ByocConfig(
            api_key="key",
            vector_url="https://example.com",
            vector_token="token",
            demo_mode="byoc",
        )
        self.assertTrue(cfg.is_live)

    def test_is_live_false_without_vector_url(self) -> None:
        cfg = ByocConfig(api_key="key", vector_url="", vector_token="token", demo_mode="byoc")
        self.assertFalse(cfg.is_live)


class TestResolveMercuryByoc(unittest.TestCase):
    def test_resolve_returns_mock_mode(self) -> None:
        with patch.dict(os.environ, {"DEMO_MODE": "mock"}, clear=True):
            result = resolve_mercury_byoc()
        self.assertEqual(result["mode"], "mock")
        self.assertTrue(result["usable"])
        self.assertIsNone(result["client"])

    def test_resolve_fail_closed_without_credentials(self) -> None:
        with patch.dict(os.environ, {"DEMO_MODE": "byoc"}, clear=True):
            result = resolve_mercury_byoc()
        self.assertEqual(result["mode"], "byoc")
        self.assertFalse(result["usable"])
        self.assertIsNone(result["client"])

    def test_resolve_byoc_with_config(self) -> None:
        cfg = ByocConfig(
            api_key="key",
            vector_url="https://example.com",
            vector_token="token",
            demo_mode="byoc",
        )
        with patch.dict(os.environ, {"DEMO_MODE": "byoc"}, clear=True):
            result = resolve_mercury_byoc(config=cfg)
        self.assertEqual(result["mode"], "byoc")
        self.assertTrue(result["usable"])


class TestThinkStashStore(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ThinkStashStore(":memory:")

    def _record(self, stash_id: str, **overrides: str) -> StashRecord:
        return StashRecord(
            stash_id=stash_id,
            session_id=overrides.get("session_id", ""),
            burst_id=overrides.get("burst_id", ""),
            reasoning_sha256=overrides.get("reasoning_sha256", "abc123"),
            vector_id=overrides.get("vector_id", "vec456"),
            proof_receipt_id=overrides.get("proof_receipt_id", ""),
            metadata=overrides.get("metadata", {}),
            created_at=overrides.get("created_at", ""),
            evidence_label=overrides.get("evidence_label", "simulated"),
        )

    def test_upsert_and_get(self) -> None:
        record = self._record("stash-1")
        self.store.upsert(record)
        result = self.store.get("stash-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["stash_id"], "stash-1")

    def test_get_missing_returns_none(self) -> None:
        self.assertIsNone(self.store.get("nonexistent"))

    def test_find_by_session(self) -> None:
        r1 = self._record("s1", session_id="sess-1")
        r2 = self._record("s2", session_id="sess-1")
        r3 = self._record("s3", session_id="sess-2")
        self.store.upsert(r1)
        self.store.upsert(r2)
        self.store.upsert(r3)
        results = self.store.find_by_session("sess-1")
        self.assertEqual(len(results), 2)

    def test_find_by_proof(self) -> None:
        r1 = self._record("p1", proof_receipt_id="proof-1")
        r2 = self._record("p2", proof_receipt_id="proof-1")
        self.store.upsert(r1)
        self.store.upsert(r2)
        results = self.store.find_by_proof("proof-1")
        self.assertEqual(len(results), 2)

    def test_count(self) -> None:
        self.assertEqual(self.store.count(), 0)
        self.store.upsert(self._record("a"))
        self.store.upsert(self._record("b"))
        self.assertEqual(self.store.count(), 2)

    def test_last_harvest_returns_none_when_empty(self) -> None:
        self.assertIsNone(self.store.last_harvest())

    def test_last_harvest_returns_latest(self) -> None:
        r1 = self._record("old", created_at="2026-01-01T00:00:00+00:00")
        r2 = self._record("new", created_at="2026-06-15T12:00:00+00:00")
        self.store.upsert(r1)
        self.store.upsert(r2)
        last = self.store.last_harvest()
        self.assertEqual(last["stash_id"], "new")

    def test_find_by_session_returns_empty_when_none(self) -> None:
        results = self.store.find_by_session("nonexistent")
        self.assertEqual(results, [])

    def test_count_after_upsert_and_get(self) -> None:
        record = self._record("x")
        self.store.upsert(record)
        self.assertEqual(self.store.count(), 1)
        self.assertIsNotNone(self.store.get("x"))


class TestThinkStashWriter(unittest.TestCase):
    def test_write_with_mock_embedder(self) -> None:
        with patch("thinkbox.byoc_stash_writer.DeterministicEmbedder") as mock_embed:
            mock_embed.return_value.embed.return_value = [[0.1] * 1536]
            config = ByocConfig(demo_mode="mock", vector_url="", vector_token="")
            writer = ThinkStashWriter(config)
            entry = ThinkStashEntry(
                stash_id="test-1",
                session_id="sess-1",
                reasoning_sha256="sha1",
                proof_receipt_id="proof-1",
            )
            with patch.object(writer, "_upsert", return_value={"ok": True}):
                result = writer.write(entry)
            self.assertEqual(result.stash_id, "test-1")
            self.assertIsNotNone(result.vector_id)

    def test_write_batch(self) -> None:
        with patch("thinkbox.byoc_stash_writer.DeterministicEmbedder") as mock_embed:
            mock_embed.return_value.embed.return_value = [[0.1] * 1536]
            config = ByocConfig(demo_mode="mock", vector_url="", vector_token="")
            writer = ThinkStashWriter(config)
            entries = [
                ThinkStashEntry(stash_id=f"batch-{i}", reasoning_sha256=f"sha-{i}")
                for i in range(3)
            ]
            with patch.object(writer, "_upsert", return_value={"ok": True}):
                results = writer.write_batch(entries)
            self.assertEqual(len(results), 3)


class TestThinkStashReader(unittest.TestCase):
    def test_fetch_disabled_when_not_configured(self) -> None:
        config = ByocConfig(demo_mode="mock")
        reader = ThinkStashReader(config)
        result = reader.fetch("any-id")
        self.assertIsNone(result)

    def test_search_returns_empty_when_not_configured(self) -> None:
        config = ByocConfig(demo_mode="mock")
        reader = ThinkStashReader(config)
        results = reader.search([0.1] * 1536, top_k=5)
        self.assertEqual(results, [])

    def test_delete_returns_false_when_not_configured(self) -> None:
        config = ByocConfig(demo_mode="mock")
        reader = ThinkStashReader(config)
        result = reader.delete("any-id")
        self.assertFalse(result)


class TestStashProofBinder(unittest.TestCase):
    def test_bind_creates_link(self) -> None:
        store = MagicMock()
        config = ByocConfig(demo_mode="mock", vector_url="", vector_token="")
        binder = StashProofBinder(store, config)
        with patch.object(binder._writer, "write", return_value=MagicMock()) as mock_write:
            link = binder.bind(
                stash_id="stash-1",
                proof_receipt_id="proof-1",
                reasoning_text="test reasoning",
            )
            mock_write.assert_called_once()
        self.assertEqual(link.stash_id, "stash-1")
        self.assertEqual(link.proof_receipt_id, "proof-1")
        self.assertEqual(len(binder._links), 1)

    def test_verify_bind_delegates_to_verify_chain(self) -> None:
        store = MagicMock()
        config = ByocConfig(demo_mode="mock")
        binder = StashProofBinder(store, config)
        with patch("thinkbox.byoc_proof_bind.verify_chain") as mock_verify:
            mock_verify.return_value.valid = True
            result = binder.verify_bind()
            self.assertTrue(result)

    def test_get_bound_proof_returns_none_for_missing(self) -> None:
        store = MagicMock()
        config = ByocConfig(demo_mode="mock")
        binder = StashProofBinder(store, config)
        result = binder.get_bound_proof("nonexistent")
        self.assertIsNone(result)

    def test_export_proof_bundle_delegates(self) -> None:
        store = MagicMock()
        config = ByocConfig(demo_mode="mock")
        binder = StashProofBinder(store, config)
        with patch("thinkbox.byoc_proof_bind.export_proof_bundle") as mock_export:
            mock_export.return_value = {"bundle": "data"}
            result = binder.export_proof_bundle("/tmp/test")
            self.assertEqual(result, {"bundle": "data"})


class TestByocLiveSkip(unittest.TestCase):
    def test_writer_skips_live_without_env(self) -> None:
        config = ByocConfig(demo_mode="mock")
        writer = ThinkStashWriter(config)
        self.assertFalse(writer._enabled)

    def test_reader_skips_live_without_env(self) -> None:
        config = ByocConfig(demo_mode="mock")
        reader = ThinkStashReader(config)
        self.assertFalse(reader._enabled)


if __name__ == "__main__":
    unittest.main()