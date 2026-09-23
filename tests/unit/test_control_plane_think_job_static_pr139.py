"""Static asset contracts for PR #139 receipt multiplex UI."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path("public/control-plane")


class TestThinkJobStaticPr139(unittest.TestCase):
    def test_html_receipt_and_multiplex(self) -> None:
        html = (ROOT / "think_job_status.html").read_text(encoding="utf-8")
        self.assertIn("receiptId", html)
        self.assertIn("Jobs digest", html)
        self.assertIn("JobsDigestMultiplexer", html)
        self.assertIn("PR #139", html)

    def test_client_receipt_watch_exports(self) -> None:
        js = (ROOT / "think_job_status_client.js").read_text(encoding="utf-8")
        self.assertIn("watchReceipt", js)
        self.assertIn("JobsDigestMultiplexer", js)
        self.assertIn("resolveWatchTarget", js)
        self.assertIn("by-receipt", js)


if __name__ == "__main__":
    unittest.main()
