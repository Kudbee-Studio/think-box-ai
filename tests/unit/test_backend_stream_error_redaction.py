"""GET /stream must not send exception text to the client (CodeQL py/stack-trace-exposure).

A provider error can carry upstream URLs, status bodies or key fragments; the client gets a generic
message and the detail stays in the server log.
"""

from __future__ import annotations

import asyncio
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
        except ImportError as exc:  # pragma: no cover - needs the project dependencies
            raise unittest.SkipTest(f"fastapi not installed: {exc}") from exc
        cls._env = patch.dict(os.environ, {"THINKBOX_API_KEY": _KEY})  # backend.main refuses to import without a key
        cls._env.start()
        cls.main = importlib.import_module("backend.main")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._env.stop()

    def test_a_provider_error_is_reported_without_its_text(self) -> None:
        # Calls the endpoint itself, not through the shared app: its auth middleware keeps the API key of
        # whichever test imported backend.main first, so an HTTP request here depended on test order.
        async def body() -> str:
            response = await self.main.stream_goal(goal="say hi")
            parts = [c if isinstance(c, str) else c.decode() async for c in response.body_iterator]
            return "".join(parts)

        fake_ctx = SimpleNamespace(provider=_FailingProvider(), tool_registry=None)
        with patch.object(self.main, "ctx", fake_ctx), self.assertLogs("thinkbox.backend.main", level="ERROR") as logs:
            text = asyncio.run(body())
        self.assertIn('"type": "error"', text)
        self.assertIn("RuntimeError", text)
        logged = "\n".join(logs.output)
        self.assertIn("RuntimeError", logged)
        # Upstream error text can echo key fragments (AGENTS.md 0.4: keys are never printed or logged).
        for fragment in ("sk-test-0123", "10.0.0.5", "upstream 401"):
            self.assertNotIn(fragment, text)
            self.assertNotIn(fragment, logged)

if __name__ == "__main__":
    unittest.main()
