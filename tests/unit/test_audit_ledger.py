"""Hermetic tests for scripts/audit_ledger.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "audit_ledger.py"


class TestAuditLedgerHermetic(unittest.TestCase):
    """Exercise audit ledger without mutating repo docs/audit."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "audit"
        self.root.mkdir()
        (self.root / "checked").mkdir()
        (self.root / "AUDIT_INDEX.json").write_text(
            json.dumps({"version": 1, "passes": [], "areas": ["tests"]}),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(SCRIPT), "--root", str(self.root), *args]
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def test_mark_checked_and_list(self) -> None:
        proc = self._run(
            "mark-checked",
            "tests",
            "foo.py",
            "pass",
            "--checker",
            "unit",
            "--commit",
            "abc123",
            "--json",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["path"], "foo.py")
        self.assertEqual(data["status"], "pass")

        listed = self._run("list", "--json")
        self.assertEqual(listed.returncode, 0)
        rows = json.loads(listed.stdout)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["area"], "tests")

    def test_mark_checked_replaces_same_path(self) -> None:
        self._run("mark-checked", "tests", "bar.py", "warn", "--commit", "c1")
        self._run("mark-checked", "tests", "bar.py", "pass", "--commit", "c2")
        listed = json.loads(self._run("list", "--json").stdout)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["status"], "pass")
        self.assertEqual(listed[0]["commit_sha"], "c2")

    def test_stale_empty_when_no_items(self) -> None:
        proc = self._run("stale", "--json", "--repo-root", str(REPO_ROOT))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout), [])

    def test_importable_api(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("audit_ledger", SCRIPT)
        assert spec and spec.loader
        audit_ledger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit_ledger)

        entry = audit_ledger.mark_checked(
            self.root,
            "tests",
            "api.py",
            "skip",
            commit_sha="deadbeef",
            checker="unit",
            finding_ids=["F002"],
            notes="",
        )
        self.assertEqual(entry["finding_ids"], ["F002"])


if __name__ == "__main__":
    unittest.main()
