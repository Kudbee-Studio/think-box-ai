"""Hermetic swarm instrumentation readiness gate (PR #147, ``swarm-instrumentation``).

Layers on PR #146 ``mercury-hermetic``. Wraps the ten hermetic instrumentation
checks from ``thinkbox/swarm_instrumentation_checks`` plus an eleventh gate
contract entry (live swarm deferred). No network, no ``INCEPTION_API_KEY``
consumption, ``live_api_called=False``. Gate contract check ``inst-11`` defers optional live swarm.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_governance_evidence import redact_secret_value
from thinkbox.kilo_live_proof_readiness import REPO_ROOT, gate_for_pr
from thinkbox.kilo_mercury_hermetic import (
    MercuryHermeticResult,
    hermetic_mercury_operator_check,
    minimal_mercury_hermetic_environ,
    redact_mercury_summary,
)
from thinkbox.kilo_substrate_checklist import redact_box_token, redact_box_url
from thinkbox.swarm_instrumentation_checks import (
    HERMETIC_INSTRUMENTATION_CHECK_COUNT,
    InstrumentationCheckResult,
    hermetic_instrumentation_catalog,
    run_hermetic_instrumentation_checks,
)

__all__ = (
    "EXPECTED_HERMETIC_PASS_COUNT",
    "EXPECTED_INSTRUMENTATION_CATALOG_SIZE",
    "GATE_ID",
    "PR_NUMBER",
    "SwarmInstrumentationEvidence",
    "SwarmInstrumentationMode",
    "SwarmInstrumentationResult",
    "SwarmInstrumentationViolation",
    "evaluate_swarm_instrumentation",
    "experiments_verify_script_path",
    "gate_contract_check",
    "hermetic_swarm_operator_check",
    "minimal_swarm_instrumentation_environ",
    "redact_swarm_summary",
    "swarm_instrumentation_catalog",
    "swarm_instrumentation_contract_summary",
    "swarm_instrumentation_gate_closed",
)

GATE_ID = "swarm-instrumentation"
PR_NUMBER = 147

EXPECTED_HERMETIC_PASS_COUNT = HERMETIC_INSTRUMENTATION_CHECK_COUNT
EXPECTED_INSTRUMENTATION_CATALOG_SIZE = 11

_VERIFY_SCRIPT_REL = Path("experiments/verify_instrumentation.py")
_LIVE_ACK_KEY = "THINKBOX_SWARM_LIVE_ACK"
_PROVIDER_KEYS = ("INCEPTION_API_KEY", "THINKBOX_OPENAI_COMPAT_API_KEY")
_SECRET_ENV_KEYS = frozenset(
    {
        "INCEPTION_API_KEY",
        "THINKBOX_OPENAI_COMPAT_API_KEY",
        "UPSTASH_PUBLIC_BOX_TOKEN",
        "UPSTASH_PUBLIC_BOX_URL",
        "THINKBOX_GOVERNANCE_TOKEN",
        "GOVERNANCE_TOKEN",
    }
)


class SwarmInstrumentationMode(str, Enum):
    """Alias of env-matrix modes for swarm-instrumentation reporting."""

    HERMETIC_UNIT = EnvMatrixMode.HERMETIC_UNIT.value
    HERMETIC_CI = EnvMatrixMode.HERMETIC_CI.value
    LIVE_PROOF_PREP = EnvMatrixMode.LIVE_PROOF_PREP.value


@dataclass(frozen=True)
class SwarmInstrumentationViolation:
    """Single fail-closed swarm-instrumentation violation."""

    code: str
    message: str
    env_key: str | None = None
    check_id: str | None = None


@dataclass(frozen=True)
class SwarmInstrumentationEvidence:
    """Redacted evidence for swarm-instrumentation gate."""

    gate_id: str
    pr_number: int
    mercury_hermetic_ok: bool
    mercury_summary_ref: dict[str, Any]
    instrumentation_results: tuple[InstrumentationCheckResult, ...]
    gate_contract_ok: bool
    passed_count: int
    total_hermetic_checks: int
    catalog_size: int
    verifier_script_present: bool
    live_swarm_invoked: bool
    evidence_label: str
    live_api_called: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "pr_number": self.pr_number,
            "mercury_hermetic_ok": self.mercury_hermetic_ok,
            "mercury_summary_ref": self.mercury_summary_ref,
            "instrumentation_results": [r.to_dict() for r in self.instrumentation_results],
            "gate_contract_ok": self.gate_contract_ok,
            "passed_count": self.passed_count,
            "total_hermetic_checks": self.total_hermetic_checks,
            "catalog_size": self.catalog_size,
            "verifier_script_present": self.verifier_script_present,
            "live_swarm_invoked": self.live_swarm_invoked,
            "evidence_label": self.evidence_label,
            "live_api_called": self.live_api_called,
        }


@dataclass
class SwarmInstrumentationResult:
    """Outcome of evaluating swarm-instrumentation for one mode."""

    mode: EnvMatrixMode
    ok: bool
    mercury_hermetic_ok: bool
    env_matrix_ok: bool
    substrate_checklist_ok: bool
    governance_evidence_ok: bool
    passed_count: int
    total_hermetic_checks: int
    violations: list[SwarmInstrumentationViolation] = field(default_factory=list)
    evidence: SwarmInstrumentationEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "ok": self.ok,
            "mercury_hermetic_ok": self.mercury_hermetic_ok,
            "env_matrix_ok": self.env_matrix_ok,
            "substrate_checklist_ok": self.substrate_checklist_ok,
            "governance_evidence_ok": self.governance_evidence_ok,
            "passed_count": self.passed_count,
            "total_hermetic_checks": self.total_hermetic_checks,
            "violations": [
                {
                    "code": v.code,
                    "message": v.message,
                    "env_key": v.env_key,
                    "check_id": v.check_id,
                }
                for v in self.violations
            ],
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "gate_id": GATE_ID,
            "pr_number": PR_NUMBER,
            "four_state_max": "TEST_VERIFIED",
            "live_api_called": False,
        }


def experiments_verify_script_path() -> Path:
    """Absolute path to ``experiments/verify_instrumentation.py``."""
    return REPO_ROOT / _VERIFY_SCRIPT_REL


def swarm_instrumentation_catalog() -> tuple[dict[str, str], ...]:
    """Eleven-entry catalog: ten hermetic instruments + gate contract (live deferred)."""
    base = list(hermetic_instrumentation_catalog())
    base.append(
        {
            "check_id": "inst-11",
            "name": "11. live swarm deferred (hermetic gate)",
            "hermetic": "true",
            "live_swarm": "false",
        }
    )
    return tuple(base)


def gate_contract_check(
    *,
    live_swarm_invoked: bool = False,
) -> tuple[bool, str]:
    """Eleventh gate check: verifier present, live swarm not invoked in hermetic paths."""
    if live_swarm_invoked:
        return False, "live swarm must not run in hermetic swarm-instrumentation gate"
    path = experiments_verify_script_path()
    if not path.is_file():
        return False, f"missing verifier script: {_VERIFY_SCRIPT_REL}"
    catalog = swarm_instrumentation_catalog()
    if len(catalog) != EXPECTED_INSTRUMENTATION_CATALOG_SIZE:
        return False, f"catalog size {len(catalog)} != {EXPECTED_INSTRUMENTATION_CATALOG_SIZE}"
    return True, "verifier script present; live swarm deferred"


def _mercury_violations_to_swarm(
    mercury: MercuryHermeticResult,
) -> list[SwarmInstrumentationViolation]:
    return [
        SwarmInstrumentationViolation(
            code=f"mercury_{v.code}",
            message=v.message,
            env_key=v.env_key,
        )
        for v in mercury.violations
    ]


def _mercury_summary_ref(mercury: MercuryHermeticResult) -> dict[str, Any]:
    return {
        "mode": mercury.mode.value,
        "ok": mercury.ok,
        "governance_evidence_ok": mercury.governance_evidence_ok,
        "violation_count": len(mercury.violations),
        "gate_id": "mercury-hermetic",
    }


def _run_instrumentation_with_violations(
    violations: list[SwarmInstrumentationViolation],
) -> tuple[list[InstrumentationCheckResult], int]:
    results = run_hermetic_instrumentation_checks()
    passed = sum(1 for r in results if r.ok)
    for result in results:
        if result.ok:
            continue
        violations.append(
            SwarmInstrumentationViolation(
                code="instrumentation_check_failed",
                message=result.detail or result.name,
                check_id=result.check_id,
            )
        )
    if passed != EXPECTED_HERMETIC_PASS_COUNT:
        violations.append(
            SwarmInstrumentationViolation(
                code="instrumentation_pass_count",
                message=(
                    f"expected {EXPECTED_HERMETIC_PASS_COUNT}/{EXPECTED_HERMETIC_PASS_COUNT} "
                    f"hermetic checks, got {passed}/{len(results)}"
                ),
            )
        )
    return results, passed


def evaluate_swarm_instrumentation(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    run_instrumentation: bool = True,
    live_swarm_invoked: bool = False,
) -> SwarmInstrumentationResult:
    """Evaluate swarm-instrumentation gate (fail-closed)."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved_mode = mode if mode is not None else detect_matrix_mode(env)
    violations: list[SwarmInstrumentationViolation] = []

    mercury = hermetic_mercury_operator_check(env)
    if not mercury.ok:
        violations.extend(_mercury_violations_to_swarm(mercury))

    if live_swarm_invoked:
        violations.append(
            SwarmInstrumentationViolation(
                code="live_swarm_forbidden",
                message="live swarm execution is forbidden in hermetic swarm-instrumentation",
            )
        )

    results: tuple[InstrumentationCheckResult, ...] = ()
    passed = 0
    if run_instrumentation:
        result_list, passed = _run_instrumentation_with_violations(violations)
        results = tuple(result_list)

    contract_ok, contract_detail = gate_contract_check(live_swarm_invoked=live_swarm_invoked)
    if not contract_ok:
        violations.append(
            SwarmInstrumentationViolation(
                code="gate_contract_failed",
                message=contract_detail,
                check_id="inst-11",
            )
        )

    evidence = SwarmInstrumentationEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        mercury_hermetic_ok=mercury.ok,
        mercury_summary_ref=_mercury_summary_ref(mercury),
        instrumentation_results=results,
        gate_contract_ok=contract_ok,
        passed_count=passed,
        total_hermetic_checks=EXPECTED_HERMETIC_PASS_COUNT,
        catalog_size=len(swarm_instrumentation_catalog()),
        verifier_script_present=experiments_verify_script_path().is_file(),
        live_swarm_invoked=live_swarm_invoked,
        evidence_label="inferred",
        live_api_called=False,
    )

    ok = mercury.ok and contract_ok and passed == EXPECTED_HERMETIC_PASS_COUNT and not live_swarm_invoked
    if ok:
        violations = []

    return SwarmInstrumentationResult(
        mode=resolved_mode,
        ok=ok,
        mercury_hermetic_ok=mercury.ok,
        env_matrix_ok=mercury.env_matrix_ok,
        substrate_checklist_ok=mercury.substrate_checklist_ok,
        governance_evidence_ok=mercury.governance_evidence_ok,
        passed_count=passed,
        total_hermetic_checks=EXPECTED_HERMETIC_PASS_COUNT,
        violations=violations,
        evidence=evidence,
    )


