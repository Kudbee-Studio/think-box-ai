"""HTTP run status catalog (PR #184 F19)."""
from __future__ import annotations

def status_catalog() -> list[dict[str, str]]:
    return [
        {"code": "started", "terminal": "false"},
        {"code": "running", "terminal": "false"},
        {"code": "completed", "terminal": "true"},
        {"code": "failed", "terminal": "true"},
    ]
