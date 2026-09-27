"""Static asset contracts for PR #140 deep-link + shared etag."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path("public/control-plane")


class TestControlPlaneStaticPr140(unittest.TestCase):
    def test_shared_etag_scripts_wired(self) -> None:
        for page in ("think_job_status.html", "receipts.html", "index.html", "pipeline_dashboard.html"):
            html = (ROOT / page).read_text(encoding="utf-8")
            self.assertIn("control_plane_etag_store.js", html)
            self.assertIn("getSharedEtagStore", html)

    def test_receipts_deep_link(self) -> None:
        html = (ROOT / "receipts.html").read_text(encoding="utf-8")
        self.assertIn("control_plane_deep_link.js", html)
        self.assertIn("Watch status", html)
        self.assertIn("PR #140", html)

    def test_think_job_boot_deep_link(self) -> None:
        html = (ROOT / "think_job_status.html").read_text(encoding="utf-8")
        self.assertIn("applyDeepLinkFromLocation", html)
        self.assertIn("control_plane_deep_link.js", html)

    def test_load_perf_persists_shared_store(self) -> None:
        js = (ROOT / "load_perf.js").read_text(encoding="utf-8")
        self.assertIn("__tbPersist", js)

    def test_etag_store_module(self) -> None:
        js = (ROOT / "control_plane_etag_store.js").read_text(encoding="utf-8")
        self.assertIn("sessionStorage", js)
        self.assertIn("thinkbox.control_plane.etag_store.v1", js)


if __name__ == "__main__":
    unittest.main()
