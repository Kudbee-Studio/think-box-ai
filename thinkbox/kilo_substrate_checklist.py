"""Hermetic Upstash Box URL/token readiness checklist (PR #143, ``substrate-checklist``).

Sits on top of PR #142 ``env-matrix`` — does not duplicate matrix contracts. Fail-closed
for accidental production Box credentials in hermetic modes; shapes for ``live_proof_prep``.
No live Mercury, GPU, or Box HTTP calls.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from thinkbox.kilo_env_matrix import (
    EnvMatrixMode,
    MatrixViolation,
    detect_matrix_mode,
    evaluate_env_matrix,
    hermetic_operator_check,
    minimal_hermetic_environ,
)
from thinkbox.kilo_live_proof_readiness import gate_for_pr

__all__ = (
    "BOX_TOKEN_ENV",
    "BOX_URL_ENV",
    "GATE_ID",
    "PR_NUMBER",
    "SubstrateChecklistMode",
    "SubstrateChecklistResult",
    "SubstrateViolation",
    "evaluate_substrate_checklist",
    "hermetic_substrate_operator_check",
    "minimal_substrate_hermetic_environ",
    "redact_box_token",
    "redact_box_url",
    "substrate_checklist_contract_summary",
    "substrate_checklist_gate_closed",
)

GATE_ID = "substrate-checklist"
PR_NUMBER = 143

BOX_URL_ENV = "UPSTASH_PUBLIC_BOX_URL"
BOX_TOKEN_ENV = "UPSTASH_PUBLIC_BOX_TOKEN"

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_HERMETIC_URL_TOKENS = frozenset({"mock", "hermetic", "dry-run", "disabled"})
_MOCK_URL_PREFIXES = ("mock://", "hermetic://")
_BOX_HOST_SUFFIX = ".box.upstash.com"
_TOKEN_MIN_LIVE_LEN = 8
_TOKEN_LIVE_PATTERN = re.compile(r"^[\w\-./+=]{8,}$")
_PLACEHOLDER_URL = re.compile(
    r"^(https?://)?(example|placeholder|test)\.",
    re.IGNORECASE,
)


class SubstrateChecklistMode(str, Enum):
    """Alias of env-matrix modes for substrate checklist reporting."""

    HERMETIC_UNIT = EnvMatrixMode.HERMETIC_UNIT.value
    HERMETIC_CI = EnvMatrixMode.HERMETIC_CI.value
    LIVE_PROOF_PREP = EnvMatrixMode.LIVE_PROOF_PREP.value


@dataclass(frozen=True)
class SubstrateViolation:
    """Single fail-closed substrate checklist violation."""

    code: str
    message: str
    env_key: str | None = None


@dataclass
class SubstrateChecklistResult:
    """Outcome of evaluating the substrate checklist for one mode."""

    mode: EnvMatrixMode
    ok: bool
    env_matrix_ok: bool
    violations: list[SubstrateViolation] = field(default_factory=list)
    entries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "ok": self.ok,
            "env_matrix_ok": self.env_matrix_ok,
            "violation_count": len(self.violations),
            "violations": [
                {"code": v.code, "message": v.message, "env_key": v.env_key}
                for v in self.violations
            ],
            "entries": self.entries,
            "gate_id": GATE_ID,
            "pr_number": PR_NUMBER,
            "four_state_max": "TEST_VERIFIED",
        }


def _env_get(environ: Mapping[str, str], key: str) -> str | None:
    raw = environ.get(key)
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped if stripped else None


def _mode_from_matrix(mode: EnvMatrixMode | None, environ: Mapping[str, str]) -> EnvMatrixMode:
    if mode is not None:
        return mode
    return detect_matrix_mode(environ)


def _is_loopback_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host in _LOOPBACK_HOSTS:
        return True
    return host.endswith(".localhost")


def is_hermetic_box_url(url: str) -> bool:
    """True when URL is an allowed hermetic/mock Box endpoint shape."""
    lowered = url.strip().lower()
    if lowered in _HERMETIC_URL_TOKENS:
        return True
    if any(lowered.startswith(prefix) for prefix in _MOCK_URL_PREFIXES):
        return True
    if _PLACEHOLDER_URL.search(url):
        return True
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return _is_loopback_url(url)
    return False


def is_live_box_url(url: str) -> bool:
    """True when URL matches Live-proof prep Box host expectations."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme.lower() != "https":
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if _is_loopback_url(url):
        return False
    return host.endswith(_BOX_HOST_SUFFIX) or ".preview.box.upstash.com" in host


