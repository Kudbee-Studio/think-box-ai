"""Jobs digest multiplex panel state (PR #139)."""

from __future__ import annotations

import unittest

from thinkbox.think_job_status_ui import (
    MultiplexPanelState,
    TransportMode,
    WatchKeyKind,
    WatchTarget,
    apply_digest_stream_event,
    merge_jobs_list_into_panel,
    multiplex_chip_label,
)


class TestDigestStreamMerge(unittest.TestCase):
    def test_hello_sets_revision(self) -> None:
        panel = MultiplexPanelState()
        changed = apply_digest_stream_event(
            panel,
            {
                "kind": "think_jobs_stream_hello",
                "digest": {"count": 2, "dashboard_revision": 9},
            },
        )
        self.assertTrue(changed)
        self.assertEqual(panel.dashboard_revision, 9)
        self.assertEqual(panel.digest_document["count"], 2)

    def test_delta_updates(self) -> None:
        panel = MultiplexPanelState()
        apply_digest_stream_event(
            panel,
            {"kind": "think_jobs_digest_delta", "dashboard_revision": 10, "digest": {"count": 3}},
        )
        self.assertEqual(panel.dashboard_revision, 10)


class TestMultiplexChip(unittest.TestCase):
    def test_chip_label(self) -> None:
        panel = MultiplexPanelState(
            digest_transport=TransportMode.SSE,
            watch_transport=TransportMode.POLL,
            active_target=WatchTarget(kind=WatchKeyKind.RECEIPT, key="rcpt_long_id_here"),
        )
        label = multiplex_chip_label(panel)
        self.assertIn("digest:sse", label)
        self.assertIn("watch:poll", label)

    def test_merge_jobs_list(self) -> None:
        panel = MultiplexPanelState()
        merge_jobs_list_into_panel(panel, {"jobs": [{"job_id": "j1"}], "dashboard_revision": 4})
        self.assertEqual(len(panel.digest_jobs), 1)
        self.assertEqual(panel.dashboard_revision, 4)


if __name__ == "__main__":
    unittest.main()
