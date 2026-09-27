"""PR #131 — hermetic ``POST /api/v1/run`` Think Job HTTP contracts.

Bridges F023 governed DAG e2e (#130) to the FastAPI control-plane entrypoint.
Mock engine only; no Mercury / live provider HTTP.
"""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from starlette.testclient import TestClient

from backend.api.v1.router import RunRequest, RunResponse
from thinkbox.dashboard_state import DashboardCategory, DashboardEvent
from thinkbox.engine import EngineConfig

from tests.e2e.api_run_hermetic import auth_headers, events_matching, hermetic_run_client, run_payload
from tests.e2e.hermetic_scaffold import (
    assert_hermetic_blob_has_no_secrets,
    isolated_dashboard_state,
)


class TestRunRequestResponseSchema(unittest.TestCase):
    def test_run_request_goal_required(self) -> None:
        with self.assertRaises(Exception):
            RunRequest()  # type: ignore[call-arg]

    def test_run_request_defaults_speculative_true(self) -> None:
        req = RunRequest(goal="hermetic goal")
        self.assertTrue(req.speculative)

    def test_run_request_optional_model_and_temperature(self) -> None:
        req = RunRequest(goal="g", model="hermetic-mock", temperature=0.2)
        self.assertEqual(req.model, "hermetic-mock")
        self.assertEqual(req.temperature, 0.2)

    def test_run_response_model_fields(self) -> None:
        resp = RunResponse(
            engine_id="engine_abcd1234",
            session_id="",
            status="started",
            summary={"goal": "x"},
        )
        dumped = resp.model_dump()
        self.assertEqual(set(dumped.keys()), {"engine_id", "session_id", "status", "summary"})


class TestPostRunHermeticSuccess(unittest.TestCase):
    def test_post_run_returns_started_status(self) -> None:
        with isolated_dashboard_state():
            with hermetic_run_client() as (client, _):
                r = client.post("/api/v1/run", json=run_payload("contract goal"), headers=auth_headers())
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "started")
        self.assertTrue(body["engine_id"].startswith("engine_"))
        self.assertTrue(body["session_id"])
        self.assertIn("receipt_id", body["summary"])
        self.assertIn("experiment_id", body["summary"])
        self.assertIn("goal", body["summary"])

    def test_think_job_entry_upserted_through_lifecycle(self) -> None:
        with isolated_dashboard_state() as dash:
            with hermetic_run_client() as (client, mock_cls):
                r = client.post("/api/v1/run", json=run_payload("upsert check"), headers=auth_headers())
                self.assertEqual(r.status_code, 200)
                mock_cls.assert_called_once()
            eid = r.json()["engine_id"]
            self.assertIn(eid, dash.think_jobs)
            job = dash.think_jobs[eid]
            self.assertEqual(job.goal, "upsert check")
            self.assertEqual(job.status, "completed")
            self.assertEqual(job.engine_id, eid)
            self.assertEqual(job.phase, "completed")

    def test_task_started_event_emitted(self) -> None:
        with isolated_dashboard_state() as dash:
            with hermetic_run_client() as (client, _):
                r = client.post("/api/v1/run", json=run_payload("events"), headers=auth_headers())
                self.assertEqual(r.status_code, 200)
                started = events_matching(
                    dash,
                    category=DashboardCategory.THINK_JOBS,
                    event_type=DashboardEvent.TASK_STARTED,
                )
                self.assertEqual(len(started), 1)
                self.assertEqual(started[0].source, "api_v1")
                self.assertEqual(started[0].data["goal"], "events")
                self.assertEqual(started[0].category, DashboardCategory.THINK_JOBS)

    def test_task_completed_after_engine_finishes(self) -> None:
        with isolated_dashboard_state() as dash:
            with hermetic_run_client(execute_result={"total_tasks": 5, "completed": 4}) as (client, _):
                r = client.post("/api/v1/run", json=run_payload("finish"), headers=auth_headers())
                self.assertEqual(r.status_code, 200)
            completed = events_matching(
                dash,
                category=DashboardCategory.THINK_JOBS,
                event_type=DashboardEvent.TASK_COMPLETED,
            )
            self.assertEqual(len(completed), 1)
            self.assertEqual(completed[0].source, "governed_engine")
            self.assertEqual(completed[0].data["tasks_total"], 5)
            self.assertEqual(completed[0].data["tasks_completed"], 4)
            self.assertEqual(completed[0].data["progress"], 1.0)

    def test_active_engines_registers_instance(self) -> None:
        from backend.api.v1 import router as router_mod

        with isolated_dashboard_state():
            with hermetic_run_client() as (client, _):
                r = client.post("/api/v1/run", json=run_payload("register"), headers=auth_headers())
        eid = r.json()["engine_id"]
        self.assertIn(eid, router_mod.active_engines)

    def test_speculative_false_forwarded_to_engine_config(self) -> None:
        with isolated_dashboard_state():
            with hermetic_run_client() as (client, mock_cls):
                client.post(
                    "/api/v1/run",
                    json=run_payload("no speculate", speculative=False),
                    headers=auth_headers(),
                )
        cfg: EngineConfig = mock_cls.call_args[0][0]
        self.assertFalse(cfg.speculative)

    def test_model_and_temperature_forwarded(self) -> None:
        with isolated_dashboard_state():
            with hermetic_run_client() as (client, mock_cls):
                client.post(
                    "/api/v1/run",
                    json=run_payload("tuned", model="hermetic-model", temperature=0.42),
                    headers=auth_headers(),
                )
        cfg: EngineConfig = mock_cls.call_args[0][0]
        self.assertEqual(cfg.model_config.model, "hermetic-model")
        self.assertEqual(cfg.model_config.temperature, 0.42)


