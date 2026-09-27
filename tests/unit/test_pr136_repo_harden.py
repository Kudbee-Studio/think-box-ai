"""PR #136 repository hardening — hermetic regression tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.validation import validate_receipt_id, validate_thinkbox_id
from thinkbox.org_memory_receipts import redact_mapping
from thinkbox.path_safe import resolve_under_roots
from thinkbox.read_cache import TtlSnapshotCache, etag_matches, reset_read_caches_for_tests
from thinkbox.sqlite_pragmas import open_sqlite


class TestSqlitePragmas(unittest.TestCase):
    def test_open_sqlite_sets_foreign_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            conn = open_sqlite(db)
            try:
                fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
                self.assertEqual(fk, 1)
            finally:
                conn.close()


class TestPathSafe(unittest.TestCase):
    def test_blocks_traversal(self) -> None:
        with self.assertRaises(PermissionError):
            resolve_under_roots("../../../etc/passwd")

    def test_allows_data_relative(self) -> None:
        resolved = resolve_under_roots("data/thinkboxmd")
        self.assertTrue(resolved.is_dir() or resolved.parent.is_dir())


class TestRedactMapping(unittest.TestCase):
    def test_redacts_inline_bearer(self) -> None:
        out = redact_mapping({"note": "Authorization: Bearer secret-token-12345678"})
        self.assertEqual(out["note"], "[REDACTED]")


class TestValidationIds(unittest.TestCase):
    def test_receipt_id_rejects_empty(self) -> None:
        ok, _ = validate_receipt_id("")
        self.assertFalse(ok)

    def test_thinkbox_id_accepts_engine(self) -> None:
        ok, val = validate_thinkbox_id("eng_dash", label="Job ID")
        self.assertTrue(ok)
        self.assertEqual(val, "eng_dash")


class TestReadCache(unittest.TestCase):
    def test_invalidate_prefix(self) -> None:
        cache = TtlSnapshotCache[float](ttl_seconds=60.0, max_entries=8)
        cache.set("experiment_dashboard:a", 1.0)
        cache.set("experiment_dashboard:b", 2.0)
        cache.set("other:c", 3.0)
        cache.invalidate_prefix("experiment_dashboard:")
        self.assertIsNone(cache.get("experiment_dashboard:a"))
        self.assertIsNotNone(cache.get("other:c"))

    def test_etag_matches_rejects_huge_header(self) -> None:
        self.assertFalse(etag_matches("W/" + ("x" * 5000), 'W/"abc"'))

    def tearDown(self) -> None:
        reset_read_caches_for_tests()


class TestHermeticProvider(unittest.TestCase):
    def test_empty_subtasks_fail_closed(self) -> None:
        from thinkbox.hermetic_provider import HermeticModelProvider

        with self.assertRaises(ValueError):
            HermeticModelProvider([])


class TestGithubWebhookBodyLimit(unittest.TestCase):
    def test_oversized_body_rejected(self) -> None:
        from thinkbox.github_webhook import MAX_WEBHOOK_BODY_BYTES, verify_github_webhook_signature

        body = b"x" * (MAX_WEBHOOK_BODY_BYTES + 1)
        result = verify_github_webhook_signature("secret", body, "sha256=deadbeef")
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "payload_too_large")
