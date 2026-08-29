"""Tests for error codes."""

from __future__ import annotations

import unittest

from core.foundation.error_codes import ErrorCode, error_dict


class TestErrorCodes(unittest.TestCase):
    def test_error_code_format(self):
        self.assertTrue(ErrorCode.EXEC_EMPTY_COMMAND.startswith("EXEC_"))
        self.assertTrue(ErrorCode.TOKEN_NOT_FOUND.startswith("TOKEN_"))
        self.assertTrue(ErrorCode.BOX_NOT_FOUND.startswith("BOX_"))

    def test_error_dict_structure(self):
        result = error_dict(ErrorCode.EXEC_TIMEOUT, "Command timed out", timeout=30)
        self.assertEqual(result["error"], "EXEC_1001")
        self.assertEqual(result["message"], "Command timed out")
        self.assertEqual(result["details"]["timeout"], 30)

    def test_all_codes_unique(self):
        codes = [e.value for e in ErrorCode]
        self.assertEqual(len(codes), len(set(codes)))

    def test_error_code_is_string(self):
        self.assertIsInstance(ErrorCode.BOX_NOT_FOUND, str)
        self.assertEqual(ErrorCode.BOX_NOT_FOUND, "BOX_4000")


if __name__ == "__main__":
    unittest.main()
