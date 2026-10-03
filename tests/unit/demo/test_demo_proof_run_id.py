"""GET /demo/runs/{run_id}/proof writes files under data/proofs/<run_id>; run_id must not leave that folder.

The router is not mounted in backend.main today; this keeps it safe if it is.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi import HTTPException

    from backend.api.v1.demo_runs import get_run_proof
except ImportError as exc:  # pragma: no cover - needs fastapi
    raise unittest.SkipTest(f"fastapi not installed: {exc}") from exc


class TestDemoProofRunId(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)

    def tearDown(self) -> None:
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_dot_segments_and_odd_names_are_refused_and_write_nothing(self) -> None:
        for run_id in ("..", ".", "...", "a b", "x\ny", ""):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(get_run_proof(run_id))
            self.assertEqual(ctx.exception.status_code, 400, run_id)
        self.assertFalse((Path(self.tmp.name) / "data").exists(), "a refused run_id still wrote files")

    def test_a_normal_run_id_writes_under_data_proofs(self) -> None:
        bundle = asyncio.run(get_run_proof("demo-001"))
        self.assertEqual(bundle["evidence_label"], "simulated")
        self.assertTrue((Path(self.tmp.name) / "data" / "proofs" / "demo-001").is_dir())


if __name__ == "__main__":
    unittest.main()
