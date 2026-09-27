"""Governance snapshot includes stream metadata (PR #137)."""

from __future__ import annotations

import unittest

from backend.api.v1.run_job_status import job_status_snapshot_for_governance


class TestGovernanceStreamSnapshot(unittest.TestCase):
    def test_snapshot_has_stream_block(self) -> None:
        snap = job_status_snapshot_for_governance()
        self.assertIn("stream", snap)
        self.assertIn("stream_schema_version", snap["stream"])


if __name__ == "__main__":
    unittest.main()
