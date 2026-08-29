"""Health checks for Think Box runtime."""

from __future__ import annotations

import os
import time
from typing import Any


def check_disk_space(path: str = ".", threshold_mb: int = 100) -> dict[str, Any]:
    """Check available disk space."""
    try:
        stat = os.statvsf(path) if hasattr(os, "statvsf") else None
        if stat is None:
            # Fallback for platforms without statvsf
            import shutil
            usage = shutil.disk_usage(path)
            free_mb = usage.free / (1024 * 1024)
        else:
            free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)

        return {
            "check": "disk_space",
            "status": "ok" if free_mb > threshold_mb else "warning",
            "free_mb": round(free_mb, 2),
            "threshold_mb": threshold_mb,
        }
    except Exception as e:
        return {"check": "disk_space", "status": "error", "error": str(e)}


def check_database(conn_fn) -> dict[str, Any]:
    """Check database connectivity and integrity."""
    try:
        conn = conn_fn()
        conn.execute("SELECT 1")
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        return {
            "check": "database",
            "status": "ok",
            "foreign_keys_enabled": bool(fk),
        }
    except Exception as e:
        return {"check": "database", "status": "error", "error": str(e)}


def check_execution() -> dict[str, Any]:
    """Check if execution subsystem is functional."""
    try:
        import asyncio
        from core.execution import LocalExecProvider
        provider = LocalExecProvider()
        healthy = asyncio.run(provider.health_check())
        return {
            "check": "execution",
            "status": "ok" if healthy else "error",
            "provider": "local",
        }
    except Exception as e:
        return {"check": "execution", "status": "error", "error": str(e)}


def full_health_check(db_path: str | None = None) -> dict[str, Any]:
    """Run all health checks and return combined report."""
    start = time.monotonic()

    checks = [
        check_disk_space(),
        check_execution(),
    ]

    # Add DB check if path provided
    if db_path:
        try:
            import sqlite3
            def conn_fn():
                conn = sqlite3.connect(db_path, timeout=5)
                conn.row_factory = sqlite3.Row
                return conn
            checks.append(check_database(conn_fn))
        except Exception as e:
            checks.append({"check": "database", "status": "error", "error": str(e)})

    all_ok = all(c.get("status") == "ok" for c in checks)

    return {
        "status": "ok" if all_ok else "degraded",
        "duration_ms": round((time.monotonic() - start) * 1000, 2),
        "checks": checks,
    }