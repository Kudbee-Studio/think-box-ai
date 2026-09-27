"""PR #137 — SSE routes fail-closed without API key."""

from __future__ import annotations

import unittest

from tests.e2e.api_run_hermetic import drain_background_tasks, hermetic_run_client, run_payload
from tests.e2e.api_run_hermetic import auth_headers


class TestThinkJobStreamAuth(unittest.TestCase):
    def test_stream_requires_api_key(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload("auth stream"),
                headers=auth_headers(),
            )
            engine_id = r.json()["engine_id"]
            drain_background_tasks()
            denied = client.get(f"/api/v1/run/job/{engine_id}/status/stream")
            self.assertEqual(denied.status_code, 401)


if __name__ == "__main__":
    unittest.main()
