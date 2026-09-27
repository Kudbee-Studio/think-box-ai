"""HTTP receipt chain routes (PR #155)."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.api.v1.control_plane_auth import LOCAL_DEV_TOKEN
from thinkbox.control_plane_operation_registry import reset_operation_registry
from thinkbox.control_plane_receipt_store import reset_control_plane_receipt_store


class TestBackendReceiptChainPr155(unittest.TestCase):
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
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(control_plane_api)
        return TestClient(app, raise_server_exceptions=True)

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {LOCAL_DEV_TOKEN}"}

    def test_chain_conditional_304(self) -> None:
        client = self._client()
        client.post(
            "/api/v1/control-plane/operations",
            json={"action_type": "cp.demo", "operation_id": "op_chain_1"},
            headers=self._auth(),
        )
        first = client.get("/api/v1/control-plane/receipts/chain", headers=self._auth())
        self.assertEqual(first.status_code, 200)
        etag = first.headers.get("etag") or first.headers.get("ETag")
        second = client.get(
            "/api/v1/control-plane/receipts/chain",
            headers={**self._auth(), "If-None-Match": etag or ""},
        )
        self.assertEqual(second.status_code, 304)

    def test_chain_page_pagination(self) -> None:
        client = self._client()
        for i in range(3):
            client.post(
                "/api/v1/control-plane/operations",
                json={"action_type": "cp.demo", "operation_id": f"op_p_{i}"},
                headers=self._auth(),
            )
        resp = client.get(
            "/api/v1/control-plane/receipts/chain/page?limit=1",
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(len(data["receipts"]), 1)
        self.assertIsNotNone(data.get("next_cursor"))

    def test_chain_head_tail(self) -> None:
        client = self._client()
        client.post(
            "/api/v1/control-plane/operations",
            json={"action_type": "cp.demo", "operation_id": "op_ht"},
            headers=self._auth(),
        )
        head = client.get("/api/v1/control-plane/receipts/chain/head", headers=self._auth())
        tail = client.get("/api/v1/control-plane/receipts/chain/tail", headers=self._auth())
        self.assertEqual(head.status_code, 200)
        self.assertEqual(tail.status_code, 200)
        self.assertIsNotNone(head.json()["data"]["head"])
        self.assertIsNotNone(tail.json()["data"]["tail"])

    def test_validate_link_412_on_bad_if_match(self) -> None:
        client = self._client()
        client.post(
            "/api/v1/control-plane/operations",
            json={"action_type": "cp.demo", "operation_id": "op_val"},
            headers=self._auth(),
        )
        chain = client.get("/api/v1/control-plane/receipts/chain", headers=self._auth())
        rid = chain.json()["data"]["page"]["receipts"][0]["receipt_id"]
        resp = client.get(
            f"/api/v1/control-plane/receipts/{rid}/validate",
            headers={**self._auth(), "If-Match": 'W/"wrong"'},
        )
        self.assertEqual(resp.status_code, 412)

    def test_validate_link_ok(self) -> None:
        client = self._client()
        client.post(
            "/api/v1/control-plane/operations",
            json={"action_type": "cp.demo", "operation_id": "op_val2"},
            headers=self._auth(),
        )
        chain = client.get("/api/v1/control-plane/receipts/chain", headers=self._auth())
        rid = chain.json()["data"]["page"]["receipts"][0]["receipt_id"]
        resp = client.get(
            f"/api/v1/control-plane/receipts/{rid}/validate",
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["data"]["valid"])

    def test_chain_filter_agent(self) -> None:
        client = self._client()
        client.post(
            "/api/v1/control-plane/operations",
            json={
                "action_type": "cp.demo",
                "operation_id": "op_ag",
                "metadata": {"agent_id": "agent-x"},
            },
            headers=self._auth(),
        )
        resp = client.get(
            "/api/v1/control-plane/receipts/chain?agent_id=agent-x",
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        receipts = resp.json()["data"]["page"]["receipts"]
        self.assertTrue(receipts)
        self.assertEqual(receipts[0].get("agent_id"), "agent-x")


if __name__ == "__main__":
    unittest.main()
