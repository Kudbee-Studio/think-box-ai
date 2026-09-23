"""Hermetic KILO environment contract matrix (PR #142, gate ``env-matrix``).

Defines required env vars, modes, feature flags, and mock-endpoint shapes for the
#141–#150 Live-proof readiness arc. Fail-closed on forbidden live defaults;
does not execute Mercury, GPU, or deploy side effects.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, MutableMapping, Sequence
from urllib.parse import urlparse

from thinkbox.kilo_live_proof_readiness import gate_for_pr

GATE_ID = "env-matrix"
PR_NUMBER = 142

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_TRUTHY = frozenset({"1", "true", "yes", "on", "ack", "ACK"})


class EnvMatrixMode(str, Enum):
    """Evaluation modes for the KILO env matrix."""

    HERMETIC_UNIT = "hermetic_unit"
    HERMETIC_CI = "hermetic_ci"
    LIVE_PROOF_PREP = "live_proof_prep"


class EnvCategory(str, Enum):
    """Contract grouping for operator reports."""

    SUBSTRATE = "substrate"
    GOVERNANCE = "governance"
    PROVIDER = "provider"
    FEATURE_FLAG = "feature_flag"
    MOCK_ENDPOINT = "mock_endpoint"
    SPINE = "spine"


@dataclass(frozen=True)
class EnvVarContract:
    """One env var (or prefix) in the KILO readiness matrix."""

    key: str
    category: EnvCategory
    description: str
    required_in: frozenset[EnvMatrixMode] = frozenset()
    forbidden_in: frozenset[EnvMatrixMode] = frozenset()
    value_pattern: re.Pattern[str] | None = None
    sensitive: bool = True
    is_prefix: bool = False


@dataclass(frozen=True)
class MatrixViolation:
    """Single fail-closed violation."""

    code: str
    message: str
    env_key: str | None = None


@dataclass
class EnvMatrixResult:
    """Outcome of evaluating the matrix for one mode."""

    mode: EnvMatrixMode
    ok: bool
    violations: list[MatrixViolation] = field(default_factory=list)
    entries: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "ok": self.ok,
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


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in _TRUTHY or value.strip() == "ACK"


def _matching_keys(environ: Mapping[str, str], contract: EnvVarContract) -> list[str]:
    if contract.is_prefix:
        return sorted(k for k in environ if k.startswith(contract.key))
    if contract.key in environ:
        return [contract.key]
    return []


def _is_loopback_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host in _LOOPBACK_HOSTS:
        return True
    if host.endswith(".localhost"):
        return True
    return False


def _mock_endpoint_ok(value: str) -> bool:
    lowered = value.lower()
    if lowered in {"mock", "hermetic", "dry-run", "disabled"}:
        return True
    if value.startswith("mock://"):
        return True
    if value.startswith("http://") or value.startswith("https://"):
        return _is_loopback_url(value)
    return True


KILO_ENV_CONTRACTS: tuple[EnvVarContract, ...] = (
    EnvVarContract(
        key="THINKBOX_KILO_HERMETIC_MODE",
        category=EnvCategory.FEATURE_FLAG,
        description="When truthy, enforce loopback-only provider URLs in hermetic paths.",
        required_in=frozenset({EnvMatrixMode.HERMETIC_CI}),
        sensitive=False,
    ),
    EnvVarContract(
        key="CI",
        category=EnvCategory.SPINE,
        description="CI runner marker; pairs with hermetic_ci mode detection.",
        forbidden_in=frozenset(),
        sensitive=False,
    ),
    EnvVarContract(
        key="THINKBOX_SWARM_LIVE_ACK",
        category=EnvCategory.GOVERNANCE,
        description="Founder live-swarm ack; forbidden in hermetic_unit/ci.",
        forbidden_in=frozenset({EnvMatrixMode.HERMETIC_UNIT, EnvMatrixMode.HERMETIC_CI}),
    ),
    EnvVarContract(
        key="THINKBOX_KILO_CLAIM_LIVE",
        category=EnvCategory.FEATURE_FLAG,
        description="Must never affirm KILO LIVE VERIFIED via env.",
        forbidden_in=frozenset(
            {EnvMatrixMode.HERMETIC_UNIT, EnvMatrixMode.HERMETIC_CI, EnvMatrixMode.LIVE_PROOF_PREP}
        ),
    ),
    EnvVarContract(
        key="THINKBOX_KILO_PRODUCTION_READY",
        category=EnvCategory.FEATURE_FLAG,
        description="Must never affirm KILO PRODUCTION READY via env.",
        forbidden_in=frozenset(
            {EnvMatrixMode.HERMETIC_UNIT, EnvMatrixMode.HERMETIC_CI, EnvMatrixMode.LIVE_PROOF_PREP}
        ),
    ),
    EnvVarContract(
        key="UPSTASH_PUBLIC_BOX_URL",
        category=EnvCategory.SUBSTRATE,
        description="Upstash Box public URL for execution substrate.",
        required_in=frozenset({EnvMatrixMode.LIVE_PROOF_PREP}),
        value_pattern=re.compile(r"^https://", re.IGNORECASE),
    ),
    EnvVarContract(
        key="UPSTASH_PUBLIC_BOX_TOKEN",
        category=EnvCategory.SUBSTRATE,
        description="Bearer token for Box substrate.",
        required_in=frozenset({EnvMatrixMode.LIVE_PROOF_PREP}),
    ),
    EnvVarContract(
        key="THINKBOX_UPCLOUD_API_TOKEN",
        category=EnvCategory.SUBSTRATE,
        description="UpCloud control-plane token (read-only inventory).",
        required_in=frozenset(),
    ),
    EnvVarContract(
        key="INCEPTION_API_KEY",
        category=EnvCategory.PROVIDER,
        description="Mercury/Inception provider key; forbidden in hermetic_unit.",
        forbidden_in=frozenset({EnvMatrixMode.HERMETIC_UNIT, EnvMatrixMode.HERMETIC_CI}),
    ),
    EnvVarContract(
        key="OPENAI_API_KEY",
        category=EnvCategory.PROVIDER,
        description="OpenAI-compatible provider key; forbidden in hermetic_unit/ci.",
        forbidden_in=frozenset({EnvMatrixMode.HERMETIC_UNIT, EnvMatrixMode.HERMETIC_CI}),
    ),
    EnvVarContract(
        key="THINKBOX_MERCURY_BASE_URL",
        category=EnvCategory.MOCK_ENDPOINT,
        description="Mercury base URL; loopback or mock in hermetic modes.",
        value_pattern=re.compile(r"^https?://", re.IGNORECASE),
        sensitive=False,
    ),
    EnvVarContract(
        key="THINKBOX_PROVIDER_BASE_URL",
        category=EnvCategory.MOCK_ENDPOINT,
        description="Generic provider base URL; loopback or mock in hermetic modes.",
        value_pattern=re.compile(r"^https?://", re.IGNORECASE),
        sensitive=False,
    ),
    EnvVarContract(
        key="THINKBOX_LEDGER_PATH",
        category=EnvCategory.SPINE,
        description="Optional ledger SQLite path override.",
        sensitive=False,
    ),
    EnvVarContract(
        key="THINKBOX_PROOF_DIR",
        category=EnvCategory.SPINE,
        description="Optional proof artifact directory override.",
        sensitive=False,
    ),
    EnvVarContract(
        key="WEBHOOK_SECRET",
        category=EnvCategory.GOVERNANCE,
        description="GitHub webhook HMAC secret for control-plane admissions.",
        required_in=frozenset(),
    ),
    EnvVarContract(
        key="THINKBOX_",
        category=EnvCategory.SPINE,
        description="Thinkbox-prefixed configuration (presence rollup).",
        is_prefix=True,
        sensitive=False,
    ),
)




def detect_matrix_mode(environ: Mapping[str, str] | None = None) -> EnvMatrixMode:
    """Infer matrix mode from environment (explicit override wins)."""
    env = environ if environ is not None else os.environ
    explicit = _env_get(env, "THINKBOX_KILO_MATRIX_MODE")
    if explicit:
        try:
            return EnvMatrixMode(explicit.strip().lower())
        except ValueError:
            pass
    if _env_get(env, "THINKBOX_KILO_LIVE_PROOF_PREP") and _is_truthy(
        _env_get(env, "THINKBOX_KILO_LIVE_PROOF_PREP") or ""
    ):
        return EnvMatrixMode.LIVE_PROOF_PREP
    if _env_get(env, "CI") or _env_get(env, "GITHUB_ACTIONS"):
        return EnvMatrixMode.HERMETIC_CI
    return EnvMatrixMode.HERMETIC_UNIT


def contract_by_key(key: str) -> EnvVarContract | None:
    """Lookup a non-prefix contract by exact key."""
    for contract in KILO_ENV_CONTRACTS:
        if not contract.is_prefix and contract.key == key:
            return contract
    return None


def list_contracts(category: EnvCategory | None = None) -> list[EnvVarContract]:
    """Return contracts, optionally filtered by category."""
    items = [c for c in KILO_ENV_CONTRACTS if not c.is_prefix]
    if category is None:
        return items
    return [c for c in items if c.category == category]


def _entry_status(
    contract: EnvVarContract,
    environ: Mapping[str, str],
    mode: EnvMatrixMode,
) -> dict[str, Any]:
    keys = _matching_keys(environ, contract)
    present = bool(keys)
    values = [_env_get(environ, k) for k in keys]
    non_empty = [v for v in values if v]
    status = "absent"
    if present and non_empty:
        status = "present"
    elif present:
        status = "empty"
    required = mode in contract.required_in
    forbidden = mode in contract.forbidden_in
    return {
        "key": contract.key,
        "category": contract.category.value,
        "status": status,
        "required_in_mode": required,
        "forbidden_in_mode": forbidden,
        "description": contract.description,
    }


def _check_forbidden_public_bind(environ: Mapping[str, str]) -> list[MatrixViolation]:
    violations: list[MatrixViolation] = []
    for key, value in environ.items():
        if not value:
            continue
        upper_key = key.upper()
        if "BIND" not in upper_key and "HOST" not in upper_key and "URL" not in upper_key:
            continue
        if _mock_endpoint_ok(value) and _is_loopback_url(value):
            continue
        if value.startswith("mock://"):
            continue
        if "0.0.0.0" in value:
            violations.append(
                MatrixViolation(
                    code="forbidden_public_bind",
                    message=f"{key} must not bind 0.0.0.0 in hermetic KILO paths",
                    env_key=key,
                )
            )
            continue
        if re.search(r":8000\b|:8001\b", value) and not _is_loopback_url(value):
            violations.append(
                MatrixViolation(
                    code="forbidden_public_bind",
                    message=f"{key} must not expose :8000/:8001 publicly in hermetic KILO paths",
                    env_key=key,
                )
            )
    return violations


def _check_contract_violations(
    contract: EnvVarContract,
    environ: Mapping[str, str],
    mode: EnvMatrixMode,
) -> list[MatrixViolation]:
    violations: list[MatrixViolation] = []
    keys = _matching_keys(environ, contract)
    if mode in contract.required_in:
        if not keys or not any(_env_get(environ, k) for k in keys):
            violations.append(
                MatrixViolation(
                    code="required_missing",
                    message=f"{contract.key} required for mode {mode.value}",
                    env_key=contract.key,
                )
            )
    if mode in contract.forbidden_in:
        for key in keys:
            value = _env_get(environ, key)
            if value is None:
                continue
            if contract.key == "THINKBOX_SWARM_LIVE_ACK" and not _is_truthy(value):
                continue
            violations.append(
                MatrixViolation(
                    code="forbidden_present",
                    message=f"{key} forbidden in mode {mode.value}",
                    env_key=key,
                )
            )
    for key in keys:
        value = _env_get(environ, key)
        if not value or contract.value_pattern is None:
            continue
        if contract.category == EnvCategory.MOCK_ENDPOINT and _mock_endpoint_ok(value):
            continue
        if not contract.value_pattern.search(value):
            violations.append(
                MatrixViolation(
                    code="shape_mismatch",
                    message=f"{key} value does not match required shape",
                    env_key=key,
                )
            )
    if contract.category == EnvCategory.MOCK_ENDPOINT and mode in (
        EnvMatrixMode.HERMETIC_UNIT,
        EnvMatrixMode.HERMETIC_CI,
    ):
        for key in keys:
            value = _env_get(environ, key)
            if value and not _mock_endpoint_ok(value):
                violations.append(
                    MatrixViolation(
                        code="non_loopback_endpoint",
                        message=f"{key} must be loopback or mock in hermetic mode",
                        env_key=key,
                    )
                )
    if (
        _is_truthy(_env_get(environ, "THINKBOX_KILO_HERMETIC_MODE") or "")
        and contract.category == EnvCategory.MOCK_ENDPOINT
    ):
        for key in keys:
            value = _env_get(environ, key)
            if value and not _mock_endpoint_ok(value):
                violations.append(
                    MatrixViolation(
                        code="hermetic_mode_endpoint",
                        message=f"{key} must be loopback while THINKBOX_KILO_HERMETIC_MODE is set",
                        env_key=key,
                    )
                )
    return violations


def evaluate_env_matrix(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> EnvMatrixResult:
    """Evaluate all contracts for *mode*; fail-closed on violations."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved_mode = mode if mode is not None else detect_matrix_mode(env)
    violations: list[MatrixViolation] = []
    entries: list[dict[str, Any]] = []
    for contract in KILO_ENV_CONTRACTS:
        if contract.is_prefix:
            continue
        entries.append(_entry_status(contract, env, resolved_mode))
        violations.extend(_check_contract_violations(contract, env, resolved_mode))
    if resolved_mode in (EnvMatrixMode.HERMETIC_UNIT, EnvMatrixMode.HERMETIC_CI):
        violations.extend(_check_forbidden_public_bind(env))
    ok = len(violations) == 0
    return EnvMatrixResult(mode=resolved_mode, ok=ok, violations=violations, entries=entries)


