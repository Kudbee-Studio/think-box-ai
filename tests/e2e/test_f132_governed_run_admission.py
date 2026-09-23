"""PR #132 — governed verified ``POST /api/v1/run`` admission + ledger (hermetic).

Wires ``GovernedEngine`` / F023 verified runner into the HTTP background task.
Mock provider only; no Mercury HTTP.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from starlette.testclient import TestClient

from backend.api.v1.run_governed import (
    DEFAULT_RUN_CAPABILITY,
    DEFAULT_VERIFIED_CAPABILITY,
    get_api_run_governance,
    parse_run_admission,
    reset_api_run_governance_for_tests,
)
from thinkbox.dashboard_state import DashboardCategory, DashboardEvent

from tests.e2e.api_run_hermetic import (
    auth_headers,
    events_matching,
    hermetic_agent_id,
    hermetic_governance_token,
    hermetic_run_client,
    hermetic_run_client_real_engine,
    run_payload,
)
from tests.e2e.hermetic_scaffold import (
    assert_hermetic_blob_has_no_secrets,
    assert_ledger_chain,
    isolated_dashboard_state,
    ledger_allowed_count,
    ledger_denied_count,
    subtask_spec,
)


class TestRunAdmissionParsing(unittest.TestCase):
    def test_parse_defaults_capability_goal_execute(self) -> None:
        ctx = parse_run_admission(
            agent_id=None,
            governance_token="tok",
            header_token=None,
            header_capability=None,
            capability=None,
            verified=False,
            subtasks=None,
        )
        self.assertEqual(ctx.capability, DEFAULT_RUN_CAPABILITY)

    def test_parse_verified_defaults_capability(self) -> None:
        ctx = parse_run_admission(
            agent_id="a1",
            governance_token="tok",
            header_token=None,
            header_capability=None,
            capability=None,
            verified=True,
            subtasks=[],
        )
        self.assertEqual(ctx.capability, DEFAULT_VERIFIED_CAPABILITY)

    def test_header_token_overrides_empty_body_token(self) -> None:
        ctx = parse_run_admission(
            agent_id="a1",
            governance_token=None,
            header_token="header-tok",
            header_capability=None,
            capability="goal:execute",
            verified=False,
            subtasks=None,
        )
        self.assertEqual(ctx.token_value, "header-tok")


class TestPostRunGovernanceFailClosed(unittest.TestCase):
    def _bare_client(self) -> TestClient:
        from backend.api.v1 import router as router_mod

        reset_api_run_governance_for_tests()
        router_mod.active_engines.clear()
        router_mod.active_governed_engines.clear()
        app = FastAPI()
        with patch.dict(os.environ, {"THINKBOX_API_KEY": "tb_hermetic_pr131_contract_key"}, clear=False):
            from backend.security import setup_security

            setup_security(app)
            app.include_router(router_mod.api_v1_router)
        return TestClient(app, raise_server_exceptions=False)

    def test_missing_governance_token_returns_403(self) -> None:
        with self._bare_client() as client:
            r = client.post(
                "/api/v1/run",
                json={"goal": "no token"},
                headers=auth_headers(),
            )
        self.assertEqual(r.status_code, 403)
        self.assertIn("governance_denied", r.text)

    def test_invalid_governance_token_returns_403(self) -> None:
        reset_api_run_governance_for_tests()
        gov = get_api_run_governance()
        gov.register_agent("bad-agent", ["goal:execute"])
        with self._bare_client() as client:
            r = client.post(
                "/api/v1/run",
                json=run_payload("bad token", governance_token="not-a-real-token"),
                headers=auth_headers(),
            )
        self.assertEqual(r.status_code, 403)

    def test_revoked_token_returns_403(self) -> None:
        gov = reset_api_run_governance_for_tests()
        token = gov.register_agent("revoke-agent", ["goal:execute"])
        gov.token_service.revoke(token)
        with self._bare_client() as client:
            r = client.post(
                "/api/v1/run",
                json={"goal": "revoked", "agent_id": "revoke-agent", "governance_token": token},
                headers=auth_headers(),
            )
        self.assertEqual(r.status_code, 403)

    def test_wrong_capability_returns_403(self) -> None:
        gov = reset_api_run_governance_for_tests()
        token = gov.register_agent("cap-agent", ["goal:execute"])
        with self._bare_client() as client:
            r = client.post(
                "/api/v1/run",
                json={
                    "goal": "wrong cap",
                    "agent_id": "cap-agent",
                    "governance_token": token,
                    "capability": "tool:shell:exec",
                },
                headers=auth_headers(),
            )
        self.assertEqual(r.status_code, 403)

    def test_agent_id_mismatch_returns_403(self) -> None:
        gov = reset_api_run_governance_for_tests()
        token = gov.register_agent("real-agent", ["goal:execute"])
        with self._bare_client() as client:
            r = client.post(
                "/api/v1/run",
                json={
                    "goal": "mismatch",
                    "agent_id": "other-agent",
                    "governance_token": token,
                },
                headers=auth_headers(),
            )
        self.assertEqual(r.status_code, 403)


class TestPostRunGovernedSuccess(unittest.TestCase):
    def test_summary_marks_governed_true(self) -> None:
        with isolated_dashboard_state():
            with hermetic_run_client() as (client, _):
                r = client.post("/api/v1/run", json=run_payload("governed"), headers=auth_headers())
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["summary"]["governed"])

    def test_active_governed_engines_registers_instance(self) -> None:
        from backend.api.v1 import router as router_mod

        with isolated_dashboard_state():
            with hermetic_run_client() as (client, _):
                r = client.post("/api/v1/run", json=run_payload("reg"), headers=auth_headers())
        eid = r.json()["engine_id"]
        self.assertIn(eid, router_mod.active_governed_engines)

    def test_ledger_allowed_after_successful_run(self) -> None:
        from backend.api.v1 import router as router_mod

        with isolated_dashboard_state():
            with hermetic_run_client() as (client, _):
                client.post("/api/v1/run", json=run_payload("ledger"), headers=auth_headers())
        governed = list(router_mod.active_governed_engines.values())[-1]
        self.assertGreaterEqual(ledger_allowed_count(governed), 2)
        assert_ledger_chain(governed)

    def test_governance_token_header_accepted(self) -> None:
        with isolated_dashboard_state():
            with hermetic_run_client() as (client, _):
                r = client.post(
                    "/api/v1/run",
                    json={"goal": "header tok", "agent_id": hermetic_agent_id()},
                    headers={
                        **auth_headers(),
                        "X-Governance-Token": hermetic_governance_token(),
                    },
                )
        self.assertEqual(r.status_code, 200)

    def test_denial_recorded_on_invalid_token_before_run(self) -> None:
        import tempfile
        from pathlib import Path

        from thinkbox.engine import EngineConfig, ThinkBoxEngine

        ledger_path = str(Path(tempfile.mkdtemp()) / "deny_ledger.db")
        gov = reset_api_run_governance_for_tests(ledger_path=ledger_path)
        gov.register_agent("deny-agent", ["goal:execute"])
        with self._bare_client_for_gov() as client:
            client.post(
                "/api/v1/run",
                json={"goal": "x", "agent_id": "deny-agent", "governance_token": "bogus"},
                headers=auth_headers(),
            )
        probe = gov.build_governed_engine(ThinkBoxEngine(EngineConfig()))
        self.assertGreaterEqual(ledger_denied_count(probe), 1)
        assert_ledger_chain(probe)

    def _bare_client_for_gov(self) -> TestClient:
        from backend.api.v1 import router as router_mod

        app = FastAPI()
        with patch.dict(os.environ, {"THINKBOX_API_KEY": "tb_hermetic_pr131_contract_key"}, clear=False):
            from backend.security import setup_security

            setup_security(app)
            app.include_router(router_mod.api_v1_router)
        return TestClient(app, raise_server_exceptions=False)


class TestPostRunVerifiedHermetic(unittest.TestCase):
    def test_verified_run_with_hermetic_mock_model(self) -> None:
        subtasks = [subtask_spec("compute", "add_small")]
        with isolated_dashboard_state() as dash:
            with hermetic_run_client_real_engine() as (client, _gov):
                r = client.post(
                    "/api/v1/run",
                    json=run_payload(
                        "verified http",
                        verified=True,
                        model="hermetic-mock",
                        subtasks=subtasks,
                    ),
                    headers=auth_headers(),
                )
            self.assertEqual(r.status_code, 200)
            from backend.api.v1 import router as router_mod

            eid = r.json()["engine_id"]
            governed = router_mod.active_governed_engines[eid]
            assert_ledger_chain(governed)
            job = dash.think_jobs[eid]
            self.assertEqual(job.status, "completed")

    def test_verified_without_subtasks_returns_422(self) -> None:
        with isolated_dashboard_state():
            with hermetic_run_client() as (client, _):
                r = client.post(
                    "/api/v1/run",
                    json=run_payload("no subtasks", verified=True),
                    headers=auth_headers(),
                )
        self.assertEqual(r.status_code, 422)

    def test_verified_wrong_capability_denied_at_http(self) -> None:
        gov = reset_api_run_governance_for_tests()
        token = gov.register_agent("v-agent", ["goal:execute"])
        with TestPostRunGovernanceFailClosed()._bare_client() as client:
            r = client.post(
                "/api/v1/run",
                json={
                    "goal": "v",
                    "agent_id": "v-agent",
                    "governance_token": token,
                    "verified": True,
                    "model": "hermetic-mock",
                    "subtasks": [subtask_spec("compute", "add_small")],
                },
                headers=auth_headers(),
            )
        self.assertEqual(r.status_code, 403)


class TestPostRunOpenApiGovernance(unittest.TestCase):
    def test_openapi_run_request_includes_governance_fields(self) -> None:
        with hermetic_run_client() as (client, _):
            spec = client.get("/openapi.json", headers=auth_headers()).json()
        props = spec["components"]["schemas"]["RunRequest"]["properties"]
        self.assertIn("governance_token", props)
        self.assertIn("agent_id", props)
        self.assertIn("verified", props)

    def test_response_blob_secrets_clean(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post("/api/v1/run", json=run_payload("scan"), headers=auth_headers())
        assert_hermetic_blob_has_no_secrets(json.dumps(r.json()))


class TestF132BridgeF023(unittest.TestCase):
    def test_run_governed_module_importable(self) -> None:
        from backend.api.v1 import run_governed

        self.assertTrue(callable(run_governed.require_http_admission))

    def test_hermetic_provider_lives_in_thinkbox(self) -> None:
        from thinkbox.hermetic_provider import HermeticModelProvider

        self.assertTrue(HermeticModelProvider.__name__, "HermeticModelProvider")


if __name__ == "__main__":
    unittest.main()
