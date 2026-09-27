"""Secret scan (PR #184 F23)."""
from __future__ import annotations
import re

def scan_text(text: str) -> list[str]:
    return re.findall(r"sk-[a-zA-Z0-9]{12,}", text)
