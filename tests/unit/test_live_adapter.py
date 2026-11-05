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


class TestProviderConfigDoesNotBypassGate(unittest.TestCase):
    """Provider env vars configure WHERE the adapter calls, not WHETHER it may.

    The ACK gate is the only authorization path. Setting provider env vars
    (base URL, model, API key) must not cause a live call to proceed when the
    flag is absent.
    """

    def test_provider_env_vars_set_but_ack_missing_still_refuses(self) -> None:
        env = {
            "THINKBOX_LIVE_BASE_URL": "http://127.0.0.1:9999",
            "THINKBOX_LIVE_MODEL": "some-model",
            "THINKBOX_LIVE_API_KEY": "sk-fake-but-real-looking-key",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("THINKBOX_LIVE_TRIAL_ACK", None)
            self.assertFalse(live_trial_authorized())
            adapter = ThinkTokenLiveAdapter()
            # Provider config is read, but the gate still blocks the call.
            self.assertEqual(adapter._base_url, "http://127.0.0.1:9999")
            self.assertEqual(adapter._model, "some-model")
            self.assertEqual(adapter._api_key, "sk-fake-but-real-looking-key")
            with mock.patch("urllib.request.urlopen") as m:
                with self.assertRaises(LiveTrialNotAuthorizedError):
                    adapter.complete("hello")
            self.assertFalse(m.called, "must not open a socket when ACK is absent")

    def test_provider_env_vars_precedence(self) -> None:
        # THINKBOX_LIVE_* takes precedence over THINKBOX_OPENAI_COMPAT_*.
        env = {
            "THINKBOX_LIVE_BASE_URL": "http://live.example/v1",
            "THINKBOX_OPENAI_COMPAT_BASE_URL": "http://compat.example/v1",
            "THINKBOX_LIVE_MODEL": "live-model",
            "THINKBOX_DEFAULT_MODEL": "default-model",
            "THINKBOX_LIVE_API_KEY": "live-key",
            "THINKBOX_OPENAI_COMPAT_API_KEY": "compat-key",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            adapter = ThinkTokenLiveAdapter()
            self.assertEqual(adapter._base_url, "http://live.example/v1")
            self.assertEqual(adapter._model, "live-model")
            self.assertEqual(adapter._api_key, "live-key")

    def test_falls_back_to_compat_vars(self) -> None:
        env = {
            "THINKBOX_OPENAI_COMPAT_BASE_URL": "http://compat.example/v1",
            "THINKBOX_DEFAULT_MODEL": "default-model",
            "THINKBOX_OPENAI_COMPAT_API_KEY": "compat-key",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            adapter = ThinkTokenLiveAdapter()
            self.assertEqual(adapter._base_url, "http://compat.example/v1")
            self.assertEqual(adapter._model, "default-model")
            self.assertEqual(adapter._api_key, "compat-key")

    def test_default_provider_is_openai_not_mercury(self) -> None:
        # The adapter must not depend on Mercury. With no provider env vars set,
        # the default points at the generic OpenAI-compatible endpoint.
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in (
                "THINKBOX_LIVE_BASE_URL", "THINKBOX_OPENAI_COMPAT_BASE_URL",
                "THINKBOX_LIVE_MODEL", "THINKBOX_DEFAULT_MODEL",
                "THINKBOX_LIVE_API_KEY", "THINKBOX_OPENAI_COMPAT_API_KEY",
            ):
                os.environ.pop(k, None)
            adapter = ThinkTokenLiveAdapter()
            self.assertIn("openai.com", adapter._base_url)
            self.assertNotIn("inceptionlabs", adapter._base_url)


if __name__ == "__main__":
    unittest.main()
