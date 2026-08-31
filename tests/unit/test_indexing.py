"""Tests for local indexing system."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.indexing.database import init_db, reset_db, project_hash, get_db
from core.indexing.memory import ProjectMemory, SessionStore
from core.indexing.search import SearchEngine


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("/tmp/test_thinkbox.db")
        if self.db_path.exists():
            self.db_path.unlink()
        init_db(self.db_path)

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_project_hash_stable(self):
        h1 = project_hash("/tmp/test")
        h2 = project_hash("/tmp/test")
        self.assertEqual(h1, h2)

    def test_project_hash_different(self):
        h1 = project_hash("/tmp/a")
        h2 = project_hash("/tmp/b")
        self.assertNotEqual(h1, h2)


class TestSessionStore(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("/tmp/test_thinkbox.db")
        if self.db_path.exists():
            self.db_path.unlink()
        init_db(self.db_path)
        self.store = SessionStore("/tmp/test", db_path=self.db_path)

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_create_session(self):
        self.store.create_session("ses_001", "Test Session")
        session = self.store.get_session("ses_001")
        self.assertIsNotNone(session)
        self.assertEqual(session["title"], "Test Session")

    def test_add_message(self):
        self.store.create_session("ses_001", "Test")
        self.store.add_message("ses_001", "user", "Hello")
        messages = SearchEngine(self.db_path).read_session("ses_001")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "Hello")

    def test_list_sessions(self):
        self.store.create_session("ses_001", "Test 1")
        self.store.create_session("ses_002", "Test 2")
        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 2)


class TestProjectMemory(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("/tmp/test_thinkbox.db")
        if self.db_path.exists():
            self.db_path.unlink()
        init_db(self.db_path)
        self.pm = ProjectMemory("/tmp/test", db_path=self.db_path)

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_remember(self):
        self.pm.remember("key1", "value1")
        self.assertEqual(self.pm.get("key1"), "value1")

    def test_forget(self):
        self.pm.remember("key1", "value1")
        self.assertTrue(self.pm.forget("key1"))
        self.assertIsNone(self.pm.get("key1"))

    def test_correction(self):
        self.pm.save_correction("lang", "Python")
        corrections = self.pm.get_corrections()
        self.assertEqual(corrections["lang"], "Python")

    def test_environment(self):
        self.pm.save_environment("port", "8080")
        env = self.pm.get_environment()
        self.assertEqual(env["port"], "8080")


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("/tmp/test_thinkbox.db")
        if self.db_path.exists():
            self.db_path.unlink()
        init_db(self.db_path)
        self.engine = SearchEngine(self.db_path)
        self.store = SessionStore("/tmp/test", db_path=self.db_path)
        self.store.create_session("ses_001", "Deploy Session")
        self.store.add_message("ses_001", "user", "How do I deploy this project?")
        self.store.add_message("ses_001", "assistant", "Run docker build .")

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_search_messages(self):
        results = self.engine.search_messages("deploy", project="/tmp/test")
        self.assertGreater(len(results), 0)

    def test_read_session(self):
        messages = self.engine.read_session("ses_001")
        self.assertEqual(len(messages), 2)


if __name__ == "__main__":
    unittest.main()
