"""Hermetic local environment preparation for the catalog pin bind workflow.

Checks the local Python/SQLite workspace, redacts env, dry-runs the
signed workflow, and persists a prep receipt. Does not call live APIs.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayer,
    MemoryLayerError,
    dry_run_trait_lab_catalog_pin_bind_workflow,
    plan_trait_lab_catalog_pin_bind_workflow,
    query_layer,
    record_task_step,
    write_verified,
)

_PREP_KIND = "trait-lab-local-env-prep"
_PREP_RECEIPT_KIND = "trait-lab-local-env-prep-receipt"
_PREP_FACT_PREFIX = "trait-lab-env-prep-"
_SECRET_PARTS = ("token", "secret", "password", "api_key", "apikey", "authorization", "bearer")

TRAIT_LAB_LOCAL_ENV_PREP_OPS: tuple[str, ...] = (
    "require_python",
    "refuse_live",
    "redact_environ",
    "probe_store",
    "require_no_live_ack",
    "list_checks",
    "count_checks",
    "has_check",
    "page_checks",
    "run_checks",
    "export_report",
    "verify_report",
    "digest",
    "etag",
    "public_row",
    "prepare_workspace",
    "dry_run_workflow",
    "prep_status",
    "persist_receipt",
    "get_receipt",
    "list_receipts",
    "has_receipt",
    "receipts_by_agent",
    "prepare_and_dry_run",
    "require_provenance",
)

TRAIT_LAB_LOCAL_ENV_PREP_CHECKS: tuple[str, ...] = (
    "python",
    "store",
    "no_live_ack",
    "not_live",
    "provenance",
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def refuse_trait_lab_local_env_prep_live(payload: Any) -> None:
    """E02 — prep payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "local env prep may not claim LIVE VERIFIED")


def require_trait_lab_local_env_python(*, minimum: tuple[int, int] = (3, 10)) -> dict[str, Any]:
    """E01 — fail-closed unless this interpreter is Python 3.10+."""
    found = (int(sys.version_info[0]), int(sys.version_info[1]))
    if found < minimum:
        raise MemoryLayerError("invalid_python", f"local env prep requires Python {minimum[0]}.{minimum[1]}+")
    return {
        "ok": True,
        "python": f"{found[0]}.{found[1]}",
        "minimum": f"{minimum[0]}.{minimum[1]}",
        "live_verified": False,
    }


def redact_trait_lab_local_env_environ(environ: Any = None) -> dict[str, str]:
    """E03 — copy env with secret-shaped keys redacted."""
    raw = environ if environ is not None else os.environ
    if not hasattr(raw, "items"):
        raise MemoryLayerError("invalid_environ", "redact requires a mapping")
    out: dict[str, str] = {}
    for key, value in raw.items():
        name = str(key)
        text = str(value)
        lowered = name.lower()
        if any(part in lowered for part in _SECRET_PARTS):
            out[name] = "[REDACTED]"
        else:
            out[name] = text
    return out


def probe_trait_lab_local_env_store(path: Path | str | None = None) -> dict[str, Any]:
    """E04 — open a tempfile MemoryStore, write, read, close."""
    tmp: tempfile.TemporaryDirectory[str] | None = None
    store_path = Path(path) if path is not None else None
    if store_path is None:
        tmp = tempfile.TemporaryDirectory()
        store_path = Path(tmp.name) / "prep.db"
    store = MemoryStore(store_path)
    try:
        write_verified(
            store,
            {
                "id": "trait-lab-env-prep-probe",
                "fact": "local env store probe",
                "how": "probe_trait_lab_local_env_store",
                "confidence": 1.0,
                "source": "local-env-prep",
                "agent_id": "prep",
                "task_id": "probe",
            },
        )
        got = store.get("verified:trait-lab-env-prep-probe")
        if got is None:
            raise MemoryLayerError("missing_store", "local env store probe failed to read")
    finally:
        store.close()
        if tmp is not None:
            tmp.cleanup()
    return {"ok": True, "path": str(store_path), "live_verified": False}


def require_trait_lab_local_env_no_live_ack(environ: Any = None) -> dict[str, Any]:
    """E05 — fail-closed when a swarm live ack is present."""
    raw = environ if environ is not None else os.environ
    ack = str(raw.get("THINKBOX_SWARM_LIVE_ACK") or "").strip()
    if ack:
        raise MemoryLayerError("live_claim", "local env prep refuses THINKBOX_SWARM_LIVE_ACK")
    return {"ok": True, "live_ack": False, "live_verified": False}


