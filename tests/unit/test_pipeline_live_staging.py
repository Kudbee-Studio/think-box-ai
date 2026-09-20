from __future__ import annotations

import os
import unittest
from unittest import mock

from thinkbox.pipeline_dashboard import compute_founder_merge_proof, verify_founder_merge_proof
from thinkbox.pipeline_live_staging import inspect_staging_config, staging_db_isolation_ok


class TestLiveStaging(unittest.TestCase):
    def test_preflight_missing_all(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = inspect_staging_config()
        self.assertFalse(cfg["ready_for_live_drill"])
        self.assertIn("THINKBOX_PIPELINE_STAGING", cfg["missing_prerequisites"])

    def test_staging_db_isolation_requires_staging_segment(self) -> None:
        with mock.patch.dict(os.environ, {"THINKBOX_PIPELINE_STAGING": "1"}, clear=False):
            ok, _ = staging_db_isolation_ok("data/thinkboxmd/db/org_memory_receipts.db")
        self.assertFalse(ok)

    def test_founder_proof_pr_bound(self) -> None:
        key = "test-proof-key"
        p108 = compute_founder_merge_proof(108, key)
        self.assertTrue(verify_founder_merge_proof(108, key, p108))
        self.assertFalse(verify_founder_merge_proof(109, key, p108))


if __name__ == "__main__":
    unittest.main()
