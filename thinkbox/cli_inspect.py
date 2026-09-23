"""KUDBEECLI Phase 1 — hermetic inspection helpers (swarm, ledger, proof, env, sessions).

Read-only surfaces for governance evidence. No live provider execution.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from thinkbox.ledger import ActionLedger
from thinkbox.org_memory_receipts import redact_mapping
from thinkbox.path_safe import display_path, resolve_under_roots, repo_root
from thinkbox.substrate import SubstrateProbe, detect_substrate
from thinkbox.swarm_stats import (
    convergence_summary,
    load_and_validate_proof,
    proof_metrics,
    validate_proof_document,
)

CLI_EXIT_OK = 0
CLI_EXIT_FAIL = 1
CLI_EXIT_USAGE = 2

_REPO_ROOT = repo_root()
_DEFAULT_PROOF_DIR = _REPO_ROOT / "data" / "thinkboxmd"
_DEFAULT_DB_DIR = _REPO_ROOT / "data" / "thinkboxmd" / "db"

_SENSITIVE_ENV_RE = re.compile(
    r"(token|secret|password|api[_-]?key|authorization|private[_-]?key)",
    re.IGNORECASE,
)

_WATCHED_ENV_PREFIXES = (
    "THINKBOX_",
    "UPSTASH_",
    "UPCLOUD_",
    "INCEPTION_",
    "OPENAI_",
    "CI",
    "GITHUB_",
    "WEBHOOK_",
)


def repo_root() -> Path:
    """Repository root (parent of ``thinkbox/``)."""
    return _REPO_ROOT


def default_proof_dir() -> Path:
    """Directory containing ``big_swarm_*.json`` proof artifacts."""
    explicit = os.environ.get("THINKBOX_PROOF_DIR", "").strip()
    if explicit:
        return resolve_under_roots(explicit)
    return _DEFAULT_PROOF_DIR


def resolve_proof_file(path: Path) -> Path:
    """Resolve a proof JSON path under repo/data roots."""
    return resolve_under_roots(str(path))


def resolve_ledger_path(explicit: str | None = None) -> Path | None:
    """Resolve ledger SQLite path; ``None`` if no file exists."""
    if explicit:
        try:
            p = resolve_under_roots(explicit, allow_temp_dir=True)
        except PermissionError:
            return None
        return p if p.is_file() else None
    env = os.environ.get("THINKBOX_LEDGER_PATH", "").strip()
    if env:
        try:
            p = resolve_under_roots(env, allow_temp_dir=True)
        except PermissionError:
            return None
        return p if p.is_file() else None
    for name in ("action_ledger.db", "ledger.db"):
        candidate = _DEFAULT_DB_DIR / name
        if candidate.is_file():
            return candidate
    return None


def discover_proof_files(directory: Path, limit: int) -> list[Path]:
    """Return newest ``big_swarm_*.json`` files up to ``limit``."""
    if not directory.is_dir():
        return []
    files = sorted(directory.glob("big_swarm_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[: max(1, limit)] if limit else files


def redacted_environment_snapshot() -> dict[str, Any]:
    """Presence-only snapshot of watched env vars (values redacted)."""
    present: dict[str, str] = {}
    for key, value in sorted(os.environ.items()):
        if not any(key.startswith(p) or key == p for p in _WATCHED_ENV_PREFIXES):
            continue
        if _SENSITIVE_ENV_RE.search(key):
            present[key] = "[SET]" if value else "[EMPTY]"
        else:
            present[key] = "[SET]" if value else "[EMPTY]"
    probe = SubstrateProbe().probe()
    return redact_mapping(
        {
            "substrate": detect_substrate(),
            "substrate_probe": probe.to_dict(),
            "watched_env": present,
            "evidence_label": "inferred",
        }
    )


def ledger_verify_report(path: Path, verbose: bool = False) -> dict[str, Any]:
    """Verify hash chain; include counts when ``verbose``."""
    ledger = ActionLedger(path)
    try:
        ok = ledger.verify()
        entries = ledger.entries(limit=1_000_000)
        report: dict[str, Any] = {
            "path": display_path(path),
            "valid": ok,
            "entry_count": len(entries),
            "evidence_label": "verified" if ok else "inferred",
        }
        if verbose and entries:
            report["latest_entry_id"] = entries[0]["entry_id"]
            report["latest_timestamp"] = entries[0]["timestamp"]
            allowed = sum(1 for e in entries if e["allowed"])
            report["allowed_count"] = allowed
            report["denied_count"] = len(entries) - allowed
        return report
    finally:
        ledger.close()


def proof_check_report(path: Path, metrics_only: bool = False) -> dict[str, Any]:
    """Validate proof JSON; optional metrics-only payload."""
    try:
        safe = resolve_proof_file(path)
    except PermissionError as exc:
        return {"path": str(path), "valid": False, "errors": [str(exc)]}
    if not safe.is_file():
        return {"path": display_path(safe), "valid": False, "errors": ["file not found"]}
    payload, errors = load_and_validate_proof(safe)
    if errors:
        return {"path": display_path(safe), "valid": False, "errors": errors}
    if metrics_only:
        return {"path": display_path(safe), "valid": True, "metrics": dict(proof_metrics(payload))}
    return {
        "path": display_path(safe),
        "valid": True,
        "run_id": payload.get("run_id"),
        "session_id": payload.get("session_id"),
        "metrics": dict(proof_metrics(payload)),
    }


@dataclass(frozen=True)
class SwarmAgentRollup:
    """Aggregated worker roles from one or more proof files."""

    proofs_considered: int
    primary_workers: int
    validator_workers: int
    total_worker_rows: int
    ok_workers: int
    failed_workers: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "proofs_considered": self.proofs_considered,
            "primary_workers": self.primary_workers,
            "validator_workers": self.validator_workers,
            "total_worker_rows": self.total_worker_rows,
            "ok_workers": self.ok_workers,
            "failed_workers": self.failed_workers,
            "evidence_label": "verified" if self.proofs_considered else "inferred",
        }


def swarm_agents_rollup(proof_paths: Sequence[Path]) -> SwarmAgentRollup:
    """Sum worker statistics across proof documents."""
    prim = val = total = ok = failed = 0
    used = 0
    for p in proof_paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if validate_proof_document(data):
            continue
        used += 1
        prim += int(data.get("primary_workers", 0))
        val += int(data.get("validator_workers", 0))
        workers = data.get("workers") or []
        total += len(workers)
        ok += sum(1 for w in workers if w.get("ok"))
        failed += len(workers) - sum(1 for w in workers if w.get("ok"))
    return SwarmAgentRollup(
        proofs_considered=used,
        primary_workers=prim,
        validator_workers=val,
        total_worker_rows=total,
        ok_workers=ok,
        failed_workers=failed,
    )


def swarm_status_summary(proof_paths: Sequence[Path]) -> dict[str, Any]:
    """Convergence-style summary across recent proofs."""
    payloads: list[dict[str, Any]] = []
    for p in proof_paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        errs = validate_proof_document(data)
        if errs:
            continue
        payloads.append(data)
    if not payloads:
        return {
            "proofs_valid": 0,
            "convergence": None,
            "evidence_label": "inferred",
        }
    summary = convergence_summary(payloads)
    return {
        "proofs_valid": len(payloads),
        "convergence": summary,
        "evidence_label": "verified",
    }


def format_human(report: dict[str, Any], title: str) -> str:
    """Simple human-readable block for CLI output."""
    lines = [title, "-" * len(title)]
    for key, value in report.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for k2, v2 in value.items():
                lines.append(f"  {k2}: {v2}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)
