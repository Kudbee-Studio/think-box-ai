"""Environment caps for Think Job SSE (PR #137)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from backend.api.v1.run_job_status_stream import clamp_stream_query_params


class TestStreamEnvCap(unittest.TestCase):
    def test_thinkbox_stream_max_events_env(self) -> None:
        with patch.dict(os.environ, {"THINKBOX_STREAM_MAX_EVENTS": "8"}):
            limits = clamp_stream_query_params(64, 120.0, 15.0)
        self.assertEqual(limits.max_events, 8)


if __name__ == "__main__":
    unittest.main()
