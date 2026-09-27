"""Audit-ledger era bridge (#125–#126) (PR #182 F19)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT


def audit_ledger_bridge_summary(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    audit_storage = root / "backend/audit_storage.py"
    return {
        "audit_storage_present": audit_storage.is_file(),
        "era": "audit-ledger-125-126",
        "durable_proof_stub": True,
        "live_api_called": False,
        "live_verified": False,
    }
