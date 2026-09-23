"""PR #134 review: receipt card shape stability."""

from __future__ import annotations

import unittest

from tests.e2e.api_run_hermetic import auth_headers, drain_background_tasks, hermetic_run_client, run_payload


class TestReceiptCardShapeReview(unittest.TestCase):
    def test_receipt_card_required_keys(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload("card shape"),
                headers=auth_headers(),
            )
            engine_id = r.json()["engine_id"]
            drain_background_tasks()
            card = client.get(
                f"/api/v1/dashboard/think-job/{engine_id}/receipt-card",
                headers=auth_headers(),
            ).json()
        for key in (
            "kind",
            "receipt_id",
            "experiment_id",
            "session_id",
            "receipt_linked",
            "live_verified",
            "production_ready",
        ):
            self.assertIn(key, card)


if __name__ == "__main__":
    unittest.main()
