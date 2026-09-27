"""Fail-closed env-backed SDK configuration (PR #179 F03)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from thinkbox.kudbee_sdk_followup.errors import config_error
from thinkbox.kudbee_sdk_followup.redact import redact_mapping


@dataclass(frozen=True)
class SdkFollowupConfig:
    """Hermetic SDK settings for the thinkbox CLI and local tooling."""

    base_url: str
    ws_path: str
    request_timeout_s: float
    max_retries: int
    dry_run: bool
    correlation_header: str

    def redacted_summary(self) -> dict[str, str | float | int | bool]:
        return redact_mapping(
            {
                "base_url": self.base_url,
                "ws_path": self.ws_path,
                "request_timeout_s": self.request_timeout_s,
                "max_retries": self.max_retries,
                "dry_run": self.dry_run,
                "correlation_header": self.correlation_header,
            },
        )


def load_config_from_env(environ: dict[str, str] | None = None) -> SdkFollowupConfig:
    env = environ if environ is not None else os.environ
    base_url = (env.get("KUDBEE_SDK_FOLLOWUP_BASE_URL") or "http://127.0.0.1:3000").strip()
    if not base_url.startswith(("http://", "https://")):
        raise config_error("KUDBEE_SDK_FOLLOWUP_BASE_URL must be http(s)", base_url=base_url)
    ws_path = (env.get("KUDBEE_SDK_FOLLOWUP_WS_PATH") or "/ws").strip()
    if not ws_path.startswith("/"):
        raise config_error("KUDBEE_SDK_FOLLOWUP_WS_PATH must start with /", ws_path=ws_path)
    try:
        timeout = float(env.get("KUDBEE_SDK_FOLLOWUP_TIMEOUT_S", "30"))
    except ValueError as exc:
        raise config_error("KUDBEE_SDK_FOLLOWUP_TIMEOUT_S must be numeric") from exc
    if timeout <= 0:
        raise config_error("KUDBEE_SDK_FOLLOWUP_TIMEOUT_S must be positive")
    try:
        max_retries = int(env.get("KUDBEE_SDK_FOLLOWUP_MAX_RETRIES", "2"))
    except ValueError as exc:
        raise config_error("KUDBEE_SDK_FOLLOWUP_MAX_RETRIES must be int") from exc
    if max_retries < 0 or max_retries > 8:
        raise config_error("KUDBEE_SDK_FOLLOWUP_MAX_RETRIES out of range 0..8")
    dry_run = env.get("KUDBEE_SDK_FOLLOWUP_DRY_RUN", "").lower() in ("1", "true", "yes")
    header = (env.get("KUDBEE_SDK_FOLLOWUP_CORRELATION_HEADER") or "x-kudbee-correlation-id").strip()
    return SdkFollowupConfig(
        base_url=base_url.rstrip("/"),
        ws_path=ws_path,
        request_timeout_s=timeout,
        max_retries=max_retries,
        dry_run=dry_run,
        correlation_header=header,
    )
