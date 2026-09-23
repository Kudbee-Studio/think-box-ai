"""Unit tests for conditional JSON responses (PR #135)."""

from __future__ import annotations

import unittest

from backend.api.v1.http_conditional import conditional_json_response


class _FakeHeaders:
    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = {k.lower(): v for k, v in mapping.items()}

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._mapping.get(key.lower(), default)


class _FakeRequest:
    def __init__(self, headers: _FakeHeaders) -> None:
        self.headers = headers


class TestConditionalJson(unittest.TestCase):
    def test_returns_304_when_etag_matches(self) -> None:
        body = {"status": "ok", "n": 1}
        first = conditional_json_response(_FakeRequest(_FakeHeaders({})), body)
        etag = first.headers.get("ETag")
        self.assertIsNotNone(etag)
        second = conditional_json_response(
            _FakeRequest(_FakeHeaders({"if-none-match": etag or ""})),
            body,
            etag=etag,
        )
        self.assertEqual(second.status_code, 304)


if __name__ == "__main__":
    unittest.main()
