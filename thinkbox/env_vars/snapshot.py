"""Redacted environment snapshots (PR #200)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from thinkbox.env_vars.profile import detect_profile
from thinkbox.env_vars.redact import redact_environ_for_display, redact_nested


def watched_prefixes() -> tuple[str, ...]:
    return (
        "THINKBOX_",
        "UPSTASH_",
        "INCEPTION_",
        "KUDBEE_",
        "GOVERNANCE_",
        "THINKBOX_CLOUD_EXEC_",
    )


def filter_watched(environ: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, val in environ.items():
        if any(key.startswith(p) or key == p for p in watched_prefixes()):
            out[key] = val
    return out


def build_redacted_snapshot(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = dict(environ if environ is not None else os.environ)
    watched = filter_watched(env)
    return redact_nested(
        {
            "profile": detect_profile(env).value,
            "watched_env": redact_environ_for_display(watched),
            "watched_key_count": len(watched),
            "live_verified": False,
            "live_api_called": False,
            "evidence_label": "inferred",
        }
    )
