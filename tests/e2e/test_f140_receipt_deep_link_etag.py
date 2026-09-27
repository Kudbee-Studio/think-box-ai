"""PR #140 — receipt deep-link + shared etag coherence (hermetic)."""

from __future__ import annotations

import unittest

from tests.e2e.api_run_hermetic import (
    auth_headers,
    drain_background_tasks,
    hermetic_run_client,
    run_payload,
)
from thinkbox.control_plane_deep_link import (
    build_think_job_watch_href,
    merge_deep_link_sources,
)
from thinkbox.control_plane_etag_store import (
    apply_conditional_get_to_store,
    if_none_match_header,
    merge_etag_stores,
    serialize_etag_store,
)
from thinkbox.think_job_status_ui import resolve_watch_target, stream_plan_for_watch_target


class TestF140ReceiptDeepLinkEtag(unittest.TestCase):
    def test_deep_link_href_matches_by_receipt_poll(self) -> None:
        with hermetic_run_client() as (client, _):
            r = client.post(
                "/api/v1/run",
                json=run_payload("f140 deep link"),
                headers=auth_headers(),
            )
            receipt_id = r.json()["summary"]["receipt_id"]
            drain_background_tasks()
            link = merge_deep_link_sources(
                query_string=f"receipt_id={receipt_id}&auto_watch=1&from=receipts.html",
            )
            self.assertEqual(link.receipt_id, receipt_id)
            href = build_think_job_watch_href(receipt_id=receipt_id)
            self.assertIn(receipt_id, href)
            poll = client.get(
                f"/api/v1/run/job/by-receipt/{receipt_id}/status",
                headers=auth_headers(),
            )
            self.assertEqual(poll.status_code, 200)
            target = resolve_watch_target(receipt_id=receipt_id)
            plan = stream_plan_for_watch_target(target, poll.json())
            self.assertIn("by-receipt", plan.poll_url)

    def test_shared_etag_store_merge_digest_poll(self) -> None:
        with hermetic_run_client() as (client, _):
            client.post(
                "/api/v1/run",
                json=run_payload("f140 etag"),
                headers=auth_headers(),
            )
            drain_background_tasks()
            url = "/api/v1/run/jobs/status/digest"
            first = client.get(url, headers=auth_headers())
            etag = first.headers.get("ETag")
            self.assertIsNotNone(etag)
            tab_a: dict = {}
            tab_b: dict = {}
            apply_conditional_get_to_store(tab_a, url, etag=etag, body=first.json())
            merge_etag_stores(tab_b, tab_a)
            second = client.get(
                url,
                headers={**auth_headers(), "If-None-Match": if_none_match_header(tab_b, url) or ""},
            )
            self.assertIn(second.status_code, (200, 304))
            blob = serialize_etag_store(tab_b)
            self.assertIn(url, blob)

    def test_invalid_deep_link_receipt_404(self) -> None:
        with hermetic_run_client() as (client, _):
            missing = client.get(
                "/api/v1/run/job/by-receipt/receipt_missing_f140/status",
                headers=auth_headers(),
            )
            self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
