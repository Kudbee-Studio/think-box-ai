"""Secret scan helper (PR #186 F23)."""
from __future__ import annotations

def looks_like_secret(text: str) -> bool:
    return "Bearer " in text or "sk-" in text
