from __future__ import annotations

import unittest

from thinkbox.pipeline_dashboard import PIPELINE_FOUNDER_MERGE_CAPABILITY
from thinkbox.pipeline_governance_rotation import issue_rotated_token


class TestGovernanceRotation(unittest.TestCase):
    def test_issue_and_reject_stale(self) -> None:
        out = issue_rotated_token(
            signing_key="rot-key",
            agent_id="pipeline-founder-gate",
            capabilities=[PIPELINE_FOUNDER_MERGE_CAPABILITY],
        )
        self.assertTrue(out["token_issued"])
        self.assertTrue(out["stale_rejected"])


if __name__ == "__main__":
    unittest.main()
