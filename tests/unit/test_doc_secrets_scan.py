"""Hermetic tests for scripts/scan_doc_secrets.py."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "scan_doc_secrets.py"


class TestDocSecretsScan(unittest.TestCase):
    def test_repo_docs_clean(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_detects_ucat_in_temp_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = root / "AGENTS.md"
            agents.write_text(
                "UPCLOUD_API=ucat_Y8X1T01M2NP0SMDK6073EBBCP7\n",
                encoding="utf-8",
            )
            # Import module functions with patched paths via subprocess env hack:
            # run inline check on one file using same patterns as script.
            import importlib.util

            spec = importlib.util.spec_from_file_location("scan_doc_secrets", SCRIPT)
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(mod)

            hits = mod.scan_file(agents)
            self.assertTrue(hits)

    def test_redacted_placeholder_allowed(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("scan_doc_secrets", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        scan_file = mod.scan_file

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "STATUS.md"
            path.write_text(
                "THINKBOX_UPCLOUD_API_TOKEN=REDACTED_THINKBOX_UPCLOUD_API_TOKEN\n",
                encoding="utf-8",
            )
            self.assertEqual(scan_file(path), [])


if __name__ == "__main__":
    unittest.main()
