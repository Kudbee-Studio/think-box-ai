"""Unit tests for control_plane_ops_harden (PR #157)."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_ops_harden import (
    IdempotencyConflict,
    IdempotencyRegistry,
    OpsRateLimitExceeded,
    OpsRateLimitWindow,
    clamp_query_limit,
    fingerprint_idempotency_body,
    get_idempotency_registry,
    http_exception_detail,
    redact_mapping_for_logs,
    reset_idempotency_registry,
    reset_ops_rate_limiter,
)
from thinkbox.control_plane_api_contract import ControlPlaneApiError


class TestClampQueryLimit(unittest.TestCase):
    def test_defaults_and_bounds(self) -> None:
        self.assertEqual(clamp_query_limit(None), 50)
        self.assertEqual(clamp_query_limit(0), 1)
        self.assertEqual(clamp_query_limit(999), 200)


class TestRedaction(unittest.TestCase):
    def test_redacts_secret_keys(self) -> None:
        payload = {"api_key": "abcdefghij", "count": 3}
        redacted = redact_mapping_for_logs(payload)
        self.assertNotEqual(redacted["api_key"], "abcdefghij")
        self.assertEqual(redacted["count"], 3)


class TestErrorEnvelope(unittest.TestCase):
    def test_http_exception_detail_shape(self) -> None:
        err = ControlPlaneApiError(code="x", message="y", http_status=400)
        detail = http_exception_detail(err, request_id="req_1")
        self.assertFalse(detail["ok"])
        self.assertFalse(detail["live_api_called"])
        self.assertEqual(detail["request_id"], "req_1")


class TestIdempotency(unittest.TestCase):
    def setUp(self) -> None:
        reset_idempotency_registry()

    def tearDown(self) -> None:
        reset_idempotency_registry()

    def test_fingerprint_stable(self) -> None:
        a = {"operation_id": "1", "action_type": "t"}
        b = {"action_type": "t", "operation_id": "1"}
        self.assertEqual(fingerprint_idempotency_body(a), fingerprint_idempotency_body(b))

    def test_conflict_on_body_change(self) -> None:
        reg = IdempotencyRegistry()
        reg.register("k1", operation_id="op1", body={"operation_id": "op1", "action_type": "a"})
        with self.assertRaises(IdempotencyConflict):
            reg.register("k1", operation_id="op1", body={"operation_id": "op1", "action_type": "b"})


class TestRateLimit(unittest.TestCase):
    def setUp(self) -> None:
        reset_ops_rate_limiter()

    def tearDown(self) -> None:
        reset_ops_rate_limiter()

    def test_rate_limit_trips(self) -> None:
        window = OpsRateLimitWindow(max_per_minute=2)
        window.check("client")
        window.check("client")
        with self.assertRaises(OpsRateLimitExceeded):
            window.check("client")


class TestIdempotencyRegistrySingleton(unittest.TestCase):
    def tearDown(self) -> None:
        reset_idempotency_registry()

    def test_lookup_after_register(self) -> None:
        reset_idempotency_registry()
        reg = get_idempotency_registry()
        reg.register("idem", operation_id="op_x", body={"operation_id": "op_x", "action_type": "t"})
        self.assertEqual(reg.lookup("idem"), "op_x")


if __name__ == "__main__":
    unittest.main()
