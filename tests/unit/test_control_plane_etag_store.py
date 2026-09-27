"""PR #140 shared control-plane etag store (hermetic)."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_etag_store import (
    apply_conditional_get_to_store,
    cached_body_for_url,
    deserialize_etag_store,
    etag_body_key,
    if_none_match_header,
    merge_etag_stores,
    prune_etag_store,
    serialize_etag_store,
    store_entry_count,
)


class TestControlPlaneEtagStore(unittest.TestCase):
    def test_apply_and_conditional_header(self) -> None:
        store: dict = {}
        url = "/api/v1/run/jobs/status/digest"
        apply_conditional_get_to_store(
            store,
            url,
            etag='W/"abc"',
            body={"count": 1},
        )
        self.assertEqual(if_none_match_header(store, url), 'W/"abc"')
        body = cached_body_for_url(store, url)
        self.assertEqual(body, {"count": 1})

    def test_merge_prefers_source(self) -> None:
        local = {"/u": "W/1", etag_body_key("/u"): {"a": 1}}
        shared = {"/u": "W/2", etag_body_key("/u"): {"a": 2}, "/v": "W/v"}
        merge_etag_stores(local, shared, prefer_source=True)
        self.assertEqual(local["/u"], "W/2")
        self.assertEqual(local["/v"], "W/v")

    def test_serialize_roundtrip(self) -> None:
        store = {"/x": "W/x", etag_body_key("/x"): {"ok": True}}
        raw = serialize_etag_store(store)
        loaded = deserialize_etag_store(raw)
        self.assertEqual(loaded["/x"], "W/x")
        self.assertEqual(loaded[etag_body_key("/x")], {"ok": True})

    def test_prune_drops_oldest(self) -> None:
        store: dict = {}
        for i in range(300):
            key = f"/url{i}"
            store[key] = f"W/{i}"
            store[etag_body_key(key)] = {"i": i}
        prune_etag_store(store, max_entries=10)
        self.assertLessEqual(store_entry_count(store), 10)


if __name__ == "__main__":
    unittest.main()
