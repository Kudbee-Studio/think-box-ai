"""Hermetic tests for thinkbox/live_adapter.py.

The live Think Token trial is NOT AUTHORIZED. These tests prove the adapter
refuses to make any network call unless THINKBOX_LIVE_TRIAL_ACK=1 is set, and
that dry-run mode prints the request payload without opening a socket.
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr
from unittest import mock

from thinkbox.live_adapter import (
    LiveTrialNotAuthorizedError,
    ThinkTokenLiveAdapter,
    live_trial_authorized,
)


class TestLiveTrialGate(unittest.TestCase):
    """The env flag is the only gate; it defaults to off."""

    def test_flag_absent_refuses(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("THINKBOX_LIVE_TRIAL_ACK", None)
            self.assertFalse(live_trial_authorized())
            adapter = ThinkTokenLiveAdapter()
            with self.assertRaises(LiveTrialNotAuthorizedError):
                adapter.complete("hello")

    def test_flag_set_to_1_enables(self) -> None:
        with mock.patch.dict(os.environ, {"THINKBOX_LIVE_TRIAL_ACK": "1"}, clear=False):
            self.assertTrue(live_trial_authorized())

    def test_flag_set_to_yes_enables(self) -> None:
        with mock.patch.dict(os.environ, {"THINKBOX_LIVE_TRIAL_ACK": "yes"}, clear=False):
            self.assertTrue(live_trial_authorized())

    def test_flag_set_to_true_enables(self) -> None:
        with mock.patch.dict(os.environ, {"THINKBOX_LIVE_TRIAL_ACK": "true"}, clear=False):
            self.assertTrue(live_trial_authorized())

    def test_flag_empty_string_disables(self) -> None:
        with mock.patch.dict(os.environ, {"THINKBOX_LIVE_TRIAL_ACK": ""}, clear=False):
            self.assertFalse(live_trial_authorized())

    def test_flag_arbitrary_value_disables(self) -> None:
        with mock.patch.dict(os.environ, {"THINKBOX_LIVE_TRIAL_ACK": "please"}, clear=False):
            self.assertFalse(live_trial_authorized())


class TestDryRunIsHermetic(unittest.TestCase):
    """Dry-run prints the request and never opens a socket."""

    def test_dry_run_does_not_call_network(self) -> None:
        # Even with the flag SET, dry_run must not touch urllib.
        with mock.patch.dict(os.environ, {"THINKBOX_LIVE_TRIAL_ACK": "1"}, clear=False):
            adapter = ThinkTokenLiveAdapter(dry_run=True)
            stderr = io.StringIO()
            with redirect_stderr(stderr), mock.patch("urllib.request.urlopen") as m:
                result = adapter.complete("build a rest endpoint")
            self.assertFalse(m.called, "dry_run must not open a network socket")
            self.assertEqual(result, "[DRY-RUN] no live call made")
            payload = json.loads(stderr.getvalue())
            self.assertEqual(payload["mode"], "dry_run")
            self.assertIn("/chat/completions", payload["url"])
            self.assertEqual(payload["payload"]["messages"][0]["content"], "build a rest endpoint")
            self.assertEqual(payload["payload"]["temperature"], 0.0)

    def test_dry_run_works_without_flag(self) -> None:
        # Dry-run must be usable even when the flag is absent — it is a local
        # inspection tool, not a live call.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("THINKBOX_LIVE_TRIAL_ACK", None)
            adapter = ThinkTokenLiveAdapter(dry_run=True)
            with mock.patch("urllib.request.urlopen") as m:
                result = adapter.complete("hello")
            self.assertFalse(m.called)
            self.assertEqual(result, "[DRY-RUN] no live call made")

    def test_dry_run_records_call(self) -> None:
        with mock.patch.dict(os.environ, {"THINKBOX_LIVE_TRIAL_ACK": "1"}, clear=False):
            adapter = ThinkTokenLiveAdapter(dry_run=True)
            with redirect_stderr(io.StringIO()):
                adapter.complete("a")
            self.assertEqual(len(adapter.calls), 1)
            self.assertEqual(adapter.calls[0]["mode"], "dry_run")


class TestLivePathRequiresKey(unittest.TestCase):
    """When the flag is set but no API key is present, the live path fails
    honestly rather than silently proceeding."""

    def test_live_without_key_raises(self) -> None:
        env = {"THINKBOX_LIVE_TRIAL_ACK": "1", "THINKBOX_OPENAI_COMPAT_API_KEY": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            adapter = ThinkTokenLiveAdapter()
            with self.assertRaises(LiveTrialNotAuthorizedError):
                adapter.complete("hello")


if __name__ == "__main__":
    unittest.main()
