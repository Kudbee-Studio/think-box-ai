"""Box commands for Think Box CLI."""

from __future__ import annotations

import os
from pathlib import Path

from ..ui.colors import bold, dim
from ..utils.output import is_json_mode, output_json

JOBS_DIR = Path(__file__).resolve().parent.parent.parent / "jobs"


def box_status() -> None:
    """Show Upstash box status."""
    box_id = os.environ.get("UPSTASH_BOX_ID", "wanted-tuna-71803")
    api_key = os.environ.get("UPSTASH_BOX_API_KEY", "")

    if not api_key:
        print("UPSTASH_BOX_API_KEY not set.")
        return

    if is_json_mode():
        output_json({"box_id": box_id, "api_key_set": bool(api_key)})
        return

    print(bold(f"Box ID: {box_id}"))
    print("Use Upstash API for live status.")


def box_health() -> None:
    """Check backend health on the box."""
    import urllib.request

    box_id = os.environ.get("UPSTASH_BOX_ID", "wanted-tuna-71803")
    url = f"https://{box_id}-8000.preview.box.upstash.com/health"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"Status: {resp.status}")
            print(resp.read().decode())
    except Exception as e:
        print(f"Health check failed: {e}")
