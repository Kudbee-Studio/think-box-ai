"""Fail-closed Phase 4 env config (PR #196 F23)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from thinkbox.cli_phase2.redact import redact_mapping
from thinkbox.cli_phase4.errors import profile_error, validation_error


@dataclass(frozen=True)
class CliPhase4Config:
    active_profile: str
    output_format: str
    max_parallel: int
    cassette_dir: str
    sandbox_roots: tuple[str, ...]

    def redacted_summary(self) -> dict[str, str | int | tuple[str, ...]]:
        return redact_mapping(
            {
                "active_profile": self.active_profile,
                "output_format": self.output_format,
                "max_parallel": self.max_parallel,
                "cassette_dir": self.cassette_dir,
                "sandbox_roots": self.sandbox_roots,
            },
        )


def load_phase4_config_from_env(environ: dict[str, str] | None = None) -> CliPhase4Config:
    env = environ if environ is not None else os.environ
    profile = (env.get("THINKBOX_CLI_PROFILE") or "default").strip()
    if not profile or "/" in profile or ".." in profile:
        raise profile_error("THINKBOX_CLI_PROFILE must be a simple name")
    fmt = (env.get("THINKBOX_CLI_OUTPUT_FORMAT") or "json").strip().lower()
    if fmt not in ("json", "table", "yaml"):
        raise validation_error("THINKBOX_CLI_OUTPUT_FORMAT must be json|table|yaml")
    try:
        max_parallel = int(env.get("THINKBOX_CLI_MAX_PARALLEL", "4"))
    except ValueError as exc:
        raise validation_error("THINKBOX_CLI_MAX_PARALLEL must be int") from exc
    if max_parallel < 1 or max_parallel > 16:
        raise validation_error("THINKBOX_CLI_MAX_PARALLEL out of range 1..16")
    cassette = (env.get("THINKBOX_CLI_CASSETTE_DIR") or "data/cli_phase4/cassettes").strip()
    roots_raw = env.get("THINKBOX_CLI_SANDBOX_ROOTS", "data,thinkbox,docs")
    roots = tuple(r.strip() for r in roots_raw.split(",") if r.strip())
    if not roots:
        raise validation_error("THINKBOX_CLI_SANDBOX_ROOTS must list at least one root")
    return CliPhase4Config(
        active_profile=profile,
        output_format=fmt,
        max_parallel=max_parallel,
        cassette_dir=cassette,
        sandbox_roots=roots,
    )
