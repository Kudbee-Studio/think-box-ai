"""PR #109 contract smoke tests — governance invariants."""

from __future__ import annotations

import unittest
from pathlib import Path


class TestPR109Contract(unittest.TestCase):
    def test_contract_document_exists(self) -> None:
        path = Path("docs/contracts/PR109_PIPELINE_CONTRACT.md")
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("Never", text)
        self.assertIn("THINKBOX_FOUNDER_MERGE_PROOF_KEY", text)
        self.assertIn("LIVE_VERIFIED", text)

    def test_no_github_merge_in_pipeline_dashboard_module(self) -> None:
        src = Path("thinkbox/pipeline_dashboard.py").read_text(encoding="utf-8")
        self.assertNotIn("merge_pull_request", src)
        self.assertNotIn("repos.merge", src)


if __name__ == "__main__":
    unittest.main()
