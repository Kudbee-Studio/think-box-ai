"""GET /stream must not send exception text to the client (CodeQL py/stack-trace-exposure).

A provider error can carry upstream URLs, status bodies or key fragments; the client gets a generic
message and the detail stays in the server log.
"""

from __future__ import annotations

import importlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

_KEY = "tb_stream_error_redaction_key"
_DETAIL = "upstream 401 for key sk-test-0123 at http://10.0.0.5:8080/v1"


class _FailingProvider:
    async def stream(self, messages):  # noqa: ARG002 - matches the provider interface
        raise RuntimeError(_DETAIL)
        yield  # pragma: no cover - makes this an async generator


class TestStreamErrorRedaction(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            importlib.import_module("fastapi")
            importlib.import_module("httpx")
        except ImportError as exc:  # pragma: no cover - needs the test dependencies
            raise unittest.SkipTest(f"fastapi/httpx not installed: {exc}") from exc
        cls._env = patch.dict(os.environ, {"THINKBOX_API_KEY": _KEY})
        cls._env.start()
        cls.main = importlib.import_module("backend.main")
        cls.header = importlib.import_module("backend.security").API_KEY_HEADER

    @classmethod
    def tearDownClass(cls) -> None:
        cls._env.stop()

    def test_a_provider_error_is_reported_without_its_text(self) -> None:
        from fastapi.testclient import TestClient

        fake_ctx = SimpleNamespace(provider=_FailingProvider(), tool_registry=None)
        with patch.object(self.main, "ctx", fake_ctx):
            client = TestClient(self.main.app)  # no `with`: the startup bootstrap does not run
            res = client.get("/stream", params={"goal": "say hi"}, headers={self.header: _KEY})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIn('"type": "error"', res.text)
        for fragment in ("sk-test-0123", "10.0.0.5", "upstream 401"):
            self.assertNotIn(fragment, res.text)


if __name__ == "__main__":
    unittest.main()
