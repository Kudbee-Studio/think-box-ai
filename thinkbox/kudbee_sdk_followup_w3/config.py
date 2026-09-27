"""Fail-closed env-backed SDK wave 3 configuration (PR #191 F03)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from thinkbox.kudbee_sdk_followup_w3.errors import config_error
from thinkbox.kudbee_sdk_followup_w3.redact import redact_mapping


@dataclass(frozen=True)
class SdkFollowupW3Config:
    base_url: str
    webhook_secret_label: str
    request_timeout_s: float
    max_retries: int
    dry_run: bool
    correlation_header: str

    def redacted_summary(self) -> dict[str, str | float | int | bool]:
        return redact_mapping(
            {
                "base_url": self.base_url,
                "webhook_secret_label": self.webhook_secret_label,
                "request_timeout_s": self.request_timeout_s,
                "max_retries": self.max_retries,
                "dry_run": self.dry_run,
                "correlation_header": self.correlation_header,
            },
        )


def load_config_from_env(environ: dict[str, str] | None = None) -> SdkFollowupW3Config:
    env = environ if environ is not None else os.environ
    base_url = (env.get("KUDBEE_SDK_FOLLOWUP_W3_BASE_URL") or "http://127.0.0.1:3000").strip()
    if not base_url.startswith(("http://", "https://")):
        raise config_error("KUDBEE_SDK_FOLLOWUP_W3_BASE_URL must be http(s)", base_url=base_url)
    label = (env.get("KUDBEE_SDK_FOLLOWUP_W3_WEBHOOK_SECRET_LABEL") or "webhook-secret").strip()
    try:
        timeout = float(env.get("KUDBEE_SDK_FOLLOWUP_W3_TIMEOUT_S", "30"))
    except ValueError as exc:
        raise config_error("KUDBEE_SDK_FOLLOWUP_W3_TIMEOUT_S must be numeric") from exc
    if timeout <= 0:
        raise config_error("KUDBEE_SDK_FOLLOWUP_W3_TIMEOUT_S must be positive")
    try:
        max_retries = int(env.get("KUDBEE_SDK_FOLLOWUP_W3_MAX_RETRIES", "2"))
    except ValueError as exc:
        raise config_error("KUDBEE_SDK_FOLLOWUP_W3_MAX_RETRIES must be int") from exc
    if max_retries < 0 or max_retries > 8:
        raise config_error("KUDBEE_SDK_FOLLOWUP_W3_MAX_RETRIES out of range 0..8")
    dry_run = env.get("KUDBEE_SDK_FOLLOWUP_W3_DRY_RUN", "").lower() in ("1", "true", "yes")
    header = (env.get("KUDBEE_SDK_FOLLOWUP_W3_CORRELATION_HEADER") or "x-kudbee-correlation-id").strip()
    return SdkFollowupW3Config(
        base_url=base_url.rstrip("/"),
        webhook_secret_label=label,
        request_timeout_s=timeout,
        max_retries=max_retries,
        dry_run=dry_run,
        correlation_header=header,
    )
