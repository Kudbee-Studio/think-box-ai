"""Staging / live-drill configuration validation (no secret export)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

STAGING_FLAG_ENV = "THINKBOX_PIPELINE_STAGING"
LIVE_DRILL_FLAG_ENV = "THINKBOX_LIVE_DRILL_ENABLED"
STAGING_DB_ENV = "THINKBOX_ORG_MEMORY_DB"
STAGING_ID_ENV = "THINKBOX_STAGING_ENVIRONMENT_ID"

_REQUIRED_FOR_LIVE_DRILL: tuple[tuple[str, bool], ...] = (
    (STAGING_FLAG_ENV, True),
    (LIVE_DRILL_FLAG_ENV, True),
    ("WEBHOOK_SECRET", False),
    ("GITHUB_WEBHOOK_SECRET", False),
    ("THINKBOX_FOUNDER_MERGE_PROOF_KEY", True),
    ("THINKBOX_GITHUB_WEBHOOK_GOVERNANCE_TOKEN", True),
    ("THINKBOX_GOVERNANCE_SIGNING_KEY", True),
    (STAGING_DB_ENV, True),
)


def _env_present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def webhook_secret_configured() -> bool:
    return _env_present("WEBHOOK_SECRET") or _env_present("GITHUB_WEBHOOK_SECRET")


def resolve_org_memory_db_path() -> str:
    return os.environ.get(
        STAGING_DB_ENV,
        os.path.join("data", "thinkboxmd", "db", "org_memory_receipts.db"),
    )


def staging_db_isolation_ok(db_path: str) -> tuple[bool, str]:
    """Fail-closed unless staging flag set and path is not the default dev db."""
    if os.environ.get(STAGING_FLAG_ENV, "").lower() not in ("1", "true", "yes"):
        return False, "THINKBOX_PIPELINE_STAGING not enabled"
    normalized = str(Path(db_path).as_posix())
    if normalized.endswith("org_memory_receipts.db") and "staging" not in normalized.lower():
        return False, "staging_db_path_must_contain_staging_segment"
    forbidden = ("production", "prod/", "/main/")
    for token in forbidden:
        if token in normalized.lower():
            return False, f"forbidden_path_token:{token}"
    return True, "ok"


def inspect_staging_config() -> dict[str, Any]:
    """Non-secret staging readiness report."""
    db_path = resolve_org_memory_db_path()
    iso_ok, iso_reason = staging_db_isolation_ok(db_path)
    checks: dict[str, Any] = {
        "staging_flag": _env_present(STAGING_FLAG_ENV),
        "live_drill_flag": _env_present(LIVE_DRILL_FLAG_ENV),
        "webhook_secret": webhook_secret_configured(),
        "founder_proof_key": _env_present("THINKBOX_FOUNDER_MERGE_PROOF_KEY"),
        "webhook_governance_token": _env_present("THINKBOX_GITHUB_WEBHOOK_GOVERNANCE_TOKEN"),
        "governance_signing_key": _env_present("THINKBOX_GOVERNANCE_SIGNING_KEY"),
        "org_memory_db_configured": _env_present(STAGING_DB_ENV),
        "staging_db_isolation_ok": iso_ok,
        "staging_db_isolation_reason": iso_reason,
        "staging_environment_id": os.environ.get(STAGING_ID_ENV, ""),
        "org_memory_db_path_hint": Path(db_path).name,
    }
    missing: list[str] = []
    if not checks["staging_flag"]:
        missing.append(STAGING_FLAG_ENV)
    if not checks["live_drill_flag"]:
        missing.append(LIVE_DRILL_FLAG_ENV)
    if not checks["webhook_secret"]:
        missing.append("WEBHOOK_SECRET|GITHUB_WEBHOOK_SECRET")
    if not checks["founder_proof_key"]:
        missing.append("THINKBOX_FOUNDER_MERGE_PROOF_KEY")
    if not checks["webhook_governance_token"]:
        missing.append("THINKBOX_GITHUB_WEBHOOK_GOVERNANCE_TOKEN")
    if not checks["governance_signing_key"]:
        missing.append("THINKBOX_GOVERNANCE_SIGNING_KEY")
    if not checks["org_memory_db_configured"]:
        missing.append(STAGING_DB_ENV)
    if not iso_ok:
        missing.append("staging_db_isolation")
    ready = len(missing) == 0
    return {
        "ready_for_live_drill": ready,
        "missing_prerequisites": missing,
        "checks": checks,
        "evidence_label": "simulated",
        "auto_merge": False,
        "github_merge": False,
    }
