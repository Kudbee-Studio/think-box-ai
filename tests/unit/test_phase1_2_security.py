"""Phase 1 & 2 Security Verification Tests.

Comprehensive async pytest integration tests verifying all security patches.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

if "fastapi" not in sys.modules:
    sys.modules["fastapi"] = MagicMock()
    sys.modules["fastapi.middleware"] = MagicMock()
    sys.modules["fastapi.middleware.cors"] = MagicMock()
    sys.modules["starlette"] = MagicMock()
    sys.modules["starlette.middleware"] = MagicMock()
    sys.modules["starlette.middleware.base"] = MagicMock()


class TestStrictAuthEnforcement(unittest.TestCase):
    """Test C1: Strict startup authentication enforcement."""

    def test_missing_env_var_raises_system_exit(self):
        from backend.security import validate_api_keys_or_exit
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                validate_api_keys_or_exit()
            self.assertEqual(ctx.exception.code, 1)

    def test_default_fallback_keys_rejected(self):
        from backend.security import validate_api_keys_or_exit
        default_keys = [
            "changeme-production-key",
            "changeme",
            "test",
            "admin",
            "password",
        ]
        for key in default_keys:
            with patch.dict(os.environ, {"THINKBOX_API_KEY": key}):
                with self.assertRaises(SystemExit):
                    validate_api_keys_or_exit()

    def test_valid_api_key_succeeds(self):
        from backend.security import validate_api_keys_or_exit
        with patch.dict(os.environ, {"THINKBOX_API_KEY": "tb_secure_key_12345"}):
            keys = validate_api_keys_or_exit()
            self.assertIn("tb_secure_key_12345", keys)

    def test_get_api_keys_rejects_defaults(self):
        from backend.security import get_api_keys
        with patch.dict(os.environ, {"THINKBOX_API_KEY": "changeme-production-key"}):
            keys = get_api_keys()
            self.assertEqual(keys, set())

    def test_get_api_keys_accepts_valid(self):
        from backend.security import get_api_keys
        with patch.dict(os.environ, {"THINKBOX_API_KEY": "tb_valid_key"}):
            keys = get_api_keys()
            self.assertIn("tb_valid_key", keys)

    def test_multiple_keys_filtered(self):
        from backend.security import get_api_keys
        with patch.dict(os.environ, {"THINKBOX_API_KEYS": "key1, changeme, key2"}):
            keys = get_api_keys()
            self.assertEqual(keys, {"key1", "key2"})


class TestPathJailHardening(unittest.TestCase):
    """Test C7: Path traversal prevention."""

    def test_blocks_relative_traversal(self):
        from backend.plugins.filesystem import _jail_path
        with self.assertRaises(PermissionError):
            _jail_path("../../../etc/passwd")

    def test_blocks_deep_traversal(self):
        from backend.plugins.filesystem import _jail_path
        with self.assertRaises(PermissionError):
            _jail_path("foo/../../../../etc/shadow")

    def test_blocks_absolute_outside(self):
        from backend.plugins.filesystem import _jail_path
        with self.assertRaises(PermissionError):
            _jail_path("/etc/passwd")

    def test_blocks_root_ssh(self):
        from backend.plugins.filesystem import _jail_path
        with self.assertRaises(PermissionError):
            _jail_path("/root/.ssh/id_rsa")

    def test_allows_relative_within(self):
        from backend.plugins.filesystem import _jail_path
        resolved = _jail_path("data/test.txt")
        self.assertIsNotNone(resolved)

    def test_allows_nested_relative(self):
        from backend.plugins.filesystem import _jail_path
        resolved = _jail_path("data/subdir/file.json")
        self.assertIsNotNone(resolved)


class TestShellExecutionHardening(unittest.TestCase):
    """Test C2: Shell execution sandboxing."""

    def test_pipe_blocked(self):
        from core.tools.shell_exec import BLOCKED_PATTERNS
        self.assertIn("|", BLOCKED_PATTERNS)

    def test_semicolon_blocked(self):
        from core.tools.shell_exec import BLOCKED_PATTERNS
        self.assertIn(";", BLOCKED_PATTERNS)

    def test_and_blocked(self):
        from core.tools.shell_exec import BLOCKED_PATTERNS
        self.assertIn("&&", BLOCKED_PATTERNS)

    def test_or_blocked(self):
        from core.tools.shell_exec import BLOCKED_PATTERNS
        self.assertIn("||", BLOCKED_PATTERNS)

    def test_backtick_blocked(self):
        from core.tools.shell_exec import BLOCKED_PATTERNS
        self.assertIn("`", BLOCKED_PATTERNS)

    def test_rm_rf_root_blocked(self):
        from core.tools.shell_exec import BLOCKED_PATTERNS
        self.assertIn("rm -rf /", BLOCKED_PATTERNS)

    def test_redirect_blocked(self):
        from core.tools.shell_exec import BLOCKED_PATTERNS
        self.assertIn(">", BLOCKED_PATTERNS)

    def test_ls_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertIn("ls", ALLOWED_COMMANDS)

    def test_cat_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertIn("cat", ALLOWED_COMMANDS)

    def test_git_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertIn("git", ALLOWED_COMMANDS)

    def test_python3_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertIn("python3", ALLOWED_COMMANDS)

    def test_rm_not_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertNotIn("rm", ALLOWED_COMMANDS)

    def test_chmod_not_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertNotIn("chmod", ALLOWED_COMMANDS)

    def test_sudo_not_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertNotIn("sudo", ALLOWED_COMMANDS)

    def test_curl_not_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertNotIn("curl", ALLOWED_COMMANDS)

    def test_timeout_capped(self):
        from core.tools.shell_exec import MAX_TIMEOUT
        self.assertEqual(MAX_TIMEOUT, 60)


class TestWebSocketAuth(unittest.TestCase):
    """Test C6: WebSocket authentication."""

    def test_valid_token_accepted(self):
        from backend.security import validate_ws_token
        result = validate_ws_token(
            {"token": "valid_key"},
            {},
            {"valid_key"}
        )
        self.assertTrue(result)

    def test_invalid_token_rejected(self):
        from backend.security import validate_ws_token
        result = validate_ws_token(
            {"token": "invalid_key"},
            {},
            {"valid_key"}
        )
        self.assertFalse(result)

    def test_missing_token_rejected(self):
        from backend.security import validate_ws_token
        result = validate_ws_token({}, {}, {"valid_key"})
        self.assertFalse(result)

    def test_header_token_accepted(self):
        from backend.security import validate_ws_token
        result = validate_ws_token(
            {},
            {"X-API-Key": "valid_key"},
            {"valid_key"}
        )
        self.assertTrue(result)

    def test_query_param_api_key_accepted(self):
        from backend.security import validate_ws_token
        result = validate_ws_token(
            {"api_key": "valid_key"},
            {},
            {"valid_key"}
        )
        self.assertTrue(result)

    def test_empty_keyset_rejects_all(self):
        from backend.security import validate_ws_token
        result = validate_ws_token(
            {"token": "any_key"},
            {},
            set()
        )
        self.assertFalse(result)


class TestInputValidation(unittest.TestCase):
    """Test input validation functions."""

    def test_validate_goal_rejects_empty(self):
        from backend.validation import validate_goal
        valid, result = validate_goal("")
        self.assertFalse(valid)

    def test_validate_goal_rejects_whitespace(self):
        from backend.validation import validate_goal
        valid, result = validate_goal("   ")
        self.assertFalse(valid)

    def test_validate_goal_rejects_too_long(self):
        from backend.validation import validate_goal
        valid, result = validate_goal("x" * 20000)
        self.assertFalse(valid)

    def test_validate_goal_accepts_valid(self):
        from backend.validation import validate_goal
        valid, result = validate_goal("Research SOL price")
        self.assertTrue(valid)
        self.assertEqual(result, "Research SOL price")

    def test_validate_path_rejects_traversal(self):
        from backend.validation import validate_path
        valid, result = validate_path("../../../etc/passwd")
        self.assertFalse(valid)

    def test_validate_path_rejects_absolute(self):
        from backend.validation import validate_path
        valid, result = validate_path("/etc/passwd")
        self.assertFalse(valid)

    def test_validate_path_accepts_relative(self):
        from backend.validation import validate_path
        valid, result = validate_path("data/test.txt")
        self.assertTrue(valid)

    def test_validate_iterations_caps(self):
        from backend.validation import validate_iterations
        self.assertEqual(validate_iterations(500), 100)
        self.assertEqual(validate_iterations(0), 1)
        self.assertEqual(validate_iterations(-5), 1)

    def test_validate_api_key_format(self):
        from backend.validation import validate_api_key
        self.assertTrue(validate_api_key("tb_abc123def456ghi789jkl012mno345pq"))
        self.assertFalse(validate_api_key("short"))
        self.assertFalse(validate_api_key(""))
        self.assertFalse(validate_api_key("has spaces"))
        self.assertFalse(validate_api_key("a" * 300))


class TestAsyncSQLiteConcurrency(unittest.TestCase):
    """Test async SQLite concurrency for audit storage."""

    def test_concurrent_writes_no_locks(self):
        from backend.audit_storage import _get_db, record_audit
        import threading

        errors = []
        db_path = Path("data/audit.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        def write_audit(i):
            try:
                record_audit(f"test_action_{i}", f"actor_{i}", "success", {"index": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_audit, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Database lock errors: {errors}")


class TestDatabaseIndexes(unittest.TestCase):
    """Test that all required database indexes exist."""

    def test_audit_log_indexes_exist(self):
        import sqlite3
        from backend.audit_storage import _get_db
        conn = _get_db()
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='audit_log'"
        ).fetchall()
        index_names = {r[0] for r in indexes}
        conn.close()

        self.assertIn("idx_audit_timestamp", index_names)
        self.assertIn("idx_audit_action", index_names)
        self.assertIn("idx_audit_actor", index_names)
        self.assertIn("idx_audit_outcome", index_names)


if __name__ == "__main__":
    unittest.main()
