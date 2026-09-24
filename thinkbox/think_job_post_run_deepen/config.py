"""Fail-closed config (PR #184 F04)."""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Mapping
from thinkbox.think_job_post_run_deepen.errors import ThinkJobPostRunDeepenError

@dataclass(frozen=True)
class PostRunDeepenConfig:
    dry_run: bool
    max_payload_bytes: int

def load_config_from_env(environ: Mapping[str, str] | None = None) -> PostRunDeepenConfig:
    env = dict(os.environ if environ is None else environ)
    dry = (env.get("THINK_JOB_POST_RUN_DEEPEN_DRY_RUN") or "true").lower()
    if dry not in ("true", "1", "yes"):
        raise ThinkJobPostRunDeepenError("dry_run_required", "dry_run=true required")
    max_b = int(env.get("THINK_JOB_POST_RUN_DEEPEN_MAX_PAYLOAD") or "65536")
    return PostRunDeepenConfig(dry_run=True, max_payload_bytes=max_b)
