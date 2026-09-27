"""HTTP conditional If-Match / 412 tests (PR #155)."""

from __future__ import annotations

import unittest

from backend.api.v1.http_conditional import (
    conditional_json_response,
    conditional_json_response_if_match,
    if_match_satisfied,
    precondition_failed,
)
from tests.unit.test_http_conditional import _FakeHeaders, _FakeRequest


class TestHttpConditionalPr155(unittest.TestCase):
    def test_precondition_failed_status(self) -> None:
        resp = precondition_failed()
        self.assertEqual(resp.status_code, 412)

    def test_if_match_absent_allows(self) -> None:
        req = _FakeRequest(_FakeHeaders({}))
        self.assertTrue(if_match_satisfied(req, 'W/"abc"'))

    def test_if_match_mismatch_412(self) -> None:
        body = {"ok": True}
        req = _FakeRequest(_FakeHeaders({"if-match": 'W/"wrong"'}))
        resp = conditional_json_response_if_match(req, body, etag='W/"right"')
        self.assertEqual(resp.status_code, 412)

    def test_if_match_match_then_304_on_inm(self) -> None:
        body = {"ok": True}
        etag = 'W/"same"'
        req = _FakeRequest(_FakeHeaders({"if-match": etag, "if-none-match": etag}))
        resp = conditional_json_response_if_match(req, body, etag=etag)
        self.assertEqual(resp.status_code, 304)

    def test_conditional_json_still_304(self) -> None:
        body = {"n": 2}
        first = conditional_json_response(_FakeRequest(_FakeHeaders({})), body)
        tag = first.headers.get("ETag")
        second = conditional_json_response(
            _FakeRequest(_FakeHeaders({"if-none-match": tag or ""})),
            body,
            etag=tag,
        )
        self.assertEqual(second.status_code, 304)


if __name__ == "__main__":
    unittest.main()
