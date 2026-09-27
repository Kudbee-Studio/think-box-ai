"""Unit tests for PR #161 end_link_api_ops_harden helpers."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_ops_harden import IdempotencyConflict
from thinkbox.end_link_api_ops_harden import (
    enrich_batch_validate_payload,
    enrich_validate_payload,
    lookup_batch_idempotency_replay,
    normalize_failure_code,
    normalize_failure_codes_in_payload,
    register_batch_idempotency_replay,
    reset_batch_idempotency_cache,
    validate_chain_filter_query,
)


class TestEndLinkApiOpsHarden(unittest.TestCase):
    def setUp(self) -> None:
        reset_batch_idempotency_cache()

    def tearDown(self) -> None:
        reset_batch_idempotency_cache()

    def test_normalize_failure_code_known(self) -> None:
        self.assertEqual(normalize_failure_code("receipt_not_found"), "receipt_not_found")

    def test_chain_filter_rejects_unsafe(self) -> None:
        _params, errors = validate_chain_filter_query(status="bad!")
        self.assertTrue(errors)

    def test_chain_filter_accepts_clean(self) -> None:
        params, errors = validate_chain_filter_query(status="OK", action="cp.demo")
        self.assertFalse(errors)
        self.assertEqual(params.status_filter, "OK")

    def test_enrich_validate_ops_meta(self) -> None:
        out = enrich_validate_payload({"valid": True, "receipt_id": "r"})
        ops = out.get("ops") or {}
        self.assertTrue(ops.get("idempotent_retry_safe"))
        self.assertFalse(ops.get("live_verified", True))

    def test_batch_idempotency_replay(self) -> None:
        body = {"receipt_ids": ["a"]}
        payload = {"total": 1}
        register_batch_idempotency_replay("key1", body, payload)
        cached = lookup_batch_idempotency_replay("key1", body)
        self.assertEqual(cached, payload)

    def test_batch_idempotency_conflict(self) -> None:
        body = {"receipt_ids": ["a"]}
        register_batch_idempotency_replay("key1", body, {"total": 1})
        with self.assertRaises(IdempotencyConflict):
            register_batch_idempotency_replay("key1", {"receipt_ids": ["b"]}, {"total": 1})

    def test_normalize_items_failure_codes(self) -> None:
        out = normalize_failure_codes_in_payload(
            {"items": [{"failure_code": "Receipt-Not-Found"}]},
        )
        self.assertEqual(out["items"][0]["failure_code"], "receipt_not_found")


if __name__ == "__main__":
    unittest.main()
