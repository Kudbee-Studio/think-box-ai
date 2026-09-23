"""HTTP END LINK API ops harden routes (PR #161)."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.control_plane_auth import LOCAL_DEV_TOKEN
from thinkbox.control_plane_operation_registry import reset_operation_registry
from thinkbox.control_plane_receipt_store import reset_control_plane_receipt_store
from thinkbox.end_link_api_ops_harden import reset_batch_idempotency_cache


class TestBackendEndLinkApiOpsHardenPr161(unittest.TestCase):
    def setUp(self) -> None:
        reset_operation_registry()
        reset_control_plane_receipt_store()
        reset_batch_idempotency_cache()
        self._env = mock.patch.dict(
            os.environ,
            {"THINKBOX_CONTROL_PLANE_ALLOW_DEV_TOKEN": "1"},
            clear=False,
        )
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        reset_operation_registry()
        reset_control_plane_receipt_store()
        reset_batch_idempotency_cache()

    def _client(self) -> TestClient:
        from backend.api.v1.control_plane import control_plane_api

        app = FastAPI()
        app.include_router(control_plane_api)
        return TestClient(app, raise_server_exceptions=True)

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {LOCAL_DEV_TOKEN}"}

    def _seed_receipt(self, client: TestClient) -> str:
        client.post(
            "/api/v1/control-plane/operations",
            json={"action_type": "cp.demo", "operation_id": "op_el_161"},
            headers=self._auth(),
        )
        chain = client.get("/api/v1/control-plane/receipts/chain", headers=self._auth())
        return chain.json()["data"]["page"]["receipts"][0]["receipt_id"]

    def test_validate_includes_ops_timing(self) -> None:
        client = self._client()
        rid = self._seed_receipt(client)
        resp = client.get(
            f"/api/v1/control-plane/receipts/{rid}/validate",
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        ops = resp.json()["data"].get("ops") or {}
        self.assertIn("timing_ms", ops)
        self.assertFalse(ops.get("live_verified", True))

    def test_chain_filter_invalid(self) -> None:
        client = self._client()
        resp = client.get(
            "/api/v1/control-plane/receipts/chain",
            params={"status": "bad status!"},
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 400)
        detail = resp.json()["detail"]
        self.assertFalse(detail.get("ok", True))

    def test_batch_idempotency_replay(self) -> None:
        client = self._client()
        rid = self._seed_receipt(client)
        body = {"receipt_ids": [rid]}
        headers = {**self._auth(), "Idempotency-Key": "batch-161"}
        first = client.post(
            "/api/v1/control-plane/receipts/validate/batch",
            json=body,
            headers=headers,
        )
        second = client.post(
            "/api/v1/control-plane/receipts/validate/batch",
            json=body,
            headers=headers,
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["data"]["total"], second.json()["data"]["total"])


if __name__ == "__main__":
    unittest.main()
