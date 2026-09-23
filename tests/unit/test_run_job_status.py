"""Unit tests for Think Job status polling (PR #134)."""

from __future__ import annotations

import unittest

from backend.api.v1.run_job_status import (
    STATUS_SCHEMA_VERSION,
    ThinkJobNotFoundError,
    build_receipt_link_card,
    build_think_job_status_payload,
    list_recent_think_job_statuses,
    poll_hints_for_status,
    redact_status_payload,
    resolve_think_job_by_receipt,
    resolve_think_job_record,
)
from backend.api.v1.run_receipts import (
    begin_http_run_receipt,
    finalize_http_run_receipt,
    reset_http_run_persistence_for_tests,
)
from thinkbox.dashboard_state import ThinkJobEntry, get_dashboard_state


class TestPollHints(unittest.TestCase):
    def test_running_not_terminal(self) -> None:
        hints = poll_hints_for_status("running")
        self.assertFalse(hints["terminal"])
        self.assertEqual(hints["schema_version"], STATUS_SCHEMA_VERSION)

    def test_completed_terminal(self) -> None:
        hints = poll_hints_for_status("completed")
        self.assertTrue(hints["terminal"])


class TestReceiptLinkCard(unittest.TestCase):
    def test_card_marks_linked_when_ids_present(self) -> None:
        card = build_receipt_link_card(
            job_id="j1",
            status="completed",
            phase="completed",
            receipt_id="rcpt",
            experiment_id="exp",
            session_id="sess",
        )
        self.assertTrue(card["receipt_linked"])
        self.assertFalse(card["live_verified"])


class TestResolveThinkJob(unittest.TestCase):
    def setUp(self) -> None:
        reset_http_run_persistence_for_tests()
        dash = get_dashboard_state()
        dash.think_jobs.clear()

    def test_dashboard_resolution(self) -> None:
        dash = get_dashboard_state()
        dash.upsert_think_job(
            ThinkJobEntry(
                job_id="eng_dash",
                goal="g",
                status="running",
                engine_id="eng_dash",
                receipt_id="r1",
                experiment_id="e1",
                session_id="s1",
            )
        )
        record = resolve_think_job_record("eng_dash")
        self.assertEqual(record["source"], "dashboard")
        payload = build_think_job_status_payload(record)
        self.assertTrue(payload["receipt"]["linked"])

    def test_sqlite_fallback_when_dashboard_empty(self) -> None:
        binding = begin_http_run_receipt(
            engine_id="eng_sql",
            goal="sqlite",
            agent_id="a",
            verified=False,
            capability="goal:execute",
        )
        finalize_http_run_receipt(binding, status="completed", outcome={"ok": True})
        record = resolve_think_job_record("eng_sql")
        self.assertEqual(record["source"], "receipt_sqlite")

    def test_unknown_job_raises(self) -> None:
        with self.assertRaises(ThinkJobNotFoundError):
            resolve_think_job_record("missing_engine_xyz")

    def test_redact_status_strips_token_fields(self) -> None:
        out = redact_status_payload({"governance_token": "x", "status": "ok"})
        self.assertNotIn("governance_token", out)

    def test_resolve_by_receipt_id(self) -> None:
        binding = begin_http_run_receipt(
            engine_id="eng_rcpt",
            goal="by receipt",
            agent_id="a",
            verified=False,
            capability="goal:execute",
        )
        finalize_http_run_receipt(binding, status="completed", outcome={"ok": True})
        record = resolve_think_job_by_receipt(binding.receipt_id)
        self.assertEqual(record["receipt_id"], binding.receipt_id)

    def test_status_payload_includes_goal_preview(self) -> None:
        dash = get_dashboard_state()
        dash.upsert_think_job(
            ThinkJobEntry(job_id="g1", goal="long goal text here", status="running")
        )
        record = resolve_think_job_record("g1")
        payload = build_think_job_status_payload(record, goal_hint="long goal text here")
        self.assertIn("goal_preview", payload)

    def test_dashboard_receipt_summary_counts_linked(self) -> None:
        dash = get_dashboard_state()
        dash.think_jobs.clear()
        dash.upsert_think_job(
            ThinkJobEntry(
                job_id="l1",
                goal="g",
                status="completed",
                receipt_id="r",
                experiment_id="e",
                session_id="s",
            )
        )
        summary = dash.get_state()["think_job_receipt_summary"]
        self.assertEqual(summary["receipt_linked"], 1)

    def test_list_recent_clamps_limit(self) -> None:
        dash = get_dashboard_state()
        for i in range(5):
            dash.upsert_think_job(
                ThinkJobEntry(job_id=f"j{i}", goal="g", status="completed")
            )
        listed = list_recent_think_job_statuses(limit=2)
        self.assertEqual(len(listed), 2)


if __name__ == "__main__":
    unittest.main()
