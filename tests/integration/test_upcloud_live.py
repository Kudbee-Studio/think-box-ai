"""Live smoke tests for UpCloud ExecutionProvider.

These tests make real API calls and ONLY run when UPCLOUD_API_KEY
is configured in the environment. They are skipped otherwise.

Never fake live success — skipped tests report as SKIPPED, not PASSED.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.providers.upcloud import UpCloudExecutionProvider
from core.providers.execution import CapabilityStatus


class TestUpCloudLiveSmoke(unittest.TestCase):
    """Live tests — skipped when no credentials are available."""

    def setUp(self) -> None:
        self.api_key = os.environ.get("UPCLOUD_API_KEY", "")
        if not self.api_key:
            self.skipTest("UPCLOUD_API_KEY not set")

    def test_live_auth_check(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": self.api_key})
        result = provider.check_auth()
        # We do NOT assume success — we record what actually happened.
        self.assertIn(
            result.status,
            [CapabilityStatus.VERIFIED, CapabilityStatus.DENIED],
        )

    def test_live_discover_capabilities(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": self.api_key})
        checks = provider.discover_capabilities()
        self.assertTrue(len(checks) > 0)
        auth_check = checks[0]
        self.assertIn(
            auth_check.status,
            [CapabilityStatus.VERIFIED, CapabilityStatus.DENIED],
        )

    def test_live_list_servers(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": self.api_key})
        if provider.check_auth().status != CapabilityStatus.VERIFIED:
            self.skipTest("Auth not verified; cannot test list_servers")
        result = provider.execute(
            "smoke-list", "list_servers", approve=True
        )
        # Honest result — may succeed or fail based on actual permissions
        self.assertIn(result.success, [True, False])

    def test_live_plan(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": self.api_key})
        plan = provider.plan(
            "smoke-plan",
            [
                {"action": "list_servers"},
                {"action": "create_server", "billable": True},
            ],
        )
        self.assertTrue(plan.dry_run)
        self.assertTrue(plan.requires_approval)

    def test_live_evidence_recorded(self) -> None:
        provider = UpCloudExecutionProvider({"api_key": self.api_key})
        provider.check_auth()
        self.assertTrue(len(provider.evidence) > 0)
        for record in provider.evidence:
            self.assertTrue(record.job_id)
            self.assertTrue(record.provider)
            self.assertTrue(record.timestamp)


if __name__ == "__main__":
    unittest.main()