def is_hermetic_box_token(token: str) -> bool:
    """True for mock/hermetic token literals allowed in unit/CI paths."""
    lowered = token.strip().lower()
    if lowered in _HERMETIC_URL_TOKENS:
        return True
    if lowered.startswith("mock_") or lowered.startswith("hermetic_"):
        return True
    if lowered in {"token", "test-token", "placeholder"}:
        return True
    return False


def is_live_box_token(token: str) -> bool:
    """Shape check for Live-proof prep (not a live HTTP validation)."""
    if not token or token != token.strip():
        return False
    if "\n" in token or "\r" in token:
        return False
    if len(token) < _TOKEN_MIN_LIVE_LEN:
        return False
    return bool(_TOKEN_LIVE_PATTERN.match(token))


def redact_box_token(token: str | None) -> str:
    """Redact token for JSON summaries — never echo full secrets."""
    if not token:
        return ""
    stripped = token.strip()
    if not stripped:
        return ""
    if is_hermetic_box_token(stripped):
        return stripped
    if len(stripped) <= 4:
        return "***"
    return f"{stripped[:3]}***{stripped[-2:]}"


def redact_box_url(url: str | None) -> str:
    """Redact URL query/userinfo while keeping host for operator reports."""
    if not url:
        return ""
    stripped = url.strip()
    if is_hermetic_box_url(stripped):
        return stripped
    try:
        parsed = urlparse(stripped)
    except ValueError:
        return "***"
    host = parsed.hostname or "***"
    scheme = parsed.scheme or "https"
    return f"{scheme}://{host}/…"


def _entry_status(environ: Mapping[str, str]) -> list[dict[str, Any]]:
    url = _env_get(environ, BOX_URL_ENV)
    token = _env_get(environ, BOX_TOKEN_ENV)
    return [
        {
            "key": BOX_URL_ENV,
            "status": "present" if url else "absent",
            "redacted_value": redact_box_url(url),
        },
        {
            "key": BOX_TOKEN_ENV,
            "status": "present" if token else "absent",
            "redacted_value": redact_box_token(token),
        },
    ]


def _violations_for_hermetic(
    environ: Mapping[str, str],
    mode: EnvMatrixMode,
) -> list[SubstrateViolation]:
    violations: list[SubstrateViolation] = []
    url = _env_get(environ, BOX_URL_ENV)
    token = _env_get(environ, BOX_TOKEN_ENV)
    if not url and not token:
        return violations
    if url and not is_hermetic_box_url(url):
        violations.append(
            SubstrateViolation(
                code="forbidden_live_box_url",
                message=f"{BOX_URL_ENV} must be mock/loopback/placeholder in {mode.value}",
                env_key=BOX_URL_ENV,
            )
        )
    if token and not is_hermetic_box_token(token):
        violations.append(
            SubstrateViolation(
                code="forbidden_live_box_token",
                message=f"{BOX_TOKEN_ENV} must use mock/hermetic literals in {mode.value}",
                env_key=BOX_TOKEN_ENV,
            )
        )
    if url and is_live_box_url(url) and token and is_live_box_token(token):
        violations.append(
            SubstrateViolation(
                code="production_credentials_in_hermetic",
                message="realistic Box URL+token pair forbidden in hermetic modes",
                env_key=BOX_URL_ENV,
            )
        )
    return violations


def _violations_for_live_prep(environ: Mapping[str, str]) -> list[SubstrateViolation]:
    violations: list[SubstrateViolation] = []
    url = _env_get(environ, BOX_URL_ENV)
    token = _env_get(environ, BOX_TOKEN_ENV)
    if not url:
        violations.append(
            SubstrateViolation(
                code="required_missing",
                message=f"{BOX_URL_ENV} required for live_proof_prep substrate checklist",
                env_key=BOX_URL_ENV,
            )
        )
    elif not is_live_box_url(url):
        violations.append(
            SubstrateViolation(
                code="shape_mismatch",
                message=f"{BOX_URL_ENV} must be https Box host (*.box.upstash.com)",
                env_key=BOX_URL_ENV,
            )
        )
    if not token:
        violations.append(
            SubstrateViolation(
                code="required_missing",
                message=f"{BOX_TOKEN_ENV} required for live_proof_prep substrate checklist",
                env_key=BOX_TOKEN_ENV,
            )
        )
    elif not is_live_box_token(token):
        violations.append(
            SubstrateViolation(
                code="shape_mismatch",
                message=f"{BOX_TOKEN_ENV} must meet live-prep token shape (no whitespace)",
                env_key=BOX_TOKEN_ENV,
            )
        )
    return violations


