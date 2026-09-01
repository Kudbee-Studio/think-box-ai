"""Unit tests for security fixes."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class TestAuthentication(unittest.TestCase):
    def test_default_api_keys_rejected(self):
        from backend.security import get_api_keys
        with patch.dict(os.environ, {}, clear=True):
            keys = get_api_keys()
            self.assertEqual(keys, set())

    def test_valid_api_key_accepted(self):
        from backend.security import get_api_keys
        with patch.dict(os.environ, {"THINKBOX_API_KEY": "tb_secure_key_12345"}):
            keys = get_api_keys()
            self.assertIn("tb_secure_key_12345", keys)

    def test_multiple_api_keys_accepted(self):
        from backend.security import get_api_keys
        with patch.dict(os.environ, {"THINKBOX_API_KEYS": "key1, key2, key3"}):
            keys = get_api_keys()
            self.assertEqual(keys, {"key1", "key2", "key3"})

    def test_validate_api_keys_exits_without_keys(self):
        from backend.security import validate_api_keys_or_exit
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                validate_api_keys_or_exit()
            self.assertEqual(ctx.exception.code, 1)

    def test_validate_api_keys_exits_with_default_key(self):
        from backend.security import validate_api_keys_or_exit
        with patch.dict(os.environ, {"THINKBOX_API_KEY": "changeme-production-key"}):
            with self.assertRaises(SystemExit) as ctx:
                validate_api_keys_or_exit()
            self.assertEqual(ctx.exception.code, 1)

    def test_validate_api_keys_succeeds_with_valid_key(self):
        from backend.security import validate_api_keys_or_exit
        with patch.dict(os.environ, {"THINKBOX_API_KEY": "tb_valid_key_12345"}):
            keys = validate_api_keys_or_exit()
            self.assertIn("tb_valid_key_12345", keys)


class TestPathJail(unittest.TestCase):
    def test_path_jail_blocks_traversal(self):
        from core.tools.fs import _jail_path
        with self.assertRaises(PermissionError):
            _jail_path("../../../etc/passwd")

    def test_path_jail_blocks_absolute_outside(self):
        from core.tools.fs import _jail_path
        with self.assertRaises(PermissionError):
            _jail_path("/etc/passwd")

    def test_path_jail_allows_relative_within(self):
        from core.tools.fs import _jail_path
        resolved = _jail_path("data/test.txt")
        self.assertIsNotNone(resolved)


class TestShellExecution(unittest.TestCase):
    def test_blocked_patterns(self):
        from core.tools.shell_exec import BLOCKED_PATTERNS
        self.assertIn("|", BLOCKED_PATTERNS)
        self.assertIn(";", BLOCKED_PATTERNS)
        self.assertIn("&&", BLOCKED_PATTERNS)
        self.assertIn("rm -rf /", BLOCKED_PATTERNS)

    def test_allowed_commands(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertIn("ls", ALLOWED_COMMANDS)
        self.assertIn("cat", ALLOWED_COMMANDS)
        self.assertIn("git", ALLOWED_COMMANDS)
        self.assertIn("python3", ALLOWED_COMMANDS)

    def test_blocked_command_not_in_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertNotIn("rm", ALLOWED_COMMANDS)
        self.assertNotIn("chmod", ALLOWED_COMMANDS)
        self.assertNotIn("sudo", ALLOWED_COMMANDS)


class TestInputValidation(unittest.TestCase):
    def test_validate_goal_rejects_empty(self):
        from backend.validation import validate_goal
        valid, result = validate_goal("")
        self.assertFalse(valid)

    def test_validate_goal_rejects_too_long(self):
        from backend.validation import validate_goal
        valid, result = validate_goal("x" * 20000)
        self.assertFalse(valid)

    def test_validate_goal_accepts_valid(self):
        from backend.validation import validate_goal
        valid, result = validate_goal("Research SOL price")
        self.assertTrue(valid)

    def test_validate_path_rejects_traversal(self):
        from backend.validation import validate_path
        valid, result = validate_path("../../../etc/passwd")
        self.assertFalse(valid)

    def test_validate_path_rejects_absolute(self):
        from backend.validation import validate_path
        valid, result = validate_path("/etc/passwd")
        self.assertFalse(valid)

    def test_validate_iterations_caps(self):
        from backend.validation import validate_iterations
        result = validate_iterations(500)
        self.assertEqual(result, 100)

    def test_validate_api_key_format(self):
        from backend.validation import validate_api_key
        self.assertTrue(validate_api_key("tb_abc123def456ghi789jkl012mno345pq"))
        self.assertFalse(validate_api_key("short"))
        self.assertFalse(validate_api_key(""))
        self.assertFalse(validate_api_key("has spaces"))


class TestDatabaseIndexing(unittest.TestCase):
    def test_audit_db_has_indexes(self):
        import sqlite3
        from backend.audit_storage import _get_db
        conn = _get_db()
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='audit_log'"
        ).fetchall()
        index_names = {r[0] for r in indexes}
        self.assertIn("idx_audit_timestamp", index_names)
        self.assertIn("idx_audit_action", index_names)
        conn.close()


if __name__ == "__main__":
    unittest.main()