_OPERATOR_FORBIDDEN_EXACT: tuple[str, ...] = (
    "THINKBOX_SWARM_LIVE_ACK",
    "THINKBOX_KILO_CLAIM_LIVE",
    "THINKBOX_KILO_PRODUCTION_READY",
)


def hermetic_operator_check(environ: Mapping[str, str] | None = None) -> EnvMatrixResult:
    """Spine/CI operator check: forbidden live defaults only (not provider key presence)."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    violations: list[MatrixViolation] = []
    for key in _OPERATOR_FORBIDDEN_EXACT:
        value = _env_get(env, key)
        if value is None:
            continue
        if key == "THINKBOX_SWARM_LIVE_ACK" and not _is_truthy(value):
            continue
        violations.append(
            MatrixViolation(
                code="forbidden_operator",
                message=f"{key} must not be set for hermetic KILO spine paths",
                env_key=key,
            )
        )
    violations.extend(_check_forbidden_public_bind(env))
    if _is_truthy(_env_get(env, "THINKBOX_KILO_HERMETIC_MODE") or ""):
        for contract in KILO_ENV_CONTRACTS:
            if contract.category != EnvCategory.MOCK_ENDPOINT or contract.is_prefix:
                continue
            for key in _matching_keys(env, contract):
                value = _env_get(env, key)
                if value and not _mock_endpoint_ok(value):
                    violations.append(
                        MatrixViolation(
                            code="hermetic_mode_endpoint",
                            message=f"{key} must be loopback while THINKBOX_KILO_HERMETIC_MODE is set",
                            env_key=key,
                        )
                    )
    entries = [
        _entry_status(c, env, mode) for c in KILO_ENV_CONTRACTS if not c.is_prefix
    ]
    return EnvMatrixResult(
        mode=mode,
        ok=len(violations) == 0,
        violations=violations,
        entries=entries,
    )


def env_matrix_gate_closed() -> bool:
    """True when PR #142 ``env-matrix`` gate passes under hermetic_unit defaults."""
    gate = gate_for_pr(PR_NUMBER)
    if gate is None or gate.gate_id != GATE_ID:
        return False
    clean: dict[str, str] = {
        k: v
        for k, v in os.environ.items()
        if k
        in (
            "CI",
            "GITHUB_ACTIONS",
            "THINKBOX_KILO_MATRIX_MODE",
            "THINKBOX_KILO_HERMETIC_MODE",
        )
    }
    return evaluate_env_matrix(EnvMatrixMode.HERMETIC_UNIT, clean).ok


def env_matrix_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Hermetic summary for CLI and spine consumers."""
    env = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    hermetic = hermetic_operator_check(env)
    prep = evaluate_env_matrix(EnvMatrixMode.LIVE_PROOF_PREP, env)
    gate = gate_for_pr(PR_NUMBER)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "detected_mode": mode.value,
        "hermetic_operator_ok": hermetic.ok,
        "live_proof_prep_ok": prep.ok,
        "live_proof_prep_missing": [
            v.env_key for v in prep.violations if v.code == "required_missing"
        ],
        "hermetic_violation_codes": sorted({v.code for v in hermetic.violations}),
        "contract_count": len([c for c in KILO_ENV_CONTRACTS if not c.is_prefix]),
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "arc_gate_theme": gate.theme if gate else None,
    }


def minimal_hermetic_environ(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build a clean hermetic env mapping for unit tests."""
    base: MutableMapping[str, str] = {
        "THINKBOX_KILO_MATRIX_MODE": EnvMatrixMode.HERMETIC_UNIT.value,
    }
    if extra:
        base.update(extra)
    return dict(base)
