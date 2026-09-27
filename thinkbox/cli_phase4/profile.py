"""Profile / context switching with fail-closed env (PR #196 F03)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from thinkbox.cli_phase4.errors import profile_error


@dataclass(frozen=True)
class CliProfile:
    name: str
    dry_run: bool
    output_format: str


def list_profiles(environ: dict[str, str] | None = None) -> tuple[str, ...]:
    env = environ if environ is not None else os.environ
    raw = env.get("THINKBOX_CLI_PROFILES", "default,inspect,ci")
    return tuple(sorted({p.strip() for p in raw.split(",") if p.strip()}))


def resolve_active_profile(environ: dict[str, str] | None = None) -> CliProfile:
    env = environ if environ is not None else os.environ
    name = (env.get("THINKBOX_CLI_PROFILE") or "default").strip()
    known = list_profiles(env)
    if name not in known:
        raise profile_error(
            "unknown profile",
            profile=name,
            known=known,
        )
    dry = env.get(f"THINKBOX_CLI_PROFILE_{name.upper()}_DRY_RUN", "").lower() in (
        "1",
        "true",
        "yes",
    )
    fmt = env.get(f"THINKBOX_CLI_PROFILE_{name.upper()}_FORMAT", "json").lower()
    return CliProfile(name=name, dry_run=dry, output_format=fmt)
