"""Hermetic governance admission + live-burst evidence shape (PR #145, ``governance-evidence``).

Layers on PR #142 ``env-matrix`` and PR #143 ``substrate-checklist``. Binds admission
decisions to redacted evidence for a future live burst — no network, no
``INCEPTION_API_KEY`` consumption, ``live_api_called=False`` in hermetic modes.
Aligned with ``thinkbox/cli_live_gate.py`` authorization-only reporting (no HTTP).
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from thinkbox.admission import AdmissionDecision
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.kilo_env_matrix import (
    EnvMatrixMode,
    MatrixViolation,
    detect_matrix_mode,
    evaluate_env_matrix,
)
from thinkbox.kilo_live_proof_readiness import gate_for_pr
from thinkbox.kilo_substrate_checklist import (
    SubstrateViolation,
    evaluate_substrate_checklist,
    hermetic_substrate_operator_check,
    minimal_substrate_hermetic_environ,
    redact_box_token,
    redact_box_url,
)

__all__ = (
    "EVIDENCE_LABEL_INFERRED",
    "EVIDENCE_LABEL_RECORDED",
    "GATE_ID",
    "GovernanceEvidenceMode",
    "GovernanceEvidenceResult",
    "GovernanceViolation",
    "LiveBurstEvidence",
    "PR_NUMBER",
    "build_live_burst_evidence",
    "evaluate_governance_evidence",
    "governance_evidence_contract_summary",
    "governance_evidence_gate_closed",
    "hermetic_governance_operator_check",
    "minimal_governance_hermetic_environ",
    "redact_secret_value",
    "token_fingerprint",
)

GATE_ID = "governance-evidence"
PR_NUMBER = 145

EVIDENCE_LABEL_INFERRED = "inferred"
EVIDENCE_LABEL_RECORDED = "recorded"

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
_TOKEN_MIN_LEN = 12


class GovernanceEvidenceMode(str, Enum):
    """Alias of env-matrix modes for governance evidence reporting."""

    HERMETIC_UNIT = EnvMatrixMode.HERMETIC_UNIT.value
    HERMETIC_CI = EnvMatrixMode.HERMETIC_CI.value
    LIVE_PROOF_PREP = EnvMatrixMode.LIVE_PROOF_PREP.value


@dataclass(frozen=True)
class GovernanceViolation:
    """Single fail-closed governance-evidence violation."""

    code: str
    message: str
    env_key: str | None = None


@dataclass(frozen=True)
class LiveBurstEvidence:
    """Redacted evidence shape for a future KILO live burst (hermetic contract)."""

    agent_id: str
    capability: str
    policy_version: str
    admission_allowed: bool
    admission_reason: str
    token_fingerprint: str | None
    env_matrix_ok: bool
    substrate_checklist_ok: bool
    substrate_summary_ref: dict[str, Any]
    env_matrix_summary_ref: dict[str, Any]
    timestamp: str
    evidence_label: str
    live_api_called: bool
    gate_id: str = GATE_ID
    pr_number: int = PR_NUMBER

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "capability": self.capability,
            "policy_version": self.policy_version,
            "admission_allowed": self.admission_allowed,
            "admission_reason": self.admission_reason,
            "token_fingerprint": self.token_fingerprint,
            "env_matrix_ok": self.env_matrix_ok,
            "substrate_checklist_ok": self.substrate_checklist_ok,
            "substrate_summary_ref": self.substrate_summary_ref,
            "env_matrix_summary_ref": self.env_matrix_summary_ref,
            "timestamp": self.timestamp,
            "evidence_label": self.evidence_label,
            "live_api_called": self.live_api_called,
            "gate_id": self.gate_id,
            "pr_number": self.pr_number,
            "four_state_max": "TEST_VERIFIED",
        }


@dataclass
class GovernanceEvidenceResult:
    """Outcome of evaluating governance evidence for one mode."""

    mode: EnvMatrixMode
    ok: bool
    env_matrix_ok: bool
    substrate_checklist_ok: bool
    violations: list[GovernanceViolation] = field(default_factory=list)
    evidence: LiveBurstEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "ok": self.ok,
            "env_matrix_ok": self.env_matrix_ok,
            "substrate_checklist_ok": self.substrate_checklist_ok,
            "violation_count": len(self.violations),
            "violations": [
                {"code": v.code, "message": v.message, "env_key": v.env_key}
                for v in self.violations
            ],
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "gate_id": GATE_ID,
            "pr_number": PR_NUMBER,
            "four_state_max": "TEST_VERIFIED",
        }


def token_fingerprint(token_value: str | None) -> str | None:
    """Stable short fingerprint for a governance token (never log raw value)."""
    if not token_value or not token_value.strip():
        return None
    digest = hashlib.sha256(token_value.strip().encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"


def redact_secret_value(key: str, value: str | None) -> str:
    """Redact sensitive env values for operator summaries."""
    if value is None or not str(value).strip():
        return "<unset>"
    if key in ("UPSTASH_PUBLIC_BOX_URL",):
        return redact_box_url(value)
    if key in ("UPSTASH_PUBLIC_BOX_TOKEN",):
        return redact_box_token(value)
    if key in _SECRET_ENV_KEYS or "KEY" in key or "TOKEN" in key or "SECRET" in key:
        raw = value.strip()
        if len(raw) <= 4:
            return "<redacted>"
        return f"<redacted:{len(raw)}chars>"
    return value


def _iso_timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _mode_from_matrix(mode: EnvMatrixMode | None, environ: Mapping[str, str]) -> EnvMatrixMode:
    if mode is not None:
        return mode
    return detect_matrix_mode(environ)


def _matrix_violations_to_governance(
    violations: list[MatrixViolation],
) -> list[GovernanceViolation]:
    return [
        GovernanceViolation(
            code=f"env_matrix_{v.code}",
            message=v.message,
            env_key=v.env_key,
        )
        for v in violations
    ]


def _substrate_violations_to_governance(
    violations: list[SubstrateViolation],
) -> list[GovernanceViolation]:
    return [
        GovernanceViolation(
            code=f"substrate_{v.code}",
            message=v.message,
            env_key=v.env_key,
        )
        for v in violations
    ]


def _env_matrix_summary_ref(
    matrix_result: Any,
) -> dict[str, Any]:
    return {
        "mode": matrix_result.mode.value,
        "ok": matrix_result.ok,
        "violation_count": len(matrix_result.violations),
        "gate_id": "env-matrix",
    }


def _substrate_summary_ref(substrate_result: Any) -> dict[str, Any]:
    return {
        "mode": substrate_result.mode.value,
        "ok": substrate_result.ok,
        "env_matrix_ok": substrate_result.env_matrix_ok,
        "violation_count": len(substrate_result.violations),
        "gate_id": "substrate-checklist",
    }


def _admission_for_token(
    token_value: str | None,
    agent_id: str,
    capability: str,
    tokens: GovernanceTokenService | None,
    identities: IdentityLedger | None,
    now: float | None = None,
) -> AdmissionDecision:
    if not token_value or not token_value.strip():
        return AdmissionDecision(False, "token_missing", agent_id, capability)
    if tokens is None or identities is None:
        return AdmissionDecision(False, "admission_context_missing", agent_id, capability)
    stripped = token_value.strip()
    token = tokens.verify(stripped, now=now)
    if token is None:
        return AdmissionDecision(False, "token_invalid_or_expired", agent_id, capability)
    if token.agent_id != agent_id:
        return AdmissionDecision(False, "token_agent_mismatch", agent_id, capability)
    if not identities.has_capability(agent_id, capability):
        return AdmissionDecision(False, "capability_not_granted", agent_id, capability)
    return AdmissionDecision(True, "admitted", agent_id, capability)


def build_live_burst_evidence(
    *,
    agent_id: str,
    capability: str,
    policy_version: str,
    decision: AdmissionDecision,
    token_value: str | None,
    env_matrix_ok: bool,
    substrate_checklist_ok: bool,
    env_matrix_ref: dict[str, Any],
    substrate_ref: dict[str, Any],
    evidence_label: str = EVIDENCE_LABEL_INFERRED,
    live_api_called: bool = False,
    timestamp: str | None = None,
) -> LiveBurstEvidence:
    """Assemble redacted live-burst evidence from admission + layer refs."""
    if evidence_label not in (EVIDENCE_LABEL_INFERRED, EVIDENCE_LABEL_RECORDED):
        evidence_label = EVIDENCE_LABEL_INFERRED
    return LiveBurstEvidence(
        agent_id=agent_id,
        capability=capability,
        policy_version=policy_version,
        admission_allowed=decision.allowed,
        admission_reason=decision.reason,
        token_fingerprint=token_fingerprint(token_value),
        env_matrix_ok=env_matrix_ok,
        substrate_checklist_ok=substrate_checklist_ok,
        substrate_summary_ref=substrate_ref,
        env_matrix_summary_ref=env_matrix_ref,
        timestamp=timestamp or decision.timestamp or _iso_timestamp(),
        evidence_label=evidence_label,
        live_api_called=live_api_called,
    )


def evaluate_governance_evidence(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    agent_id: str = "kilo-live-proof-agent",
    capability: str = "kilo:live_burst",
    policy_version: str = "kilo-live-proof-v1",
    token_value: str | None = None,
    tokens: GovernanceTokenService | None = None,
    identities: IdentityLedger | None = None,
    now: float | None = None,
) -> GovernanceEvidenceResult:
    """Evaluate governance-evidence gate for *mode* (fail-closed)."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved_mode = _mode_from_matrix(mode, env)
    violations: list[GovernanceViolation] = []

    matrix_result = evaluate_env_matrix(resolved_mode, env)
    substrate_result = evaluate_substrate_checklist(resolved_mode, env)
    env_ok = matrix_result.ok
    substrate_ok = substrate_result.ok

    if not env_ok:
        violations.extend(_matrix_violations_to_governance(matrix_result.violations))
    if not substrate_ok:
        violations.extend(_substrate_violations_to_governance(substrate_result.violations))

    decision = _admission_for_token(token_value, agent_id, capability, tokens, identities, now=now)
    if not decision.allowed:
        code_map = {
            "token_missing": "token_missing",
            "token_invalid_or_expired": "token_invalid_or_expired",
            "token_agent_mismatch": "token_agent_mismatch",
            "capability_not_granted": "capability_not_granted",
            "admission_context_missing": "admission_context_missing",
        }
        violations.append(
            GovernanceViolation(
                code=code_map.get(decision.reason, "admission_denied"),
                message=f"admission denied: {decision.reason}",
            )
        )

    evidence = build_live_burst_evidence(
        agent_id=agent_id,
        capability=capability,
        policy_version=policy_version,
        decision=decision,
        token_value=token_value,
        env_matrix_ok=env_ok,
        substrate_checklist_ok=substrate_ok,
        env_matrix_ref=_env_matrix_summary_ref(matrix_result),
        substrate_ref=_substrate_summary_ref(substrate_result),
        evidence_label=EVIDENCE_LABEL_INFERRED,
        live_api_called=False,
    )

    ok = env_ok and substrate_ok and decision.allowed

    return GovernanceEvidenceResult(
        mode=resolved_mode,
        ok=ok,
        env_matrix_ok=env_ok,
        substrate_checklist_ok=substrate_ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def _violations_for_hermetic_operator(env: Mapping[str, str]) -> list[GovernanceViolation]:
    """Fail-closed if raw governance tokens appear in hermetic operator env."""
    hits: list[GovernanceViolation] = []
    for key in ("THINKBOX_GOVERNANCE_TOKEN", "GOVERNANCE_TOKEN"):
        raw = env.get(key, "").strip()
        if raw and len(raw) >= _TOKEN_MIN_LEN and not raw.startswith("mock_"):
            hits.append(
                GovernanceViolation(
                    code="forbidden_live_token_in_hermetic",
                    message=f"{key} must not hold production token in hermetic operator paths",
                    env_key=key,
                )
            )
    return hits


def hermetic_governance_operator_check(
    environ: Mapping[str, str] | None = None,
) -> GovernanceEvidenceResult:
    """Spine/CI operator check: substrate + env-matrix operator pass, no live secrets."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    substrate_op = hermetic_substrate_operator_check(env)
    violations: list[GovernanceViolation] = []
    if not substrate_op.ok:
        violations.extend(_substrate_violations_to_governance(substrate_op.violations))
    violations.extend(_violations_for_hermetic_operator(env))

    matrix_ref = _env_matrix_summary_ref(evaluate_env_matrix(mode, env))
    substrate_ref = _substrate_summary_ref(substrate_op)

    decision = AdmissionDecision(
        allowed=len(violations) == 0,
        reason="hermetic_operator_ok" if not violations else "hermetic_operator_denied",
    )
    evidence = build_live_burst_evidence(
        agent_id="operator",
        capability="kilo:governance_evidence_check",
        policy_version="hermetic",
        decision=decision,
        token_value=None,
        env_matrix_ok=substrate_op.env_matrix_ok,
        substrate_checklist_ok=substrate_op.ok,
        env_matrix_ref=matrix_ref,
        substrate_ref=substrate_ref,
        evidence_label=EVIDENCE_LABEL_INFERRED,
        live_api_called=False,
    )
    return GovernanceEvidenceResult(
        mode=mode,
        ok=len(violations) == 0,
        env_matrix_ok=substrate_op.env_matrix_ok,
        substrate_checklist_ok=substrate_op.ok,
        violations=violations,
        evidence=evidence,
    )


def governance_evidence_gate_closed() -> bool:
    """True when PR #145 gate passes under hermetic_unit with clean env."""
    gate = gate_for_pr(PR_NUMBER)
    if gate is None or gate.gate_id != GATE_ID:
        return False
    env = minimal_governance_hermetic_environ()
    op = hermetic_governance_operator_check(env)
    tokens = GovernanceTokenService(signing_key="hermetic-governance-evidence")
    identities = IdentityLedger()
    identities.register(
        agent_id="kilo-live-proof-agent",
        capabilities=["kilo:live_burst"],
        policy_version="kilo-live-proof-v1",
    )
    issued = tokens.issue(
        TokenRequest(
            agent_id="kilo-live-proof-agent",
            capabilities=["kilo:live_burst"],
            policy_version="kilo-live-proof-v1",
            ttl_seconds=3600.0,
        )
    )
    unit = evaluate_governance_evidence(
        EnvMatrixMode.HERMETIC_UNIT,
        env,
        token_value=issued.token_value,
        tokens=tokens,
        identities=identities,
    )
    return op.ok and unit.ok


def governance_evidence_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Hermetic summary for CLI and spine consumers (redacted)."""
    env = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    operator = hermetic_governance_operator_check(env)
    prep = evaluate_governance_evidence(EnvMatrixMode.LIVE_PROOF_PREP, env)
    gate = gate_for_pr(PR_NUMBER)
    redacted_env_sample = {
        k: redact_secret_value(k, env.get(k))
        for k in sorted(
            set(env.keys())
            & (_SECRET_ENV_KEYS | {"THINKBOX_SWARM_LIVE_ACK", "THINKBOX_KILO_MATRIX_MODE"})
        )
    }
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "detected_mode": mode.value,
        "env_matrix_layer": True,
        "substrate_checklist_layer": True,
        "hermetic_operator_ok": operator.ok,
        "hermetic_env_matrix_ok": operator.env_matrix_ok,
        "hermetic_substrate_ok": operator.substrate_checklist_ok,
        "live_proof_prep_ok": prep.ok,
        "live_proof_prep_violation_codes": sorted({v.code for v in prep.violations}),
        "hermetic_violation_codes": sorted({v.code for v in operator.violations}),
        "evidence_shape_fields": sorted(LiveBurstEvidence.__dataclass_fields__.keys()),
        "redacted_env_sample": redacted_env_sample,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "arc_gate_theme": gate.theme if gate else None,
        "gate_closed_default": governance_evidence_gate_closed(),
    }


def minimal_governance_hermetic_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Clean hermetic env for governance-evidence unit tests."""
    base: MutableMapping[str, str] = dict(minimal_substrate_hermetic_environ())
    if extra:
        base.update(extra)
    return dict(base)


def _scrub_raw_tokens_from_text(text: str) -> str:
    """Remove govt.* token literals from serialized summaries."""
    return re.sub(r"govt\.[^\s\"']+", "<redacted-govt-token>", text)
