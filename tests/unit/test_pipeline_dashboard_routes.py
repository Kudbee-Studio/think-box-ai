from __future__ import annotations

import os
import tempfile
import unittest

_HAVE_FASTAPI = False
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.api.v1.pipeline_dashboard import (
        pipeline_dashboard_router,
        reset_pipeline_dashboard_cache,
    )

    _HAVE_FASTAPI = True
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore
    TestClient = None  # type: ignore
    pipeline_dashboard_router = None  # type: ignore
    reset_pipeline_dashboard_cache = None  # type: ignore


@unittest.skipUnless(_HAVE_FASTAPI, "fastapi not installed")
class TestPipelineDashboardRoutes(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db = os.path.join(self._tmpdir.name, "org_memory.db")
        os.environ["THINKBOX_ORG_MEMORY_DB"] = self._db
        os.environ["THINKBOX_PIPELINE_TEST_MODE"] = "true"
        reset_pipeline_dashboard_cache()
        app = FastAPI()
        app.include_router(pipeline_dashboard_router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        reset_pipeline_dashboard_cache()
        self._tmpdir.cleanup()
        os.environ.pop("THINKBOX_ORG_MEMORY_DB", None)

    def test_reconcile_route(self) -> None:
        resp = self.client.get("/api/v1/control-plane/pipeline/reconcile")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("chain_verified", body)

    def test_admissions_provenance_route(self) -> None:
        resp = self.client.get("/api/v1/control-plane/pipeline/admissions/provenance")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("events", body)
        self.assertIn("summary", body)
        self.assertFalse(body.get("auto_merge"))

    def test_rollup_consistency_route(self) -> None:
        resp = self.client.get("/api/v1/control-plane/pipeline/pr/42/rollup-consistency")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body.get("pr_number"), 42)

    def test_integrity_route_expanded_shape(self) -> None:
        resp = self.client.get("/api/v1/control-plane/pipeline/pr/42/integrity")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("chain_verified", body)
        self.assertIn("state_machine", body)


if __name__ == "__main__":
    unittest.main()
