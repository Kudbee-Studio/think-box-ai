"""Integration and E2E tests for Think Box AI."""

import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("/tmp/test_thinkbox.db")
        if self.db_path.exists():
            self.db_path.unlink()
        from core.database import init_db
        self.conn = init_db(self.db_path)

    def tearDown(self):
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_jobs_table_exists(self):
        tables = [r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        self.assertIn("jobs", tables)

    def test_sessions_table_exists(self):
        tables = [r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        self.assertIn("sessions", tables)

    def test_memory_table_exists(self):
        tables = [r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        self.assertIn("memory_entries", tables)

    def test_insert_job(self):
        self.conn.execute("INSERT INTO jobs (id, intent, hat, state, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            ("test_001", "Test", "researcher", "queue", "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z"))
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM jobs WHERE id=?", ("test_001",)).fetchone()
        self.assertIsNotNone(row)

    def test_insert_memory(self):
        self.conn.execute("INSERT INTO memory_entries VALUES (?,?,?,?,?,?,?,?,?)",
            ("key1", "task", "fact", "value1", "agent1", "task1", "2026-09-01T00:00:00Z", "2026-09-01T00:00:00Z", "{}", 1.0))
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM memory_entries WHERE key=?", ("key1",)).fetchone()
        self.assertIsNotNone(row)


class TestProviderRegistry(unittest.TestCase):
    def test_list_providers(self):
        from core.providers import ProviderRegistry
        providers = ProviderRegistry.list_providers()
        self.assertIn("ollama", providers)
        self.assertIn("openai_compat", providers)
        self.assertIn("anthropic", providers)

    def test_get_provider(self):
        from core.providers import ProviderRegistry
        OllamaCls = ProviderRegistry.get("ollama")
        self.assertIsNotNone(OllamaCls)

    def test_unknown_provider_raises(self):
        from core.providers import ProviderRegistry
        with self.assertRaises(ValueError):
            ProviderRegistry.get("unknown")


class TestSecurity(unittest.TestCase):
    def test_generate_api_key(self):
        from core.security import generate_api_key
        key = generate_api_key()
        self.assertTrue(key.startswith("tb_"))
        self.assertEqual(len(key), 66)  # tb_ + 64 hex chars

    def test_hash_api_key(self):
        from core.security import hash_api_key, verify_api_key
        key = "tb_test_key_12345"
        hashed = hash_api_key(key)
        self.assertTrue(verify_api_key(key, hashed))
        self.assertFalse(verify_api_key("wrong_key", hashed))

    def test_security_headers(self):
        from core.security import security_headers
        headers = security_headers()
        self.assertIn("Content-Security-Policy", headers)
        self.assertIn("X-Frame-Options", headers)


class TestNotifications(unittest.TestCase):
    def setUp(self):
        self.store = NotificationStore(Path("/tmp/test_notifications.jsonl"))

    def tearDown(self):
        if self.store.path.exists():
            self.store.path.unlink()

    def test_add_notification(self):
        from core.notifications import Notification
        n = Notification(id="n1", type="info", title="Test", message="Hello")
        self.store.add(n)
        items = self.store.list()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Test")


class TestWebhooks(unittest.TestCase):
    def setUp(self):
        self.ingest = WebhookIngest(secret="test_secret")

    def tearDown(self):
        if self.ingest.events_log.exists():
            self.ingest.events_log.unlink()

    def test_ingest_event(self):
        event = self.ingest.ingest("test_event", {"foo": "bar"}, "test_source")
        self.assertEqual(event["type"], "test_event")
        self.assertEqual(event["source"], "test_source")

    def test_verify_signature(self):
        import json
        payload = json.dumps({"test": True}).encode()
        sig = self.ingest.signature(payload)
        self.assertTrue(self.ingest.verify_signature(payload, sig))


class TestAnalytics(unittest.TestCase):
    def setUp(self):
        self.analytics = Analytics()

    def test_track_event(self):
        self.analytics.track("test_event", {"foo": "bar"})
        stats = self.analytics.get_stats()
        self.assertGreater(stats["total_events"], 0)

    def test_get_stats(self):
        self.analytics.track("job_created")
        self.analytics.track("job_completed")
        stats = self.analytics.get_stats()
        self.assertEqual(stats["jobs_created"], 1)
        self.assertEqual(stats["jobs_completed"], 1)


if __name__ == "__main__":
    unittest.main()