def require_trait_lab_local_env_provenance(*, agent_id: str, task_id: str) -> dict[str, Any]:
    """E25 — fail-closed without agent_id and task_id."""
    if not str(agent_id or "").strip() or not str(task_id or "").strip():
        raise MemoryLayerError("missing_provenance", "local env prep requires agent_id and task_id")
    return {"ok": True, "agent_id": agent_id, "task_id": task_id, "live_verified": False}


def list_trait_lab_local_env_prep_checks() -> list[str]:
    """E06 — stable check names."""
    return list(TRAIT_LAB_LOCAL_ENV_PREP_CHECKS)


def count_trait_lab_local_env_prep_checks() -> int:
    """E07 — number of local prep checks."""
    return len(TRAIT_LAB_LOCAL_ENV_PREP_CHECKS)


def trait_lab_local_env_prep_has_check(name: str) -> bool:
    """E08 — true when the check name is in the catalog."""
    wanted = str(name or "").strip()
    if not wanted:
        raise MemoryLayerError("missing_check", "has_check requires a name")
    return wanted in TRAIT_LAB_LOCAL_ENV_PREP_CHECKS


def page_trait_lab_local_env_prep_checks(*, offset: int = 0, limit: int = 50) -> dict[str, Any]:
    """E09 — deterministic check page."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise MemoryLayerError("invalid_offset", "offset must be >= 0")
    names = list_trait_lab_local_env_prep_checks()
    return {
        "kind": _PREP_KIND,
        "checks": names[offset : offset + limit],
        "count": len(names),
        "offset": offset,
        "limit": limit,
        "live_verified": False,
    }


def run_trait_lab_local_env_prep_checks(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
    store_path: Path | str | None = None,
) -> dict[str, Any]:
    """E10 — run every local prep check. Not a live ranking."""
    require_trait_lab_local_env_provenance(agent_id=agent_id, task_id=task_id)
    results = {
        "python": require_trait_lab_local_env_python(),
        "store": probe_trait_lab_local_env_store(store_path),
        "no_live_ack": require_trait_lab_local_env_no_live_ack(environ),
        "not_live": {"ok": True, "live_verified": False},
        "provenance": {"ok": True, "agent_id": agent_id, "task_id": task_id, "live_verified": False},
    }
    refuse_trait_lab_local_env_prep_live({"live_verified": False})
    return {
        "kind": _PREP_KIND,
        "checks": results,
        "count": len(results),
        "ok": all(bool(row.get("ok")) for row in results.values()),
        "live_verified": False,
    }


def _public_check_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "path"}


def _report_body(checks: dict[str, Any]) -> dict[str, Any]:
    public_checks = {name: _public_check_row(row) for name, row in checks.items()}
    return {
        "kind": _PREP_KIND,
        "checks": public_checks,
        "count": len(public_checks),
        "ok": all(bool(row.get("ok")) for row in public_checks.values()),
        "live_verified": False,
    }


def export_trait_lab_local_env_prep_report(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
    store_path: Path | str | None = None,
) -> dict[str, Any]:
    """E11 — portable prep report. Not a live ranking."""
    ran = run_trait_lab_local_env_prep_checks(
        agent_id=agent_id, task_id=task_id, environ=environ, store_path=store_path
    )
    body = _report_body(ran["checks"])
    refuse_trait_lab_local_env_prep_live(body)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "prep_sha256": hashlib.sha256(encoded).hexdigest(),
        "exported_at": _utc(),
    }


def verify_trait_lab_local_env_prep_report(report: Any) -> dict[str, Any]:
    """E12 — rematch prep_sha256 over the stable report body."""
    if not isinstance(report, dict):
        raise MemoryLayerError("invalid_prep", "prep report must be an object")
    if report.get("kind") != _PREP_KIND:
        raise MemoryLayerError("invalid_prep", "kind must be trait-lab-local-env-prep")
    refuse_trait_lab_local_env_prep_live(report)
    if not isinstance(report.get("checks"), dict):
        raise MemoryLayerError("invalid_prep", "checks must be an object")
    sha = str(report.get("prep_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_prep_hash", "verify requires prep_sha256")
    body = _report_body(report["checks"])
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("prep_mismatch", f"prep hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "prep_sha256": sha, "live_verified": False}


def trait_lab_local_env_prep_digest(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> str:
    """E13 — SHA-256 over the stable prep report body."""
    return str(export_trait_lab_local_env_prep_report(agent_id=agent_id, task_id=task_id, environ=environ)["prep_sha256"])


def trait_lab_local_env_prep_etag(*, agent_id: str, task_id: str, environ: Any = None) -> str:
    """E14 — short digest for prep identity."""
    return trait_lab_local_env_prep_digest(agent_id=agent_id, task_id=task_id, environ=environ)[:16]


def public_trait_lab_local_env_prep_row(row: dict[str, Any]) -> dict[str, Any]:
    """E15 — stable report row without agent/task fields."""
    if not isinstance(row, dict) or not row.get("checks"):
        raise MemoryLayerError("invalid_prep", "public row requires a prep report")
    return _report_body(row["checks"])


def prepare_trait_lab_local_env_workspace(root: Path | str | None = None) -> dict[str, Any]:
    """E16 — create a local tempfile workspace and store path."""
    if root is None:
        root = Path(tempfile.mkdtemp(prefix="trait-lab-env-prep-"))
    else:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
    store_path = root / "layers.db"
    return {
        "prepared": True,
        "root": str(root),
        "store_path": str(store_path),
        "live_verified": False,
    }


def dry_run_trait_lab_local_env_workflow(
    store: MemoryStore,
    *,
    agent_id: str = "",
    task_id: str = "",
) -> dict[str, Any]:
    """E17 — dry-run the rematch workflow step. No writes."""
    plan = plan_trait_lab_catalog_pin_bind_workflow(["rematch"])
    ran = dry_run_trait_lab_catalog_pin_bind_workflow(store, plan, agent_id=agent_id, task_id=task_id)
    if ran.get("wrote"):
        raise MemoryLayerError("invalid_prep", "local env dry-run must not write")
    return ran


def trait_lab_local_env_prep_status(result: Any) -> str:
    """E18 — ready, blocked, dry_run, or planned."""
    if not isinstance(result, dict):
        raise MemoryLayerError("invalid_prep", "prep status requires a result")
    refuse_trait_lab_local_env_prep_live(result)
    if result.get("ok") is True or result.get("prepared") is True:
        return "ready"
    if result.get("status") == "dry_run":
        return "dry_run"
    if result.get("ok") is False:
        return "blocked"
    raise MemoryLayerError("invalid_prep", "prep status is missing")


def _prep_fact_id(prep_sha256: str) -> str:
    return f"{_PREP_FACT_PREFIX}{prep_sha256[:16]}"


def persist_trait_lab_local_env_prep_receipt(
    store: MemoryStore,
    report: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """E19 — write a prep receipt fact. Does not apply packs or runs."""
    require_trait_lab_local_env_provenance(agent_id=agent_id, task_id=task_id)
    verified = verify_trait_lab_local_env_prep_report(report)
    sha = str(verified["prep_sha256"])
    write_verified(
        store,
        {
            "id": _prep_fact_id(sha),
            "fact": f"local env prep {sha} ok={verified['ok']}",
            "how": f"persist_trait_lab_local_env_prep_receipt {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _PREP_RECEIPT_KIND,
            "ok": verified["ok"],
            "count": verified["count"],
        },
    )
    record_task_step(
        store,
        task_id,
        "local-env-prep",
        {"prep_sha256": sha, "ok": verified["ok"]},
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "prep_sha256": sha,
        "fact_id": _prep_fact_id(sha),
        "ok": verified["ok"],
        "live_verified": False,
    }


def _prep_receipt_row(entry: Any) -> dict[str, Any] | None:
    if not str(entry.key).startswith("verified:trait-lab-env-prep-"):
        return None
    if entry.value.get("live_verified") is True:
        return None
    if str(entry.value.get("id") or "") == "trait-lab-env-prep-probe":
        return None
    sha = str(entry.value.get("source") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        return None
    return {
        "kind": _PREP_RECEIPT_KIND,
        "prep_sha256": sha,
        "fact_id": _prep_fact_id(sha),
        "ok": bool(entry.value.get("ok")),
        "count": int(entry.value.get("count") or 0),
        "agent_id": entry.agent_id,
        "task_id": entry.task_id,
        "live_verified": False,
    }


def _collect_prep_receipts(store: MemoryStore, *, scan: int = 200) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in query_layer(store, MemoryLayer.VERIFIED_KNOWLEDGE, prefix="verified:trait-lab-env-prep-", limit=scan):
        row = _prep_receipt_row(entry)
        if row is None or row["prep_sha256"] in seen:
            continue
        seen.add(row["prep_sha256"])
        found.append(row)
    found.sort(key=lambda row: str(row["prep_sha256"]))
    return found


def get_trait_lab_local_env_prep_receipt(store: MemoryStore, prep_sha256: str) -> dict[str, Any]:
    """E20 — select one prep receipt by prep_sha256."""
    sha = str(prep_sha256 or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_prep_hash", "receipt select requires prep_sha256")
    entry = store.get(f"verified:{_prep_fact_id(sha)}")
    if entry is None:
        raise MemoryLayerError("missing_prep", f"no local env prep receipt {sha[:12]}")
    row = _prep_receipt_row(entry)
    if row is None:
        raise MemoryLayerError("invalid_prep", f"local env prep receipt {sha[:12]} is malformed")
    return {**row, "live_verified": False}


def list_trait_lab_local_env_prep_receipts(store: MemoryStore, *, limit: int = 50) -> dict[str, Any]:
    """E21 — index persisted prep receipts."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    rows = _collect_prep_receipts(store)[:limit]
    public = [
        {
            "prep_sha256": row["prep_sha256"],
            "fact_id": row["fact_id"],
            "kind": _PREP_RECEIPT_KIND,
            "ok": row["ok"],
            "count": row["count"],
            "live_verified": False,
        }
        for row in rows
    ]
    return {
        "kind": _PREP_RECEIPT_KIND,
        "receipts": public,
        "count": len(rows),
        "live_verified": False,
    }