def _forbidden_live_provider_in_operator(
    env: Mapping[str, str],
) -> list[SwarmInstrumentationViolation]:
    """Fail-closed when production-shaped provider keys appear without mercury mock."""
    from thinkbox.kilo_mercury_hermetic import mock_client_configured

    if mock_client_configured(env):
        return []
    hits: list[SwarmInstrumentationViolation] = []
    for key in _PROVIDER_KEYS:
        raw = (env.get(key) or "").strip()
        if not raw or len(raw) < 12:
            continue
        if raw.startswith("mock_") or raw.startswith("test_"):
            continue
        hits.append(
            SwarmInstrumentationViolation(
                code="forbidden_live_provider_without_mock",
                message=f"{key} present without mercury mock in hermetic operator paths",
                env_key=key,
            )
        )
    return hits


def hermetic_swarm_operator_check(
    environ: Mapping[str, str] | None = None,
) -> SwarmInstrumentationResult:
    """Spine/CI operator check: mercury layer + 10/10 instrumentation + gate contract."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    mercury = hermetic_mercury_operator_check(env)
    violations: list[SwarmInstrumentationViolation] = []
    if not mercury.ok:
        violations.extend(_mercury_violations_to_swarm(mercury))
    violations.extend(_forbidden_live_provider_in_operator(env))

    results, passed = _run_instrumentation_with_violations(violations)
    contract_ok, contract_detail = gate_contract_check(live_swarm_invoked=False)
    if not contract_ok:
        violations.append(
            SwarmInstrumentationViolation(
                code="gate_contract_failed",
                message=contract_detail,
                check_id="inst-11",
            )
        )

    evidence = SwarmInstrumentationEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        mercury_hermetic_ok=mercury.ok,
        mercury_summary_ref=_mercury_summary_ref(mercury),
        instrumentation_results=tuple(results),
        gate_contract_ok=contract_ok,
        passed_count=passed,
        total_hermetic_checks=EXPECTED_HERMETIC_PASS_COUNT,
        catalog_size=len(swarm_instrumentation_catalog()),
        verifier_script_present=experiments_verify_script_path().is_file(),
        live_swarm_invoked=False,
        evidence_label="inferred",
        live_api_called=False,
    )

    ok = (
        mercury.ok
        and contract_ok
        and passed == EXPECTED_HERMETIC_PASS_COUNT
        and len(violations) == 0
    )
    return SwarmInstrumentationResult(
        mode=mode,
        ok=ok,
        mercury_hermetic_ok=mercury.ok,
        env_matrix_ok=mercury.env_matrix_ok,
        substrate_checklist_ok=mercury.substrate_checklist_ok,
        governance_evidence_ok=mercury.governance_evidence_ok,
        passed_count=passed,
        total_hermetic_checks=EXPECTED_HERMETIC_PASS_COUNT,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def swarm_instrumentation_gate_closed() -> bool:
    """True when PR #147 gate passes under hermetic operator + unit evaluation."""
    gate = gate_for_pr(PR_NUMBER)
    if gate is None or gate.gate_id != GATE_ID:
        return False
    env = minimal_swarm_instrumentation_environ()
    op = hermetic_swarm_operator_check(env)
    unit = evaluate_swarm_instrumentation(EnvMatrixMode.HERMETIC_UNIT, env)
    return op.ok and unit.ok


