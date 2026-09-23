"""Static control-plane assets for Think Job status UI (PR #138)."""

from __future__ import annotations

import unittest
from pathlib import Path


class TestThinkJobStatusStatic(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path("public/control-plane")

    def test_html_includes_client_and_load_perf(self) -> None:
        html = (self.root / "think_job_status.html").read_text()
        self.assertIn("think_job_status_client.js", html)
        self.assertIn("load_perf.js", html)
        self.assertIn("TBThinkJobStatus", html)

    def test_client_exports_watcher(self) -> None:
        js = (self.root / "think_job_status_client.js").read_text()
        self.assertIn("ThinkJobStatusWatcher", js)
        self.assertIn("fetch", js)
        self.assertIn("degraded_poll", js)

    def test_index_links_think_jobs(self) -> None:
        index = (self.root / "index.html").read_text()
        self.assertIn("think_job_status.html", index)

    def test_pipeline_links_think_jobs(self) -> None:
        pipe = (self.root / "pipeline_dashboard.html").read_text()
        self.assertIn("think_job_status.html", pipe)

    def test_html_has_stop_watch(self) -> None:
        html = (self.root / "think_job_status.html").read_text()
        self.assertIn("btnStop", html)


if __name__ == "__main__":
    unittest.main()
