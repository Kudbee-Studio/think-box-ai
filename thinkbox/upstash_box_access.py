"""Bounded Upstash Box access verification (PR #201).

Uses the existing ``UpstashBoxExecutionAdapter`` contract only:

- ``UPSTASH_PUBLIC_BOX_URL``
- ``UPSTASH_PUBLIC_BOX_TOKEN`` (Bearer on POST ``{url}/run``)

Never prints, logs, or returns secret values, token lengths, or
Authorization headers. ``UPSTASH_BOX_API_KEY`` is inventory-only and
is never sent as a credential.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from thinkbox.execution_adapter import (
    ENV_TOKEN,
    ENV_URL,
    ExecutionReceipt,
    UpstashBoxConfig,
    UpstashBoxExecutionAdapter,
)
from thinkbox.kilo_substrate_checklist import is_live_box_url
from thinkbox.repository import Repository

ADAPTER_REQUIRED_KEYS: tuple[str, ...] = (ENV_URL, ENV_TOKEN)
DOCUMENT_ONLY_UNUSED_KEYS: tuple[str, ...] = ("UPSTASH_BOX_API_KEY",)
PROOF_COMMAND = "echo KUD_BEE_UPSTASH_ACCESS_PROOF"
PROOF_JOB_ID = "pr201_upstash_access_probe"
PROOF_ARTIFACT_NAME = "access_proof.json"
HTTP_TIMEOUT_SEC = 10.0

HttpTransport = Callable[[str, str], "HttpProbeResult"]


class AccessClass(str, Enum):
    """Explicit access-test states for PR #201."""

    ENV_NOT_CONFIGURED = "A"
    ENDPOINT_REACHABLE_AUTH_FAILED = "B"
    ENDPOINT_REACHABLE = "C"
    REMOTE_EXECUTION_VERIFIED = "D"
    BLOCKED = "E"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _present(environ: Mapping[str, str], key: str) -> bool:
    raw = environ.get(key)
    return bool(raw and str(raw).strip())


def presence_inventory(
    environ: Mapping[str, str] | None = None,
    extra_keys: tuple[str, ...] = (),
) -> dict[str, bool]:
    """Return env key names mapped to present/absent only."""
    env = os.environ if environ is None else environ
    keys = ADAPTER_REQUIRED_KEYS + DOCUMENT_ONLY_UNUSED_KEYS + extra_keys
    return {key: _present(env, key) for key in keys}


def endpoint_identity(url: str | None) -> dict[str, Any] | None:
    """Host-only identity. Drops userinfo, query, fragment, and path."""
    if not url or not str(url).strip():
        return None
    parsed = urlparse(str(url).strip())
    host = parsed.hostname or ""
    if parsed.username or parsed.password:
        return {
            "scheme": parsed.scheme or "",
            "hostname": host or None,
            "has_userinfo": True,
            "host_suffix_box_upstash": host.endswith(".box.upstash.com"),
            "looks_live_box_host": False,
        }
    return {
        "scheme": parsed.scheme or "",
        "hostname": host or None,
        "has_userinfo": False,
        "host_suffix_box_upstash": host.endswith(".box.upstash.com"),
        "looks_live_box_host": is_live_box_url(str(url).strip()),
    }


@dataclass(frozen=True)
class HttpProbeResult:
    """Sanitized HTTP outcome — status and reason class only."""

    status: int | None
    reason_class: str
    error_type: str = ""


def classify_http_body_reason(status: int | None, body: str) -> str:
    """Map a short public body to a reason class. Never return the body."""
    if status == 401:
        return "unauthorized"
    if status == 403:
        return "forbidden"
    if status == 200:
        return "ok"
    snippet = (body or "").strip().lower()
    if status == 404 and snippet == "preview not found":
        return "preview_not_found"
    if status == 404:
        return "not_found"
    if status is None:
        return "network_error"
    return "other"


