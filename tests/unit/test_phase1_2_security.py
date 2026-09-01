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
            with patch.dict(os.environ, {"THINKBOX_API_KEY": key}, clear=True):
                with self.assertRaises(SystemExit):
                    validate_api_keys_or_exit()

    def test_valid_api_key_succeeds(self):
        from backend.security import validate_api_keys_or_exit
        with patch.dict(os.environ, {"THINKBOX_API_KEY": "tb_secure_key_12345"}, clear=True):
            keys = validate_api_keys_or_exit()
            self.assertIn("tb_secure_key_12345", keys)

    def test_get_api_keys_rejects_defaults(self):
        from backend.security import get_api_keys
        with patch.dict(os.environ, {"THINKBOX_API_KEY": "changeme-production-key"}, clear=True):
            keys = get_api_keys()
            self.assertEqual(keys, set())

    def test_get_api_keys_accepts_valid(self):
        from backend.security import get_api_keys
        with patch.dict(os.environ, {"THINKBOX_API_KEY": "tb_valid_key"}, clear=True):
            keys = get_api_keys()
            self.assertIn("tb_valid_key", keys)

    def test_multiple_keys_filtered(self):
        from backend.security import get_api_keys
        with patch.dict(os.environ, {"THINKBOX_API_KEYS": "key1, changeme, key2"}, clear=True):
            keys = get_api_keys()
            self.assertEqual(keys, {"key1", "key2"})


class TestPathJailHardening(unittest.TestCase):
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


class TestShellExecutionHardening(unittest.TestCase):
    def test_pipe_blocked(self):
        from core.tools.shell_exec import BLOCKED_PATTERNS
        self.assertIn("|", BLOCKED_PATTERNS)

    def test_semicolon_blocked(self):
        from core.tools.shell_exec import BLOCKED_PATTERNS
        self.assertIn(";", BLOCKED_PATTERNS)

    def test_rm_rf_root_blocked(self):
        from core.tools.shell_exec import BLOCKED_PATTERNS
        self.assertIn("rm -rf /", BLOCKED_PATTERNS)

    def test_ls_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertIn("ls", ALLOWED_COMMANDS)

    def test_cat_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertIn("cat", ALLOWED_COMMANDS)

    def test_rm_not_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertNotIn("rm", ALLOWED_COMMANDS)

    def test_curl_not_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertNotIn("curl", ALLOWED_COMMANDS)

    def test_sudo_not_allowed(self):
        from core.tools.shell_exec import ALLOWED_COMMANDS
        self.assertNotIn("sudo", ALLOWED_COMMANDS)

    def test_timeout_capped(self):
        from core.tools.shell_exec import MAX_TIMEOUT
        self.assertEqual(MAX_TIMEOUT, 60)


class TestWebSocketAuth(unittest.TestCase):
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


class TestInputValidation(unittest.TestCase):
    def test_validate_goal_rejects_empty(self):
        from backend.validation import validate_goal
        valid, result = validate_goal("")
        self.assertFalse(valid)

    def test_validate_goal_accepts_valid(self):
        from backend.validation import validate_goal
        valid, result = validate_goal("Research SOL price")
        self.assertTrue(valid)

    def test_validate_path_rejects_traversal(self):
        from backend.validation import validate_path
        valid, result = validate_path("../../../etc/passwd")
        self.assertFalse(valid)

    def test_validate_iterations_caps(self):
        from backend.validation import validate_iterations
        result = validate_iterations(500)
        self.assertEqual(result, 100)


class TestDatabaseIndexes(unittest.TestCase):
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