class TestPostRunAuthFailClosed(unittest.TestCase):
    def _bare_client(self) -> TestClient:
        from backend.api.v1 import router as router_mod

        app = FastAPI()
        with patch.dict(os.environ, {"THINKBOX_API_KEY": "tb_hermetic_pr131_contract_key"}, clear=False):
            from backend.security import setup_security

            setup_security(app)
            app.include_router(router_mod.api_v1_router)
        return TestClient(app, raise_server_exceptions=False)

    def test_missing_api_key_returns_401(self) -> None:
        with self._bare_client() as client:
            r = client.post("/api/v1/run", json={"goal": "no auth"})
        self.assertEqual(r.status_code, 401)
        self.assertIn("Unauthorized", r.text)

    def test_invalid_api_key_returns_401(self) -> None:
        with self._bare_client() as client:
            r = client.post(
                "/api/v1/run",
                json={"goal": "bad key"},
                headers={"X-API-Key": "not-a-valid-key"},
            )
        self.assertEqual(r.status_code, 401)

    def test_openapi_exempt_without_api_key(self) -> None:
        with self._bare_client() as client:
            r = client.get("/openapi.json")
        self.assertEqual(r.status_code, 200)

    def test_api_key_query_param_rejected_by_default(self) -> None:
        with isolated_dashboard_state():
            with hermetic_run_client() as (client, _):
                r = client.post(
                    "/api/v1/run?api_key=tb_hermetic_pr131_contract_key",
                    json=run_payload("query auth"),
                )
        self.assertEqual(r.status_code, 401)

    def test_api_key_query_param_opt_in(self) -> None:
        with isolated_dashboard_state():
            with patch("backend.security.ALLOW_QUERY_API_KEY", True):
                with hermetic_run_client() as (client, _):
                    r = client.post(
                        "/api/v1/run?api_key=tb_hermetic_pr131_contract_key",
                        json=run_payload("query auth opt-in"),
                    )
        self.assertEqual(r.status_code, 200)

    def test_rate_limit_headers_present_on_authed_request(self) -> None:
        with isolated_dashboard_state():
            with hermetic_run_client() as (client, _):
                r = client.post("/api/v1/run", json=run_payload("rl"), headers=auth_headers())
        self.assertEqual(r.status_code, 200)
        self.assertIn("X-RateLimit-Limit", r.headers)
        self.assertIn("X-RateLimit-Remaining", r.headers)


class TestPostRunValidationAndFailure(unittest.TestCase):
    def test_invalid_json_body_returns_422(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                content=b"not-json",
                headers={**auth_headers(), "Content-Type": "application/json"},
            )
        self.assertEqual(r.status_code, 422)

    def test_missing_goal_field_returns_422(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post("/api/v1/run", json={"speculative": True}, headers=auth_headers())
        self.assertEqual(r.status_code, 422)

    def test_engine_failure_emits_task_failed(self) -> None:
        with isolated_dashboard_state() as dash:
            with hermetic_run_client(execute_raises=RuntimeError("hermetic boom")) as (client, _):
                r = client.post("/api/v1/run", json=run_payload("fail"), headers=auth_headers())
                self.assertEqual(r.status_code, 200)
            failed = events_matching(
                dash,
                category=DashboardCategory.THINK_JOBS,
                event_type=DashboardEvent.TASK_FAILED,
            )
            self.assertEqual(len(failed), 1)
            self.assertIn("hermetic boom", failed[0].data["result"]["error"])
            self.assertEqual(dash.think_jobs[r.json()["engine_id"]].status, "failed")

    def test_response_blob_secrets_clean(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload("scan me"),
                headers=auth_headers(),
            )
        assert_hermetic_blob_has_no_secrets(json.dumps(r.json()))


class TestPostRunOpenApiContract(unittest.TestCase):
    def test_openapi_lists_post_run(self) -> None:
        with hermetic_run_client() as (client, _):
            spec = client.get("/openapi.json", headers=auth_headers()).json()
        paths = spec.get("paths", {})
        self.assertIn("/api/v1/run", paths)
        self.assertIn("post", paths["/api/v1/run"])

    def test_openapi_run_response_refs_run_response(self) -> None:
        with hermetic_run_client() as (client, _):
            spec = client.get("/openapi.json", headers=auth_headers()).json()
        post = spec["paths"]["/api/v1/run"]["post"]
        schema = post["responses"]["200"]["content"]["application/json"]["schema"]
        title = schema.get("title") or schema.get("$ref", "")
        self.assertTrue("RunResponse" in str(title) or "RunResponse" in json.dumps(schema))

    def test_goal_truncated_in_immediate_summary(self) -> None:
        long_goal = "g" * 150
        with hermetic_run_client() as (client, _):
            r = client.post("/api/v1/run", json=run_payload(long_goal), headers=auth_headers())
        summary_goal = r.json()["summary"]["goal"]
        self.assertEqual(len(summary_goal), 100)


class TestF131BridgeToF023(unittest.TestCase):
    def test_router_imports_think_job_entry(self) -> None:
        from backend.api.v1.router import ThinkJobEntry as imported

        self.assertEqual(imported.__name__, "ThinkJobEntry")

    def test_f023_scaffold_still_importable(self) -> None:
        from tests.e2e import test_f023_think_job_lifecycle  # noqa: F401

        self.assertTrue(hasattr(test_f023_think_job_lifecycle, "TestF023ModelProviderWiring"))


if __name__ == "__main__":
    unittest.main()
