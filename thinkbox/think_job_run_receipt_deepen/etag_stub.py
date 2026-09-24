"""ETag stub for receipt GET (PR #186 F18)."""
from __future__ import annotations

def weak_etag(body: bytes) -> str:
    return f'W/"{len(body)}"'
