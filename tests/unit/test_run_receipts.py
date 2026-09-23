"""Unit tests for HTTP governed run receipts (PR #133)."""

from __future__ import annotations

import unittest

from backend.api.v1.run_receipts import (
    RunReceiptPersistError,
    begin_http_run_receipt,
    finalize_http_run_receipt,
    read_run_receipt,
    redact_receipt_payload,
    reset_http_run_persistence_for_tests,
    set_persist_fail_hook,
    write_simple_http_run_proof,
)


class TestRunReceiptLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        reset_http_run_persistence_for_tests()
        set_persist_fail_hook(False)

    def test_begin_and_read_receipt(self) -> None:
        binding = begin_http_run_receipt(
            engine_id="eng_1",
            goal="hermetic goal",
            agent_id="agent-a",
            verified=True,
            capability="goal:execute:verified",
            admission_reason="ok",
        )
        finalize_http_run_receipt(
            binding,
            status="completed",
            outcome={"governed": True},
            confidence=1.0,
        )
        payload = read_run_receipt(binding.receipt_id)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["receipt_id"], binding.receipt_id)
        self.assertFalse(payload["live_verified"])

    def test_redact_strips_tokens(self) -> None:
        redacted = redact_receipt_payload(
            {"governance_token": "secret", "agent_id": "a", "tokens": 3}
        )
        self.assertNotIn("governance_token", redacted)
        self.assertIn("tokens", redacted)

    def test_persist_fail_hook_raises(self) -> None:
        binding = begin_http_run_receipt(
            engine_id="eng_2",
            goal="fail hook",
            agent_id="agent-b",
            verified=False,
            capability="goal:execute",
        )
        set_persist_fail_hook(True)
        with self.assertRaises(RunReceiptPersistError):
            write_simple_http_run_proof(binding, {"governed": True})


    def test_engine_lookup_without_memory_index(self) -> None:
        stack = reset_http_run_persistence_for_tests()
        binding = begin_http_run_receipt(
            engine_id="engine_lookup_1",
            goal="lookup",
            agent_id="agent",
            verified=False,
            capability="goal:execute",
        )
        finalize_http_run_receipt(binding, status="completed", outcome={"ok": True}, persistence=stack)
        stack._engine_index.clear()
        from backend.api.v1.run_receipts import read_run_receipt_by_engine

        payload = read_run_receipt_by_engine("engine_lookup_1")
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["receipt_id"], binding.receipt_id)


if __name__ == "__main__":
    unittest.main()
