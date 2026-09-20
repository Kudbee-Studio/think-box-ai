from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from thinkbox.github_webhook import build_hermetic_github_webhook_service, compute_github_signature

_HERMETIC_SECRET = "live-capture-secret"


class TestLiveWebhookCapture(unittest.TestCase):
    def test_staging_records_delivery_receipt(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"THINKBOX_PIPELINE_STAGING": "1"},
            clear=False,
        ):
            svc = build_hermetic_github_webhook_service(_HERMETIC_SECRET)
            payload = {
                "action": "opened",
                "number": 110,
                "pull_request": {"head": {"ref": "feat/live", "sha": "abc"}},
            }
            body = json.dumps(payload).encode()
            sig = compute_github_signature(_HERMETIC_SECRET, body)
            svc.process(
                body,
                "pull_request",
                sig,
                delivery_id="gh-delivery-110",
                drill_correlation_id="corr-110",
            )
            rows = svc._store.query(pr_number=110, limit=20)  # noqa: SLF001
            self.assertTrue(any(r.get("action") == "live_webhook_delivery" for r in rows))


if __name__ == "__main__":
    unittest.main()
