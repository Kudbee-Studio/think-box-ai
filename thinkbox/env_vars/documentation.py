"""Sync documentation keys with .env.example (PR #200)."""

from __future__ import annotations

import re
from pathlib import Path

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

_ENV_LINE = re.compile(r"^([A-Z][A-Z0-9_]+)=", re.MULTILINE)


def documented_keys(repo_root: Path | None = None) -> frozenset[str]:
    root = repo_root if repo_root is not None else REPO_ROOT
    example = root / ".env.example"
    if not example.is_file():
        return frozenset()
    text = example.read_text(encoding="utf-8")
    return frozenset(_ENV_LINE.findall(text))


def schema_keys_union() -> frozenset[str]:
    from thinkbox.env_vars.cloud_execution_keys import CLOUD_EXECUTION_FIELDS
    from thinkbox.env_vars.governance_keys import GOVERNANCE_FIELDS
    from thinkbox.env_vars.provider_keys import PROVIDER_FIELDS
    from thinkbox.env_vars.substrate_keys import SUBSTRATE_FIELDS
    from thinkbox.env_vars.think_job_keys import THINK_JOB_FIELDS

    keys: set[str] = set()
    for group in (
        SUBSTRATE_FIELDS,
        GOVERNANCE_FIELDS,
        CLOUD_EXECUTION_FIELDS,
        PROVIDER_FIELDS,
        THINK_JOB_FIELDS,
    ):
        for field in group:
            keys.add(field.key)
    return frozenset(keys)
