"""Validate env without full parse (PR #200)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from thinkbox.env_vars.errors import EnvVarsError
from thinkbox.env_vars.parse import parse_schema
from thinkbox.env_vars.schema import EnvField


@dataclass
class ValidationResult:
    ok: bool
    violations: list[EnvVarsError] = field(default_factory=list)
    parsed_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "violation_count": len(self.violations),
            "violation_types": [v.error_type for v in self.violations],
            "parsed_keys": self.parsed_keys,
        }


def validate_fields(fields: tuple[EnvField, ...], environ: Mapping[str, str]) -> ValidationResult:
    violations: list[EnvVarsError] = []
    parsed_keys: list[str] = []
    try:
        parsed = parse_schema(fields, environ)
        parsed_keys = sorted(parsed.keys())
        ok = True
    except EnvVarsError as exc:
        violations.append(exc)
        ok = False
    return ValidationResult(ok=ok, violations=violations, parsed_keys=parsed_keys)
