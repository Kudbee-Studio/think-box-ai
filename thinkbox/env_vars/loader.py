"""Load and merge env from mapping (PR #200)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from thinkbox.env_vars.parse import parse_schema
from thinkbox.env_vars.schema import EnvField


@dataclass(frozen=True)
class LoadedEnv:
    """Parsed env snapshot (values may be redacted in exports)."""

    profile: str
    parsed: dict[str, object]
    field_count: int


def load_from_mapping(
    fields: tuple[EnvField, ...],
    environ: Mapping[str, str],
    profile: str = "hermetic",
) -> LoadedEnv:
    parsed = parse_schema(fields, environ)
    return LoadedEnv(profile=profile, parsed=parsed, field_count=len(fields))
