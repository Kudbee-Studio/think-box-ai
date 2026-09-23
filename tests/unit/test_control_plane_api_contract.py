"""Unit tests for control-plane API contract (PR #154)."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_api_contract import (
    CONTROL_PLANE_API_VERSION,
    error_envelope,
    success_envelope,
    validate_operation_create_body,
    validate_required_fields,
)


class TestControlPlaneApiContract(unittest.TestCase):
    def test_api_version_constant(self) -> None:
        self.assertEqual(CONTROL_PLANE_API_VERSION, "control-plane-api-v1")

    def test_validate_required_fields_ok(self) -> None:
        self.assertEqual(validate_required_fields({"x": "1"}, ("x",)), [])

    def test_validate_required_fields_missing(self) -> None:
        v = validate_required_fields({}, ("x",))
        self.assertEqual(v[0].code, "missing_field")

    def test_validate_operation_body_ok(self) -> None:
        self.assertEqual(
            validate_operation_create_body(
                {"action_type": "a", "operation_id": "op1"},
            ),
            [],
        )

    def test_validate_operation_body_missing_id(self) -> None:
        v = validate_operation_create_body({"action_type": "a"})
        self.assertTrue(any(x.field == "operation_id" for x in v))

    def test_error_envelope_shape(self) -> None:
        from thinkbox.control_plane_api_contract import ControlPlaneApiError

        body = error_envelope(ControlPlaneApiError(code="x", message="y"))
        self.assertFalse(body["ok"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["api_version"], CONTROL_PLANE_API_VERSION)

    def test_success_envelope_shape(self) -> None:
        body = success_envelope({"state": "ok"})
        self.assertTrue(body["ok"])
        self.assertEqual(body["data"]["state"], "ok")


if __name__ == "__main__":
    unittest.main()