def redact_swarm_summary(text: str) -> str:
    """Scrub secret-like literals from serialized summaries."""
    return redact_mercury_summary(text)


def swarm_instrumentation_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Hermetic summary for CLI and spine consumers (redacted)."""
    env = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    operator = hermetic_swarm_operator_check(env)
    prep_env = dict(env)
    prep_env.setdefault("THINKBOX_KILO_MATRIX_MODE", EnvMatrixMode.LIVE_PROOF_PREP.value)
    prep = evaluate_swarm_instrumentation(
        EnvMatrixMode.LIVE_PROOF_PREP,
        prep_env,
        run_instrumentation=False,
    )
    gate = gate_for_pr(PR_NUMBER)
    catalog = swarm_instrumentation_catalog()
    redacted_env_sample = {
        k: redact_secret_value(k, env.get(k))
        for k in sorted(set(env.keys()) & _SECRET_ENV_KEYS)
    }
    if "UPSTASH_PUBLIC_BOX_URL" in env:
        redacted_env_sample["UPSTASH_PUBLIC_BOX_URL"] = redact_box_url(
            env.get("UPSTASH_PUBLIC_BOX_URL") or ""
        )
    if "UPSTASH_PUBLIC_BOX_TOKEN" in env:
        redacted_env_sample["UPSTASH_PUBLIC_BOX_TOKEN"] = redact_box_token(
            env.get("UPSTASH_PUBLIC_BOX_TOKEN") or ""
        )
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "detected_mode": mode.value,
        "mercury_hermetic_layer": True,
        "env_matrix_layer": True,
        "substrate_checklist_layer": True,
        "governance_evidence_layer": True,
        "hermetic_operator_ok": operator.ok,
        "hermetic_mercury_ok": operator.mercury_hermetic_ok,
        "instrumentation_passed": operator.passed_count,
        "instrumentation_total": operator.total_hermetic_checks,
        "instrumentation_catalog_size": len(catalog),
        "instrumentation_check_ids": [entry["check_id"] for entry in catalog],
        "verifier_script": str(_VERIFY_SCRIPT_REL),
        "verifier_script_present": experiments_verify_script_path().is_file(),
        "live_proof_prep_ok": prep.ok,
        "live_proof_prep_violation_codes": sorted({v.code for v in prep.violations}),
        "hermetic_violation_codes": sorted({v.code for v in operator.violations}),
        "redacted_env_sample": redacted_env_sample,
        "live_api_called": False,
        "live_swarm_invoked": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "arc_gate_theme": gate.theme if gate else None,
        "gate_closed_default": swarm_instrumentation_gate_closed(),
        "eleven_of_eleven_hermetic": (
            operator.passed_count == EXPECTED_HERMETIC_PASS_COUNT
            and len(catalog) == EXPECTED_INSTRUMENTATION_CATALOG_SIZE
        ),
    }


def minimal_swarm_instrumentation_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Clean hermetic env for swarm-instrumentation unit tests."""
    base: MutableMapping[str, str] = dict(minimal_mercury_hermetic_environ())
    if extra:
        base.update(extra)
    return dict(base)
