"""HTTP END LINK deepen routes (PR #158)."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.control_plane_auth import LOCAL_DEV_TOKEN
from thinkbox.control_plane_operation_registry import reset_operation_registry
from thinkbox.control_plane_receipt_store import reset_control_plane_receipt_store


class TestBackendEndLinkDeepenPr158(unittest.TestCase):
    def setUp(self) -> None:
        reset_operation_registry()
        reset_control_plane_receipt_store()
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
            json={"action_type": "cp.demo", "operation_id": "op_el_158"},
            headers=self._auth(),
        )
        chain = client.get("/api/v1/control-plane/receipts/chain", headers=self._auth())
        return chain.json()["data"]["page"]["receipts"][0]["receipt_id"]

    def test_validate_includes_link_integrity(self) -> None:
        client = self._client()
        rid = self._seed_receipt(client)
        resp = client.get(
            f"/api/v1/control-plane/receipts/{rid}/validate",
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertTrue(data["valid"])
        self.assertEqual(data.get("link_integrity"), "ok")
        self.assertIn("deepen", data)

    def test_batch_validate_mixed(self) -> None:
        client = self._client()
        rid = self._seed_receipt(client)
        resp = client.post(
            "/api/v1/control-plane/receipts/validate/batch",
            json={"receipt_ids": [rid, "rcpt_missing_158"]},
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()["data"]
        self.assertEqual(payload["valid_count"], 1)
        self.assertEqual(payload["invalid_count"], 1)
        self.assertFalse(payload["live_api_called"])

    def test_batch_validate_bad_body(self) -> None:
        client = self._client()
        resp = client.post(
            "/api/v1/control-plane/receipts/validate/batch",
            json={"receipt_ids": []},
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 400)

    def test_chain_filter_evidence_label(self) -> None:
        client = self._client()
        self._seed_receipt(client)
        resp = client.get(
            "/api/v1/control-plane/receipts/chain/page?evidence_label=simulated",
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["data"]["receipts"])


if __name__ == "__main__":
    unittest.main()
