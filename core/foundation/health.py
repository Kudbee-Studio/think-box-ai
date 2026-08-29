"""Health check aggregation for all KUDBEE subsystems."""

from __future__ import annotations
import os
import time
import shutil
from typing import Any, List
from core.foundation.error_codes import ErrorCode, format_error_response


def check_disk_space(path: str = ".", threshold_mb: int = 100) -> dict[str, Any]:
    """Check available disk space."""
    try:
        usage = shutil.disk_usage(path)
        free_mb = usage.free / (1024 * 1024)
        return {
            "check": "disk_space",
            "status": "ok" if free_mb > threshold_mb else "warning",
            "free_mb": round(free_mb, 2),
            "threshold_mb": threshold_mb,
        }
    except Exception as e:
        return {"check": "disk_space", "status": "error", "error": str(e)}


def check_execution() -> dict[str, Any]:
    """Check if execution subsystem is functional."""
    try:
        from core.tools import shell_exec
        import asyncio
        result = asyncio.run(shell_exec({"command": "echo health_check"}))
        return {
            "check": "execution",
            "status": "ok" if result.get("success") else "error",
            "provider": "local",
        }
    except Exception as e:
        return {"check": "execution", "status": "error", "error": str(e)}


def check_database(db_path: str | None = None) -> dict[str, Any]:
    """Check database connectivity and integrity."""
    if not db_path or not os.path.exists(db_path):
        return {"check": "database", "status": "skipped", "reason": "no_db_path"}
    
    try:
        import sqlite3
        conn = sqlite3.connect(db_path, timeout=5)
        conn.execute("SELECT 1")
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        conn.close()
        return {
            "check": "database",
            "status": "ok",
            "foreign_keys_enabled": bool(fk),
        }
    except Exception as e:
        return {"check": "database", "status": "error", "error": str(e)}


def check_provider(name: str, base_url: str | None = None) -> dict[str, Any]:
    """Check model provider health."""
    try:
        if name == "openai_compat" and base_url:
            import urllib.request
            req = urllib.request.Request(
                f"{base_url.rsplit('/chat/completions', 0)[0]}/models",
                headers={"Authorization": "Bearer healthcheck"},
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return {"check": f"provider:{name}", "status": "ok"}
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    return {"check": f"provider:{name}", "status": "ok"}
                return {"check": f"provider:{name}", "status": "error", "error": str(e)}
        return {"check": f"provider:{name}", "status": "skipped"}
    except Exception as e:
        return {"check": f"provider:{name}", "status": "error", "error": str(e)}


def full_health_check(db_path: str | None = None, providers: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Run all health checks and return combined report.
    
    Time Complexity: O(N) where N = number of subsystems checked
    Space Complexity: O(N) for check results
    """
    start = time.monotonic()
    
    checks: list[dict[str, Any]] = [
        check_disk_space(),
        check_execution(),
    ]
    
    if db_path:
        checks.append(check_database(db_path))
    
    if providers:
        for p in providers:
            checks.append(check_provider(p["name"], p.get("base_url")))
    
    all_ok = all(c.get("status") in ("ok", "skipped") for c in checks)
    
    return {
        "status": "ok" if all_ok else "degraded",
        "duration_ms": round((time.monotonic() - start) * 1000, 2),
        "checks": checks,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
    }