def _matrix_environ_for_check(
    environ: Mapping[str, str],
    mode: EnvMatrixMode,
) -> dict[str, str]:
    """Project env for env-matrix so hermetic Box mocks do not trip https shape rules."""
    projected = dict(environ)
    if mode not in (EnvMatrixMode.HERMETIC_UNIT, EnvMatrixMode.HERMETIC_CI):
        return projected
    url = _env_get(environ, BOX_URL_ENV)
    token = _env_get(environ, BOX_TOKEN_ENV)
    if url and is_hermetic_box_url(url):
        projected.pop(BOX_URL_ENV, None)
    if token and is_hermetic_box_token(token):
        projected.pop(BOX_TOKEN_ENV, None)
    return projected


def _matrix_violations_to_substrate(
    matrix_violations: list[MatrixViolation],
) -> list[SubstrateViolation]:
    return [
        SubstrateViolation(
            code=f"env_matrix_{v.code}",
            message=v.message,
            env_key=v.env_key,
        )
        for v in matrix_violations
    ]


def evaluate_substrate_checklist(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> SubstrateChecklistResult:
    """Evaluate Box URL/token readiness; requires env-matrix pass for same mode."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved_mode = _mode_from_matrix(mode, env)
    matrix_env = _matrix_environ_for_check(env, resolved_mode)
    matrix_result = evaluate_env_matrix(resolved_mode, matrix_env)
    violations: list[SubstrateViolation] = []
    if not matrix_result.ok:
        violations.extend(_matrix_violations_to_substrate(matrix_result.violations))
    if resolved_mode in (EnvMatrixMode.HERMETIC_UNIT, EnvMatrixMode.HERMETIC_CI):
        violations.extend(_violations_for_hermetic(env, resolved_mode))
    elif resolved_mode == EnvMatrixMode.LIVE_PROOF_PREP:
        violations.extend(_violations_for_live_prep(env))
    entries = _entry_status(env)
    ok = len(violations) == 0
    return SubstrateChecklistResult(
        mode=resolved_mode,
        ok=ok,
        env_matrix_ok=matrix_result.ok,
        violations=violations,
        entries=entries,
    )


def hermetic_substrate_operator_check(
    environ: Mapping[str, str] | None = None,
) -> SubstrateChecklistResult:
    """Spine/CI operator check: env-matrix operator pass + no live Box creds."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    matrix_env = _matrix_environ_for_check(env, mode)
    matrix_op = hermetic_operator_check(matrix_env)
    violations: list[SubstrateViolation] = []
    if not matrix_op.ok:
        violations.extend(_matrix_violations_to_substrate(matrix_op.violations))
    violations.extend(_violations_for_hermetic(env, mode))
    entries = _entry_status(env)
    return SubstrateChecklistResult(
        mode=mode,
        ok=len(violations) == 0,
        env_matrix_ok=matrix_op.ok,
        violations=violations,
        entries=entries,
    )


def substrate_checklist_gate_closed() -> bool:
    """True when PR #143 gate passes under hermetic_unit with clean env."""
    gate = gate_for_pr(PR_NUMBER)
    if gate is None or gate.gate_id != GATE_ID:
        return False
    env = minimal_substrate_hermetic_environ()
    op = hermetic_substrate_operator_check(env)
    unit = evaluate_substrate_checklist(EnvMatrixMode.HERMETIC_UNIT, env)
    return op.ok and unit.ok


def substrate_checklist_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Hermetic summary for CLI and spine consumers."""
    env = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    operator = hermetic_substrate_operator_check(env)
    prep = evaluate_substrate_checklist(EnvMatrixMode.LIVE_PROOF_PREP, env)
    gate = gate_for_pr(PR_NUMBER)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "detected_mode": mode.value,
        "env_matrix_layer": True,
        "hermetic_operator_ok": operator.ok,
        "hermetic_env_matrix_ok": operator.env_matrix_ok,
        "live_proof_prep_ok": prep.ok,
        "live_proof_prep_missing": [
            v.env_key for v in prep.violations if v.code == "required_missing"
        ],
        "hermetic_violation_codes": sorted({v.code for v in operator.violations}),
        "entries_redacted": operator.entries,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "arc_gate_theme": gate.theme if gate else None,
        "gate_closed_default": substrate_checklist_gate_closed(),
    }


def minimal_substrate_hermetic_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Clean hermetic env for substrate unit tests (includes env-matrix baseline)."""
    base: MutableMapping[str, str] = dict(minimal_hermetic_environ())
    if extra:
        base.update(extra)
    return dict(base)
