"""Bound POST /run payload size (hermetic)."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_post_run_deepen.config import load_config_from_env


def payload_within_bounds(byte_len: int) -> dict[str, Any]:
    cfg = load_config_from_env({"THINK_JOB_POST_RUN_DEEPEN_DRY_RUN": "true"})
    return {
        "within_bounds": byte_len <= cfg.max_payload_bytes,
        "max_payload_bytes": cfg.max_payload_bytes,
        "live_api_called": False,
    }