def default_http_transport(url: str, method: str = "GET") -> HttpProbeResult:
    """Unauthenticated probe. Does not attach Authorization."""
    req = urllib.request.Request(url, method=method.upper(), headers={"Accept": "text/plain"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as resp:
            raw = resp.read(64)
            status = int(getattr(resp, "status", 200) or 200)
            reason = classify_http_body_reason(status, raw.decode("utf-8", errors="replace"))
            return HttpProbeResult(status=status, reason_class=reason)
    except urllib.error.HTTPError as exc:
        raw = exc.read(64) if exc.fp is not None else b""
        body = raw.decode("utf-8", errors="replace") if raw else ""
        status = int(exc.code)
        return HttpProbeResult(
            status=status,
            reason_class=classify_http_body_reason(status, body),
            error_type="HTTPError",
        )
    except urllib.error.URLError as exc:
        return HttpProbeResult(
            status=None,
            reason_class="network_error",
            error_type=type(exc.reason).__name__ if exc.reason else "URLError",
        )
    except TimeoutError:
        return HttpProbeResult(status=None, reason_class="timeout", error_type="TimeoutError")


def _redact_receipt(receipt: ExecutionReceipt) -> dict[str, Any]:
    return {
        "job_id": receipt.job_id,
        "execution_id": receipt.execution_id,
        "provider": receipt.provider,
        "status": receipt.status,
        "verified": receipt.verified,
        "exit_code": receipt.exit_code,
        "artifact_path_empty": receipt.artifact_path == "",
        "checkpoint_id_empty": receipt.checkpoint_id == "",
        "checkpoint_id": receipt.checkpoint_id or None,
        "start_time": receipt.start_time,
        "end_time": receipt.end_time,
        "error_is_config_absent": receipt.error
        == f"{ENV_URL} or {ENV_TOKEN} absent",
        "provenance": list(receipt.provenance),
    }


def classify_access(
    *,
    url_present: bool,
    token_present: bool,
    http_result: HttpProbeResult | None,
    receipt_status: str | None,
    receipt_verified: bool,
) -> tuple[AccessClass, str]:
    """Map probe facts onto A–E. HTTP reachability alone is never D."""
    if not url_present or not token_present:
        missing = []
        if not url_present:
            missing.append(ENV_URL)
        if not token_present:
            missing.append(ENV_TOKEN)
        return (
            AccessClass.ENV_NOT_CONFIGURED,
            "absent: " + ", ".join(missing),
        )

    if receipt_status == "COMPLETED" and receipt_verified:
        return (
            AccessClass.REMOTE_EXECUTION_VERIFIED,
            "adapter receipt COMPLETED and hash-verified",
        )

    if http_result is not None:
        if http_result.reason_class in {"unauthorized", "forbidden"} or http_result.status in {
            401,
            403,
        }:
            return (
                AccessClass.ENDPOINT_REACHABLE_AUTH_FAILED,
                f"HTTP {http_result.status} auth rejected",
            )
        if http_result.reason_class == "preview_not_found":
            return (
                AccessClass.BLOCKED,
                "endpoint returned preview not found",
            )
        if http_result.reason_class == "timeout":
            return (AccessClass.BLOCKED, "endpoint probe timed out")
        if http_result.status is None:
            return (
                AccessClass.BLOCKED,
                f"endpoint unreachable ({http_result.error_type or 'network_error'})",
            )
        if http_result.status == 200 and receipt_status != "COMPLETED":
            return (
                AccessClass.ENDPOINT_REACHABLE,
                "endpoint HTTP 200 without verified remote execution",
            )

    if receipt_status == "REMOTE_FAILED":
        return (AccessClass.BLOCKED, "adapter REMOTE_FAILED after configured POST /run")
    if receipt_status == "ARTIFACT_MISMATCH":
        return (AccessClass.BLOCKED, "remote response artifact hash mismatch")
    if receipt_status == "EXIT_FAILED":
        return (AccessClass.BLOCKED, "remote execution non-zero exit")
    return (AccessClass.BLOCKED, "configured but no verified remote execution")


@dataclass
class AccessReport:
    """Redacted access-test report. Safe to serialize and commit."""

    timestamp: str
    classification: AccessClass
    blocker: str
    presence: dict[str, bool]
    endpoint: dict[str, Any] | None
    adapter_configured: bool
    detect_substrate: str
    http_called: bool
    http_status: int | None
    http_reason_class: str | None
    execute_attempted: bool
    receipt: dict[str, Any] | None
    live_http_used: bool
    unused_document_only_present: dict[str, bool] = field(default_factory=dict)

    @property
    def live_verified(self) -> bool:
        return (
            self.classification is AccessClass.REMOTE_EXECUTION_VERIFIED
            and self.live_http_used
            and bool(self.receipt and self.receipt.get("verified"))
        )

    @property
    def live_api_called(self) -> bool:
        return self.live_http_used and (self.http_called or self.execute_attempted)

    @property
    def four_state_max(self) -> str:
        if self.live_verified:
            return "LIVE_VERIFIED"
        return "TEST_VERIFIED"

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "pr_number": 201,
            "gate_id": "upstash-box-access-verification",
            "timestamp": self.timestamp,
            "classification": self.classification.value,
            "classification_name": self.classification.name,
            "blocker": self.blocker,
            "presence": dict(self.presence),
            "endpoint": self.endpoint,
            "adapter_configured": self.adapter_configured,
            "detect_substrate": self.detect_substrate,
            "http_called": self.http_called,
            "http_status": self.http_status,
            "http_reason_class": self.http_reason_class,
            "execute_attempted": self.execute_attempted,
            "receipt": self.receipt,
            "live_http_used": self.live_http_used,
            "live_verified": self.live_verified,
            "live_api_called": self.live_api_called,
            "four_state_max": self.four_state_max,
            "unused_document_only_present": dict(self.unused_document_only_present),
            "adapter_required_keys": list(ADAPTER_REQUIRED_KEYS),
            "document_only_unused_keys": list(DOCUMENT_ONLY_UNUSED_KEYS),
            "auth_mechanism": "HTTP Authorization header from env UPSTASH_PUBLIC_BOX_TOKEN on POST {url}/run",
        }


def run_access_probe(
    *,
    environ: Mapping[str, str] | None = None,
    allow_network: bool = False,
    allow_execute: bool = False,
    http_transport: HttpTransport | None = None,
    live_http_used: bool = False,
) -> AccessReport:
    """Run the smallest legitimate probe permitted by the current env.

    Network and adapter execute are opt-in. Tests keep both false or inject
    a fake transport. Production/operator runs set ``allow_network`` and
    ``allow_execute`` only when the adapter is configured.
    """
    env = os.environ if environ is None else environ
    presence = presence_inventory(env)
    unused = {key: presence.get(key, False) for key in DOCUMENT_ONLY_UNUSED_KEYS}
    url_present = presence[ENV_URL]
    token_present = presence[ENV_TOKEN]
    config = UpstashBoxConfig.load_from_env(
        **({"url": env.get(ENV_URL, ""), "token": env.get(ENV_TOKEN, "")} if environ is not None else {}),
    )
    if environ is not None:
        config = UpstashBoxConfig(
            url=str(env.get(ENV_URL, "") or ""),
            token=str(env.get(ENV_TOKEN, "") or ""),
            env_url=ENV_URL,
            env_token=ENV_TOKEN,
        )
        if config.url:
            host = urlparse(config.url).hostname or ""
            config.box_id = host.split(".")[0] if host else ""

    from thinkbox.substrate import detect_substrate

    substrate = detect_substrate() if environ is None else (
        (urlparse(config.url).hostname or "upstash-box") if config.url else (
            "upcloud-gpu" if env.get("THINKBOX_UPCLOUD_API_TOKEN") else (
                "ci" if env.get("CI") else "local"
            )
        )
    )

    endpoint = endpoint_identity(config.url) if config.url else None
    http_result: HttpProbeResult | None = None
    http_called = False
    receipt_data: dict[str, Any] | None = None
    execute_attempted = False
    receipt_status: str | None = None
    receipt_verified = False

    # Unauthenticated GET only when a URL exists and the caller opted into network.
    if allow_network and url_present:
        transport = http_transport or default_http_transport
        target = config.url.rstrip("/")
        http_result = transport(target, "GET")
        http_called = True

    # Adapter execute is the existing contract. Unconfigured returns NOT_CONFIGURED
    # without HTTP. Configured POST /run requires allow_execute.
    if allow_execute or not config.is_configured:
        execute_attempted = True
        tmp = tempfile.TemporaryDirectory()
        try:
            repo_path = Path(tmp.name) / "repo"
            repo_path.mkdir()
            _init_throwaway_git(repo_path)
            adapter = UpstashBoxExecutionAdapter(
                repo=Repository(repo_path),
                config=config,
            )
            receipt = adapter.execute(
                job_id=PROOF_JOB_ID,
                command=PROOF_COMMAND,
                artifact_name=PROOF_ARTIFACT_NAME,
            )
            receipt_data = _redact_receipt(receipt)
            receipt_status = receipt.status
            receipt_verified = receipt.verified
        finally:
            tmp.cleanup()

    classification, blocker = classify_access(
        url_present=url_present,
        token_present=token_present,
        http_result=http_result,
        receipt_status=receipt_status,
        receipt_verified=receipt_verified,
    )

    return AccessReport(
        timestamp=_now(),
        classification=classification,
        blocker=blocker,
        presence=presence,
        endpoint=endpoint,
        adapter_configured=config.is_configured,
        detect_substrate=substrate,
        http_called=http_called,
        http_status=None if http_result is None else http_result.status,
        http_reason_class=None if http_result is None else http_result.reason_class,
        execute_attempted=execute_attempted,
        receipt=receipt_data,
        live_http_used=bool(
            live_http_used and config.is_configured and (http_called or execute_attempted)
        ),
        unused_document_only_present=unused,
    )


def _init_throwaway_git(repo_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "pr201-probe"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "pr201-probe@example.invalid"],
        cwd=repo_path,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "pr201-probe"],
        cwd=repo_path,
        check=True,
    )


def write_evidence(report: AccessReport, dest: Path) -> Path:
    """Write a redacted JSON evidence artifact."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = report.to_public_dict()
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dest


def assert_no_secret_material(payload: Mapping[str, Any], environ: Mapping[str, str]) -> None:
    """Fail if any configured secret value leaked into a public payload."""
    dumped = json.dumps(payload, default=str)
    for key in (*ADAPTER_REQUIRED_KEYS, *DOCUMENT_ONLY_UNUSED_KEYS):
        raw = environ.get(key)
        if raw and str(raw).strip() and str(raw).strip() in dumped:
            raise ValueError(f"secret material from {key} leaked into public payload")
    # Flag a real header value, not the documented mechanism sentence.
    if re.search(r"bearer\s+[A-Za-z0-9._\-]{8,}", dumped, re.IGNORECASE):
        raise ValueError("authorization header leaked into public payload")
