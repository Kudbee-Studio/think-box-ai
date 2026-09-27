"""Test fixtures for env pack (PR #200)."""

from __future__ import annotations

from thinkbox.env_vars.ci_matrix import minimal_hermetic_environ


def malformed_int_environ() -> dict[str, str]:
    base = minimal_hermetic_environ()
    base["THINKBOX_CLOUD_EXEC_MAX_ACTIVE_JOBS"] = "not-an-int"
    return base


def missing_optional_ok_environ() -> dict[str, str]:
    return minimal_hermetic_environ()


def valid_cloud_worker_environ() -> dict[str, str]:
    base = minimal_hermetic_environ()
    base.update(
        {
            "THINKBOX_CLOUD_EXEC_WORKER_ID": "worker-hermetic-001",
            "THINKBOX_CLOUD_EXEC_MAX_ACTIVE_JOBS": "2",
        }
    )
    return base
