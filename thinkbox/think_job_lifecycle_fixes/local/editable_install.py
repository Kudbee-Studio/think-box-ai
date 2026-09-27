"""Check that thinkbox is importable after local bootstrap."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_lifecycle_fixes.local.bootstrap import ensure_repo_on_path


def editable_install_ok() -> dict[str, Any]:
    ensure_repo_on_path()
    try:
        import thinkbox  # noqa: F401
        ok = True
        err = None
    except ImportError as exc:
        ok = False
        err = str(exc)
    return {
        "step": "editable_install",
        "ok": ok,
        "error": err,
        "live_api_called": False,
    }
