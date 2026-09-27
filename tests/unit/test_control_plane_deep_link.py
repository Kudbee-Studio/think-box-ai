"""PR #140 deep-link into receipt-keyed watch."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_deep_link import (
    DeepLinkError,
    assert_deep_link_watchable,
    build_think_job_watch_href,
    merge_deep_link_sources,
    parse_watch_deep_link_hash,
    parse_watch_deep_link_query,
)


class TestControlPlaneDeepLink(unittest.TestCase):
    def test_build_href_query(self) -> None:
        href = build_think_job_watch_href(receipt_id="tb_sess_rcpt_abc12345")
        self.assertIn("think_job_status.html?", href)
        self.assertIn("receipt_id=", href)
        self.assertIn("auto_watch=1", href)
        self.assertIn("from=receipts.html", href)

    def test_build_href_hash_mode(self) -> None:
        href = build_think_job_watch_href(
            receipt_id="tb_sess_rcpt_abc12345",
            use_hash_for_receipt=True,
        )
        self.assertTrue(href.startswith("think_job_status.html#"))

    def test_parse_query_and_hash_merge(self) -> None:
        link = merge_deep_link_sources(
            query_string="engine_id=eng1",
            hash_fragment="receipt_id=tb_sess_rcpt_deadbeef",
        )
        self.assertEqual(link.receipt_id, "tb_sess_rcpt_deadbeef")
        self.assertEqual(link.engine_id, "eng1")
        self.assertTrue(link.auto_watch)

    def test_invalid_receipt_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            parse_watch_deep_link_query("receipt_id=receipt_missing_xyz")

    def test_assert_watchable(self) -> None:
        link = parse_watch_deep_link_query("receipt_id=tb_sess_rcpt_ok")
        assert_deep_link_watchable(link)

    def test_missing_target_raises(self) -> None:
        with self.assertRaises(DeepLinkError):
            build_think_job_watch_href(receipt_id="", engine_id="")


if __name__ == "__main__":
    unittest.main()
