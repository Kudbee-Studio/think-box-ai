"""HTTP hardening tests for control-plane routes (PR #157)."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.api.v1.control_plane_auth import LOCAL_DEV_TOKEN
from thinkbox.control_plane_operation_registry import reset_operation_registry
from thinkbox.control_plane_ops_harden import reset_idempotency_registry, reset_ops_rate_limiter


class TestBackendControlPlaneOpsHarden(unittest.TestCase):
    def setUp(self) -> None:
        reset_operation_registry()
        reset_idempotency_registry()
        reset_ops_rate_limiter()
        self._env = mock.patch.dict(
            os.environ,
            {"THINKBOX_CONTROL_PLANE_ALLOW_DEV_TOKEN": "1"},
            clear=False,
        )
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        reset_operation_registry()
        reset_idempotency_registry()
        reset_ops_rate_limiter()

    def _client(self) -> TestClient:
        from backend.api.v1.control_plane import control_plane_api
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(control_plane_api)
        return TestClient(app, raise_server_exceptions=True)

    def _auth(self, **extra: str) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {LOCAL_DEV_TOKEN}"}
        headers.update(extra)
        return headers

    def test_contract_includes_ops_harden(self) -> None:
        client = self._client()
        resp = client.get("/api/v1/control-plane/contract", headers=self._auth())
        data = resp.json()["data"]
        self.assertEqual(data.get("ops_harden"), "api-ops-harden")

    def test_structured_404_operation(self) -> None:
        client = self._client()
        resp = client.get("/api/v1/control-plane/operations/missing_op", headers=self._auth())
        self.assertEqual(resp.status_code, 404)
        detail = resp.json()["detail"]
        self.assertFalse(detail["ok"])
        self.assertEqual(detail["error"]["code"], "operation_not_found")

    def test_idempotency_key_replay(self) -> None:
        client = self._client()
        body = {"action_type": "cp.demo", "operation_id": "idem_op_1"}
        headers = self._auth(**{"Idempotency-Key": "key-abc"})
        first = client.post("/api/v1/control-plane/operations", json=body, headers=headers)
        second = client.post("/api/v1/control-plane/operations", json=body, headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["data"]["operation_id"], second.json()["data"]["operation_id"])

    def test_chain_limit_clamped(self) -> None:
        client = self._client()
        resp = client.get(
            "/api/v1/control-plane/receipts/chain/page?limit=99999",
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        page = resp.json()["data"]
        self.assertLessEqual(len(page.get("receipts") or []), 200)

    def test_validate_envelope_on_missing_receipt(self) -> None:
        client = self._client()
        resp = client.get(
            "/api/v1/control-plane/receipts/rcpt_does_not_exist/validate",
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 404)
        detail = resp.json()["detail"]
        self.assertEqual(detail["error"]["code"], "receipt_not_found")


if __name__ == "__main__":
    unittest.main()
