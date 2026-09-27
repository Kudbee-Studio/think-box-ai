"""HTTP tests for control-plane API routes (PR #154, hermetic TestClient)."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.api.v1.control_plane_auth import LOCAL_DEV_TOKEN
from thinkbox.control_plane_operation_registry import reset_operation_registry


class TestBackendControlPlaneApi(unittest.TestCase):
    def setUp(self) -> None:
        reset_operation_registry()
        self._env = mock.patch.dict(
            os.environ,
            {"THINKBOX_CONTROL_PLANE_ALLOW_DEV_TOKEN": "1"},
            clear=False,
        )
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        reset_operation_registry()

    def _client(self) -> TestClient:
        from backend.api.v1.control_plane import control_plane_api
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(control_plane_api)
        return TestClient(app, raise_server_exceptions=True)

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {LOCAL_DEV_TOKEN}"}

    def test_contract_requires_auth(self) -> None:
        client = self._client()
        resp = client.get("/api/v1/control-plane/contract")
        self.assertEqual(resp.status_code, 401)

    def test_contract_ok(self) -> None:
        client = self._client()
        resp = client.get("/api/v1/control-plane/contract", headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["live_api_called"])

    def test_create_operation_roundtrip(self) -> None:
        client = self._client()
        payload = {"action_type": "cp.demo", "operation_id": "http_op_1"}
        resp = client.post(
            "/api/v1/control-plane/operations",
            json=payload,
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["operation_id"], "http_op_1")

    def test_get_operation_etag(self) -> None:
        client = self._client()
        client.post(
            "/api/v1/control-plane/operations",
            json={"action_type": "cp.demo", "operation_id": "http_op_2"},
            headers=self._auth(),
        )
        resp = client.get(
            "/api/v1/control-plane/operations/http_op_2",
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        etag = resp.headers.get("etag") or resp.headers.get("ETag")
        self.assertTrue(etag)
        resp304 = client.get(
            "/api/v1/control-plane/operations/http_op_2",
            headers={**self._auth(), "If-None-Match": etag},
        )
        self.assertEqual(resp304.status_code, 304)

    def test_unconfigured_returns_503(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            from backend.api.v1.control_plane_auth import configured_control_plane_token

            self.assertIsNone(configured_control_plane_token())


if __name__ == "__main__":
    unittest.main()
