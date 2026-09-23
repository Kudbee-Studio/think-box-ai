"""Stream query clamp validation (PR #137)."""

from __future__ import annotations

import unittest

from backend.validation import clamp_stream_scalar


class TestValidationStream(unittest.TestCase):
    def test_clamp_stream_scalar_defaults_on_bad_input(self) -> None:
        self.assertEqual(clamp_stream_scalar("nope", default=10.0, minimum=1.0, maximum=20.0), 10.0)

    def test_clamp_stream_scalar_bounds(self) -> None:
        self.assertEqual(clamp_stream_scalar(999, default=10.0, minimum=1.0, maximum=64.0), 64.0)


if __name__ == "__main__":
    unittest.main()