def has_trait_lab_local_env_prep_receipt(store: MemoryStore, prep_sha256: str) -> bool:
    """E22 — true when a prep receipt exists."""
    sha = str(prep_sha256 or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_prep_hash", "has_receipt requires prep_sha256")
    return any(row["prep_sha256"] == sha for row in _collect_prep_receipts(store))


def list_trait_lab_local_env_prep_receipts_by_agent(
    store: MemoryStore,
    agent_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """E23 — receipts written by one agent."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise MemoryLayerError("invalid_limit", "limit must be >= 1")
    wanted = str(agent_id or "").strip()
    if not wanted:
        raise MemoryLayerError("missing_agent", "prep receipt by agent requires agent_id")
    rows = [row for row in _collect_prep_receipts(store) if row.get("agent_id") == wanted]
    if not rows:
        raise MemoryLayerError("missing_agent", f"no local env prep receipt for agent {wanted}")
    return {
        "kind": _PREP_RECEIPT_KIND,
        "receipts": [
            {
                "prep_sha256": row["prep_sha256"],
                "fact_id": row["fact_id"],
                "kind": _PREP_RECEIPT_KIND,
                "ok": row["ok"],
                "count": row["count"],
                "live_verified": False,
            }
            for row in rows[:limit]
        ],
        "count": len(rows),
        "agent_id": wanted,
        "live_verified": False,
    }


def prepare_and_dry_run_trait_lab_local_env(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """E24 — prepare a workspace, run checks, dry-run rematch, persist receipt."""
    require_trait_lab_local_env_provenance(agent_id=agent_id, task_id=task_id)
    workspace = prepare_trait_lab_local_env_workspace()
    store = MemoryStore(workspace["store_path"])
    try:
        report = export_trait_lab_local_env_prep_report(
            agent_id=agent_id,
            task_id=task_id,
            environ=environ,
            store_path=workspace["store_path"],
        )
        dry = dry_run_trait_lab_local_env_workflow(store, agent_id=agent_id, task_id=task_id)
        receipt = persist_trait_lab_local_env_prep_receipt(
            store, report, agent_id=agent_id, task_id=task_id
        )
    finally:
        store.close()
    return {
        "kind": _PREP_KIND,
        "workspace": workspace,
        "report": report,
        "dry_run": dry,
        "receipt": receipt,
        "status": "ready",
        "ok": bool(report["ok"]) and dry["status"] == "dry_run",
        "live_verified": False,
    }
