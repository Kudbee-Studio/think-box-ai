"""Unit tests for hermetic control-plane clients (PR #154)."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_hermetic_clients import (
    HermeticGovernanceClient,
    HermeticOrchestrationClient,
)


class TestHermeticClients(unittest.IsolatedAsyncioTestCase):
    async def test_governance_denies_without_token(self) -> None:
        client = HermeticGovernanceClient(None)
        decision = await client.check_admission("demo", {})
        self.assertFalse(decision.allowed)

    async def test_governance_allows_with_token(self) -> None:
        client = HermeticGovernanceClient("tok")
        decision = await client.check_admission("demo", {})
        self.assertTrue(decision.allowed)

    async def test_governance_denies_live_mercury_flag(self) -> None:
        client = HermeticGovernanceClient("tok")
        decision = await client.check_admission("demo", {"live_mercury": True})
        self.assertFalse(decision.allowed)

    async def test_orchestration_grant(self) -> None:
        orch = HermeticOrchestrationClient()
        grant = await orch.request_capacity({})
        self.assertTrue(grant.granted)
        self.assertTrue(grant.allocation_id.startswith("alloc-hermetic-"))


if __name__ == "__main__":
    unittest.main()
