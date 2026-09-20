from __future__ import annotations

import unittest

from thinkbox.pipeline_ci_timeline import validate_ci_timeline


class TestCITimeline(unittest.TestCase):
    def test_chronological_ok(self) -> None:
        events = [
            {"timestamp": "2026-01-01T00:00:00+00:00", "conclusion": "success"},
            {"timestamp": "2026-01-02T00:00:00+00:00", "conclusion": "success"},
        ]
        v = validate_ci_timeline(events)
        self.assertTrue(v["chronological"])
        self.assertTrue(v["complete"])


if __name__ == "__main__":
    unittest.main()
