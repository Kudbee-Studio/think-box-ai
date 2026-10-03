"""Redacting live-proof bundle builder for governed ``upcloud-ssh`` runs.

Reads the raw evidence a real governed run leaves on disk (a hash-verified
``governed_exec`` artifact, its receipt, and the repository checkpoint), rebuilds
a redacted, committed bundle, and refuses to emit it unless every check passes:

* the artifact is re-hashed and must match the receipt's recorded hash;
* the receipt must be ``COMPLETED`` and ``verified``;
* no private key block, bearer token, API key or key path may appear anywhere;
* only allow-listed fields survive; absolute workspace paths never do.

The bundle is written to ``docs/evidence/live-proof/<execution_id>.json`` plus a
human-readable ``.md`` summary. The module is pure except for the two writers, so
it is unit-testable without a network or a real worker.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from thinkbox.execution_adapter import _sha256_file
from thinkbox.local_execution_adapter import receipt_to_public_dict
from thinkbox.upcloud_ssh_execution_adapter import UPCLOUD_SSH_PROVIDER

__all__ = (
    "BUNDLE_SCHEMA_VERSION",
    "EVIDENCE_DIR_REL",
    "LiveProofBundleError",
    "LiveProofBundleResult",
    "build_live_proof_bundle",
    "default_evidence_dir",
    "scan_for_secrets",
    "write_live_proof_bundle",
)

BUNDLE_SCHEMA_VERSION = 1
EVIDENCE_DIR_REL = Path("docs/evidence/live-proof")

# Fields copied verbatim from the artifact payload. Anything not listed is dropped.
_ARTIFACT_ALLOWLIST: tuple[str, ...] = (
    "provider",
    "execution_id",
    "job_id",
    "exit_code",
    "timed_out",
    "intent_fingerprint",
    "command_argv_preview",
    "elapsed_s",
    "stdout",
    "stderr",
    "stdout_truncated",
    "stderr_truncated",
)

# Field names that must never appear in a bundle, at any depth.
_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "private_key_path",
        "key_path",
        "private_key",
        "password",
        "api_key",
        "token",
        "secret",
        "path",
        "artifact_path",
        "receipt_path",
        "remote_user",
    }
)

_PRIVATE_KEY_BLOCK = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_BEARER = re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}", re.IGNORECASE)
_API_KEY = re.compile(r"\b(sk-|ucat_|ghp_|gho_)[A-Za-z0-9]{16,}")
_UPSTASH_TOKEN = re.compile(r"UPSTASH_[A-Z_]*TOKEN\s*=\s*\S+")
_SSH_KEY_HINT = re.compile(r"[~/.]{1,2}[^\s]*\.ssh/\S+")


class LiveProofBundleError(Exception):
    """Raised when a raw run cannot become a safe committed bundle."""


def default_evidence_dir(repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else Path.cwd()
    return root / EVIDENCE_DIR_REL


def scan_for_secrets(text: str) -> list[str]:
    """Return the names of every secret pattern found in ``text`` (empty when clean)."""
    hits: list[str] = []
    if _PRIVATE_KEY_BLOCK.search(text):
        hits.append("private_key_block")
    if _BEARER.search(text):
        hits.append("bearer_token")
    if _API_KEY.search(text):
        hits.append("api_key")
    if _UPSTASH_TOKEN.search(text):
        hits.append("upstash_token")
    if _SSH_KEY_HINT.search(text):
        hits.append("ssh_key_path")
    return hits


def _walk_forbidden_keys(node: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(node, Mapping):
        for key, value in node.items():
            key_str = str(key)
            dotted = f"{prefix}.{key_str}" if prefix else key_str
            if key_str in _FORBIDDEN_KEYS:
                found.append(dotted)
            found.extend(_walk_forbidden_keys(value, dotted))
    elif isinstance(node, list | tuple):
        for idx, value in enumerate(node):
            found.extend(_walk_forbidden_keys(value, f"{prefix}[{idx}]"))
    return found


@dataclass(frozen=True)
class LiveProofBundleResult:
    """A validated, redacted bundle ready to commit."""

    execution_id: str
    bundle: dict[str, Any]
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LiveProofBundleError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LiveProofBundleError(f"invalid json: {path}") from exc
    if not isinstance(data, dict):
        raise LiveProofBundleError(f"expected a json object: {path}")
    return data


def _redact_artifact(raw: Mapping[str, Any]) -> dict[str, Any]:
    payload = {key: raw.get(key) for key in _ARTIFACT_ALLOWLIST if key in raw}
    raw_host = raw.get("remote_host")
    # Keep the worker's public address only when it is the known worker-02 IP.
    payload["remote_host_known"] = raw_host == "209.50.51.174"
    payload["remote_host"] = raw_host if payload["remote_host_known"] else "<redacted-host>"
    return payload


def build_live_proof_bundle(
    artifact_path: Path,
    receipt: Mapping[str, Any],
    checkpoint: Mapping[str, Any] | None,
    *,
    recorded_at: str,
) -> LiveProofBundleResult:
    """Validate raw run evidence and return the redacted bundle.

    Raises :class:`LiveProofBundleError` on any failed check. ``receipt`` may be
    the raw receipt snapshot or a public dict; only its safe fields are read.
    """
    raw = _load_json(artifact_path)

    recorded_hash = str(receipt.get("artifact_hash") or "")
    if not recorded_hash:
        raise LiveProofBundleError("receipt has no artifact_hash")
    actual_hash = _sha256_file(artifact_path)
    if actual_hash != recorded_hash:
        raise LiveProofBundleError(
            f"artifact hash mismatch: recorded {recorded_hash[:12]}… actual {actual_hash[:12]}…"
        )

    status = str(receipt.get("status") or "")
    if status != "COMPLETED":
        raise LiveProofBundleError(f"receipt status is not COMPLETED: {status!r}")
    if not receipt.get("verified"):
        raise LiveProofBundleError("receipt verified is not true")

    if str(raw.get("provider") or "") != UPCLOUD_SSH_PROVIDER:
        raise LiveProofBundleError(f"artifact provider is not {UPCLOUD_SSH_PROVIDER}")

    redacted_artifact = _redact_artifact(raw)
    safe_receipt = receipt_to_public_dict(_receipt_from_mapping(receipt))
    # The public receipt dict hardcodes these false for the generic adapter; inside
    # a verified bundle the receipt mirrors the bundle's own conclusion.
    safe_receipt["live_verified"] = True
    safe_receipt["live_api_called"] = True

    checkpoint_summary: dict[str, Any] = {}
    if checkpoint is not None:
        meta = checkpoint.get("metadata") if isinstance(checkpoint.get("metadata"), Mapping) else {}
        safe_meta_keys = sorted(str(k) for k in meta if str(k) not in _FORBIDDEN_KEYS)
        checkpoint_summary = {
            "checkpoint_id": checkpoint.get("checkpoint_id"),
            "git_branch": checkpoint.get("git_branch"),
            "head": checkpoint.get("head"),
            "metadata_keys": safe_meta_keys,
        }

    bundle: dict[str, Any] = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "evidence_label": "verified",
        "live_verified": True,
        "live_api_called": True,
        "provider": UPCLOUD_SSH_PROVIDER,
        "execution_id": raw.get("execution_id"),
        "job_id": raw.get("job_id"),
        "artifact_sha256": actual_hash,
        "artifact": redacted_artifact,
        "receipt": safe_receipt,
        "checkpoint": checkpoint_summary,
        "redactions": ["artifact_path", "receipt_path", "workspace_path", "remote_user"],
        "recorded_at": recorded_at,
    }

    serialized = json.dumps(bundle, sort_keys=True)
    secret_hits = scan_for_secrets(serialized)
    if secret_hits:
        raise LiveProofBundleError(f"secret patterns in bundle: {', '.join(secret_hits)}")

    forbidden = _walk_forbidden_keys(bundle)
    if forbidden:
        raise LiveProofBundleError(f"forbidden keys in bundle: {', '.join(sorted(set(forbidden)))}")

    warnings: list[str] = []
    if checkpoint is None:
        warnings.append("checkpoint_missing")
    return LiveProofBundleResult(
        execution_id=str(raw.get("execution_id") or ""),
        bundle=bundle,
        warnings=tuple(warnings),
    )


def _receipt_from_mapping(receipt: Mapping[str, Any]) -> Any:
    """Wrap a receipt mapping so ``receipt_to_public_dict`` can read it."""
    from thinkbox.execution_adapter import ExecutionReceipt

    return ExecutionReceipt(
        job_id=str(receipt.get("job_id") or ""),
        execution_id=str(receipt.get("execution_id") or ""),
        provider=str(receipt.get("provider") or ""),
        status=str(receipt.get("status") or ""),
        verified=bool(receipt.get("verified")),
        exit_code=receipt.get("exit_code"),
        start_time=str(receipt.get("start_time") or ""),
        end_time=str(receipt.get("end_time") or ""),
        artifact_name=str(receipt.get("artifact_name") or ""),
        artifact_hash=str(receipt.get("artifact_hash") or ""),
        artifact_path="<redacted>" if receipt.get("artifact_path") else "",
        checkpoint_id=str(receipt.get("checkpoint_id") or ""),
        receipt_path="<redacted>" if receipt.get("receipt_path") else "",
        error="",
        provenance=list(receipt.get("provenance") or []),
    )


def _render_markdown(bundle: Mapping[str, Any]) -> str:
    artifact = bundle.get("artifact") or {}
    lines = [
        "# Live-proof bundle",
        "",
        f"- **provider:** `{bundle.get('provider')}`",
        f"- **execution_id:** `{bundle.get('execution_id')}`",
        f"- **artifact sha256:** `{bundle.get('artifact_sha256')}`",
        f"- **recorded_at:** {bundle.get('recorded_at')}",
        f"- **live_verified:** {bundle.get('live_verified')}",
        "",
        "## Command",
        "",
        f"`{' '.join(str(a) for a in artifact.get('command_argv_preview') or [])}`",
        "",
        "## Result",
        "",
        f"- exit_code: `{artifact.get('exit_code')}`",
        f"- timed_out: `{artifact.get('timed_out')}`",
        f"- elapsed_s: `{artifact.get('elapsed_s')}`",
        "",
        "## stdout",
        "",
        "```",
        str(artifact.get("stdout") or "").rstrip(),
        "```",
        "",
        "> This bundle is redacted from a real governed `upcloud-ssh` run. The raw",
        "> artifact, receipt and checkpoint stay in `.thinkbox/` (git-ignored).",
        "",
    ]
    return "\n".join(lines)


def write_live_proof_bundle(
    result: LiveProofBundleResult,
    evidence_dir: Path,
) -> tuple[Path, Path]:
    """Write the JSON bundle and its Markdown summary; returns both paths."""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stem = result.execution_id or "unknown"
    json_path = evidence_dir / f"{stem}.json"
    md_path = evidence_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(result.bundle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(_render_markdown(result.bundle), encoding="utf-8")
    return json_path, md_path
