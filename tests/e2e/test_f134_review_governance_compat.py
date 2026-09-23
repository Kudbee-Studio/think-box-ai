"""PR #134 review: governance status remains compatible with PR #132 fields."""

from __future__ import annotations

import unittest

from tests.e2e.api_run_hermetic import auth_headers, hermetic_run_client


class TestGovernanceCompatAfterJobStatus(unittest.TestCase):
    def test_governance_status_still_has_ledger_fields(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.get("/api/v1/run/governance/status", headers=auth_headers())
        body = r.json()
        self.assertIn("ledger_verified", body)
        self.assertIn("think_job_status", body)
        self.assertIn("receipt_snapshot", body)


if __name__ == "__main__":
    unittest.main()
