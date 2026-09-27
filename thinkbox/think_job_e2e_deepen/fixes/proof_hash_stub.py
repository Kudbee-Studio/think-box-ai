"""FIX13: Deterministic proof hash stub for job artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def proof_hash_stub(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def apply_fix() -> dict[str, Any]:
    digest = proof_hash_stub({"job_id": "demo", "state": "COMPLETE", "dry_run": True})
    return {"fix_id": "FIX13", "proof_sha256": digest, "live_api_called": False}
