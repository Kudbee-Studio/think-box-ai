"""Webhook HMAC dry-run verification (PR #191 F13). No live HTTP."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from thinkbox.kudbee_sdk_followup_w3.errors import webhook_error
from thinkbox.kudbee_sdk_followup_w3.observability import get_metrics


@dataclass(frozen=True)
class WebhookVerifyResult:
    valid: bool
    algorithm: str
    dry_run: bool


def parse_signature_header(header_value: str) -> tuple[str, str]:
    value = header_value.strip()
    if "=" not in value:
        raise webhook_error("malformed signature header")
    algorithm, digest = value.split("=", 1)
    return algorithm, digest


def sign_payload(secret: bytes, body: bytes, algorithm: str = "sha256") -> str:
    if algorithm != "sha256":
        raise webhook_error("unsupported algorithm", algorithm=algorithm)
    digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(
    secret: bytes,
    body: bytes,
    header_value: str,
    *,
    dry_run: bool = True,
) -> WebhookVerifyResult:
    get_metrics().record_request()
    expected = sign_payload(secret, body)
    valid = hmac.compare_digest(expected, header_value.strip())
    if not valid and not dry_run:
        raise webhook_error("signature mismatch")
    get_metrics().webhook_verifications += 1
    return WebhookVerifyResult(valid=valid, algorithm="sha256", dry_run=dry_run)
