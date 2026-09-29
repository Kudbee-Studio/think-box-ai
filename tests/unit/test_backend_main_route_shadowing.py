"""Route-shadowing guard for the real ``backend.main:app``.

The governed-run e2e tests build their own FastAPI app from ``api_v1_router``,
so they never saw that ``backend.main`` registered a legacy ``POST /api/v1/run``
(the unversioned LLM loop) *before* including ``api_v1_router``. That legacy
route answered every request, and the governed ``run_goal`` (admission,
receipts, ThinkJobEntry, execution substrates) was unreachable over HTTP.
These tests load the real app.
"""

from __future__ import annotations

import collections
import importlib
import os
import unittest
from typing import Any
from unittest.mock import patch

_KEY = "tb_route_shadow_guard_key"


def _flatten(routes: list[Any], prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten app routes across FastAPI versions (flat lists or nested included routers)."""
    out: list[tuple[str, Any]] = []
    for route in routes:
        if type(route).__name__ == "_IncludedRouter":
            inner = getattr(route, "router", None) or getattr(route, "original_router", None)
            sub = getattr(inner, "routes", None) if inner is not None else None
            out.extend(_flatten(sub if sub is not None else getattr(route, "routes", []),
                                prefix + (getattr(route, "prefix", "") or "")))
        else:
            out.append((prefix + str(getattr(route, "path", "")), route))
    return out


def _endpoint_name(route: Any) -> str:
    ep = getattr(route, "endpoint", None)
    return f"{getattr(ep, '__module__', '?')}.{getattr(ep, '__name__', '?')}"


class TestBackendMainRouteShadowing(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            importlib.import_module("fastapi")
        except ImportError as exc:  # pragma: no cover - CI installs the project
            raise unittest.SkipTest(f"fastapi not installed: {exc}") from exc
        cls._env = patch.dict(os.environ, {"THINKBOX_API_KEY": _KEY})
        cls._env.start()
        cls.main = importlib.import_module("backend.main")
        cls.flat = _flatten(cls.main.app.router.routes)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._env.stop()

    def _handlers(self, method: str, path: str) -> list[str]:
        return [
            _endpoint_name(r)
            for p, r in self.flat
            if p == path and method in (getattr(r, "methods", None) or set())
        ]

    def test_api_v1_run_is_served_by_the_governed_handler_only(self) -> None:
        self.assertEqual(
            self._handlers("POST", "/api/v1/run"),
            ["backend.api.v1.router.run_goal"],
        )

    def test_legacy_unversioned_run_still_exists(self) -> None:
        self.assertEqual(self._handlers("POST", "/run"), ["backend.main.run_goal"])

    def test_no_path_is_shadowed_by_a_different_handler(self) -> None:
        by_key: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
        for path, route in self.flat:
            for method in getattr(route, "methods", None) or ():
                by_key[(method, path)].add(_endpoint_name(route))
        shadowed = {k: sorted(v) for k, v in by_key.items() if len(v) > 1}
        self.assertEqual(shadowed, {}, f"routes shadowed by a different handler: {shadowed}")

    def test_real_app_request_reaches_governed_handler(self) -> None:
        from starlette.testclient import TestClient

        client = TestClient(self.main.app)
        resp = client.post("/api/v1/run", headers={"X-API-Key": _KEY}, json={"goal": "hostname"})
        # The shadowing legacy handler answered 200 {"success": false, "error": "No provider configured"}.
        # The governed handler rejects a run without governance admission instead.
        self.assertNotEqual(resp.json(), {"success": False, "error": "No provider configured"})
        self.assertIn(resp.status_code, (400, 401, 403, 422))


if __name__ == "__main__":
    unittest.main()
