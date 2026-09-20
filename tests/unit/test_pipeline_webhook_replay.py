from __future__ import annotations

import unittest

from thinkbox.pipeline_webhook_replay import register_delivery, reset_replay_cache


class TestWebhookReplay(unittest.TestCase):
    def setUp(self) -> None:
        reset_replay_cache()

    def test_duplicate_delivery_suppressed(self) -> None:
        self.assertTrue(register_delivery("d1"))
        self.assertFalse(register_delivery("d1"))


if __name__ == "__main__":
    unittest.main()
