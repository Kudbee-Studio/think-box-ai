"""Fail-closed env config for Think Job e2e deepen (PR #183 F04)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from thinkbox.think_job_e2e_deepen.errors import ThinkJobE2eDeepenError

__all__ = ("ThinkJobE2eConfig", "load_config_from_env")


@dataclass(frozen=True)
class ThinkJobE2eConfig:
    dry_run: bool
    export_redact: bool
    max_job_steps: int


def load_config_from_env(environ: Mapping[str, str] | None = None) -> ThinkJobE2eConfig:
    env = dict(os.environ if environ is None else environ)
    dry_raw = (env.get("THINK_JOB_E2E_DEEPEN_DRY_RUN") or "true").lower()
    if dry_raw not in ("true", "1", "yes"):
        raise ThinkJobE2eDeepenError("dry_run_required", "hermetic deepen requires dry_run=true")
    max_steps = int(env.get("THINK_JOB_E2E_DEEPEN_MAX_STEPS") or "64")
    if max_steps < 1 or max_steps > 512:
        raise ThinkJobE2eDeepenError("max_steps", "max_steps out of range")
    redact = (env.get("THINK_JOB_E2E_DEEPEN_REDACT") or "true").lower() in ("true", "1", "yes")
    return ThinkJobE2eConfig(dry_run=True, export_redact=redact, max_job_steps=max_steps)
