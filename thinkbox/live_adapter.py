"""Thin live adapter for the Think Token trial.

Wraps the existing OpenAI-compatible completion path (Mercury 2 at
api.inceptionlabs.ai) behind a single complete(prompt) method that matches the
harness provider interface in thinkbox/think_token_eval.py.

The adapter is OFF BY DEFAULT. It refuses to make any network call unless
THINKBOX_LIVE_TRIAL_ACK=1 is set in the environment. This is the only gate; no
other code path can reach the network from this module.

The live trial is NOT AUTHORIZED. Setting the flag does not authorize it —
authorization requires a separate founder-issued governance token and an
explicit founder approval that has not been given. This module is a shim that
makes the harness runnable against a real provider when someone chooses to
authorize it; it does not authorize anything itself.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

LIVE_TRIAL_ACK_ENV = "THINKBOX_LIVE_TRIAL_ACK"


def live_trial_authorized() -> bool:
    """True only when the explicit env flag is set to 1 (or yes/true)."""
    return os.environ.get(LIVE_TRIAL_ACK_ENV, "").strip().lower() in ("1", "yes", "true")


class LiveTrialNotAuthorizedError(RuntimeError):
    """Raised when a live call is attempted without the env flag set."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _default_base_url() -> str:
    return os.environ.get(
        "THINKBOX_OPENAI_COMPAT_BASE_URL", "https://api.inceptionlabs.ai/v1"
    )


def _default_model() -> str:
    return os.environ.get("THINKBOX_DEFAULT_MODEL", "openai/gpt-oss-20b")


def _default_api_key() -> str:
    return os.environ.get("THINKBOX_OPENAI_COMPAT_API_KEY", "")


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class ThinkTokenLiveAdapter:
    """Minimal OpenAI-compatible completion adapter.

    Implements complete(prompt) -> str, the only method the evaluation harness
    calls on its provider. It is intentionally thin: it builds one chat
    completion request, posts it, and returns the first choice's message content.

    Network access is gated by live_trial_authorized(). In dry-run mode the
    request payload is printed and no socket is opened.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        dry_run: bool = False,
    ) -> None:
        self._api_key = api_key if api_key is not None else _default_api_key()
        self._base_url = (base_url if base_url is not None else _default_base_url()).rstrip("/")
        self._model = model if model is not None else _default_model()
        self.dry_run = dry_run
        self.calls: list[dict[str, Any]] = []

    # -- public API ---------------------------------------------------------

    def complete(self, prompt: str) -> str:
        """Return the model's completion for prompt.

        Refuses to call the network unless the env flag is set (or dry_run is
        True, which prints the request and returns a sentinel).
        """
        if not live_trial_authorized() and not self.dry_run:
            raise LiveTrialNotAuthorizedError(
                "Live model call refused: set THINKBOX_LIVE_TRIAL_ACK=1 to enable. "
                "The live Think Token trial is NOT AUTHORIZED."
            )
        payload = self._build_payload(prompt)
        if self.dry_run:
            self.calls.append({"mode": "dry_run", "prompt_len": len(prompt)})
            return self._dry_run_response(payload)
        if not self._api_key:
            raise LiveTrialNotAuthorizedError(
                "No THINKBOX_OPENAI_COMPAT_API_KEY configured; cannot call the live provider."
            )
        return self._post(payload)

    # -- internals ----------------------------------------------------------

    def _build_payload(self, prompt: str) -> dict[str, Any]:
        return {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }

    def _dry_run_response(self, payload: dict[str, Any]) -> str:
        # In dry-run mode we never touch the network. We print the exact request
        # and return a sentinel so callers can observe the call path without
        # spending a live request.
        print(
            json.dumps(
                {
                    "mode": "dry_run",
                    "url": self._base_url + "/chat/completions",
                    "payload": payload,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return "[DRY-RUN] no live call made"

    def _post(self, payload: dict[str, Any]) -> str:
        url = self._base_url + "/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        self.calls.append({"mode": "live", "url": url, "prompt_len": len(payload)})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - gated URL
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise LiveTrialNotAuthorizedError(f"Live provider request failed: {exc}") from exc
        choices = body.get("choices") or []
        if not choices:
            raise LiveTrialNotAuthorizedError("Live provider returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise LiveTrialNotAuthorizedError("Live provider returned no message content")
        return content


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in argv
    if not dry_run and not live_trial_authorized():
        print(
            "Refusing live call: THINKBOX_LIVE_TRIAL_ACK is not set. "
            "The live Think Token trial is NOT AUTHORIZED.",
            file=sys.stderr,
        )
        return 2
    adapter = ThinkTokenLiveAdapter(dry_run=dry_run)
    prompt = " ".join(a for a in argv if not a.startswith("--"))
    if not prompt:
        prompt = "Say hello."
    result = adapter.complete(prompt)
    if dry_run:
        print(result)
        return 0
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
