"""Auth helpers for Think Job status UI (PR #138)."""

from __future__ import annotations

import unittest

from thinkbox.think_job_status_ui import api_headers


class TestThinkJobStatusUiAuth(unittest.TestCase):
    def test_api_headers_require_key(self) -> None:
        with self.assertRaises(ValueError):
            api_headers("")

    def test_api_headers_x_api_key(self) -> None:
        h = api_headers("secret-key")
        self.assertEqual(h["X-API-Key"], "secret-key")

    def test_api_headers_bearer(self) -> None:
        h = api_headers("", bearer="tok")
        self.assertIn("Bearer", h["Authorization"])


if __name__ == "__main__":
    unittest.main()
