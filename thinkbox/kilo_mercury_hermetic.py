"""Hermetic Mercury mock client + live-gate stub alignment (PR #146, ``mercury-hermetic``).

Layers on PR #142 ``env-matrix``, PR #143 ``substrate-checklist``, and PR #145
``governance-evidence``. Bounded mock completions for Live-proof prep shape — no
network, no ``INCEPTION_API_KEY`` consumption, ``live_api_called=False`` in hermetic
modes. Aligned with ``thinkbox/cli_live_gate.swarm_live_authorization_report``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, MutableMapping

from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.kilo_env_matrix import (
    EnvMatrixMode,
    detect_matrix_mode,
    evaluate_env_matrix,
)
from thinkbox.kilo_governance_evidence import (
    GovernanceEvidenceResult,
    LiveBurstEvidence,
    evaluate_governance_evidence,
    hermetic_governance_operator_check,
    minimal_governance_hermetic_environ,
    redact_secret_value,
)
from thinkbox.kilo_live_proof_readiness import gate_for_pr
from thinkbox.kilo_substrate_checklist import redact_box_token, redact_box_url

__all__ = (
    "BoundedMercuryMockClient",
    "GATE_ID",
    "MERCURY_HERMETIC_MODEL",
    "MercuryHermeticCallResult",
    "MercuryHermeticEvidence",
    "MercuryHermeticResult",
    "MercuryHermeticViolation",
    "MercuryMockMode",
    "PR_NUMBER",
    "align_live_gate_stub",
    "bounded_mercury_fixtures",
    "evaluate_mercury_hermetic",
    "hermetic_mercury_operator_check",
    "mercury_hermetic_contract_summary",
    "mercury_hermetic_gate_closed",
    "minimal_mercury_hermetic_environ",
    "mock_client_configured",
    "redact_mercury_summary",
)

GATE_ID = "mercury-hermetic"
PR_NUMBER = 146

MERCURY_HERMETIC_MODEL = "mercury-2"
_MOCK_ENV_KEY = "THINKBOX_KILO_MERCURY_MOCK"
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
_KEY_MIN_LEN = 12


class MercuryMockMode(str, Enum):
    """Alias of env-matrix modes for mercury-hermetic reporting."""

    HERMETIC_UNIT = EnvMatrixMode.HERMETIC_UNIT.value
    HERMETIC_CI = EnvMatrixMode.HERMETIC_CI.value
    LIVE_PROOF_PREP = EnvMatrixMode.LIVE_PROOF_PREP.value


@dataclass(frozen=True)
class MercuryHermeticViolation:
    """Single fail-closed mercury-hermetic violation."""

    code: str
    message: str
    env_key: str | None = None


@dataclass(frozen=True)
class MercuryHermeticCallResult:
    """Bounded mock Mercury completion (no network)."""

    model: str
    content: str
    reasoning: str | None
    prompt_chars: int
    fixture_id: str
    live_api_called: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "content": self.content,
            "reasoning": self.reasoning,
            "prompt_chars": self.prompt_chars,
            "fixture_id": self.fixture_id,
            "live_api_called": self.live_api_called,
        }


@dataclass(frozen=True)
class MercuryHermeticEvidence:
    """Redacted evidence for mercury-hermetic gate (hermetic contract)."""

    gate_id: str
    pr_number: int
    governance_evidence_ok: bool
    governance_summary_ref: dict[str, Any]
    live_gate_report: dict[str, Any]
    mock_client_configured: bool
    mock_call: MercuryHermeticCallResult | None
    model: str
    evidence_label: str
    live_api_called: bool
    governance_evidence: LiveBurstEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "pr_number": self.pr_number,
            "governance_evidence_ok": self.governance_evidence_ok,
            "governance_summary_ref": self.governance_summary_ref,
            "live_gate_report": self.live_gate_report,
            "mock_client_configured": self.mock_client_configured,
            "mock_call": self.mock_call.to_dict() if self.mock_call else None,
            "model": self.model,
            "evidence_label": self.evidence_label,
            "live_api_called": self.live_api_called,
            "governance_evidence": (
                self.governance_evidence.to_dict() if self.governance_evidence else None
            ),
        }


@dataclass
class MercuryHermeticResult:
    """Outcome of evaluating mercury-hermetic for one mode."""

    mode: EnvMatrixMode
    ok: bool
    governance_evidence_ok: bool
    env_matrix_ok: bool
    substrate_checklist_ok: bool
    violations: list[MercuryHermeticViolation] = field(default_factory=list)
    evidence: MercuryHermeticEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "ok": self.ok,
            "governance_evidence_ok": self.governance_evidence_ok,
            "env_matrix_ok": self.env_matrix_ok,
            "substrate_checklist_ok": self.substrate_checklist_ok,
            "violations": [
                {"code": v.code, "message": v.message, "env_key": v.env_key}
                for v in self.violations
            ],
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "gate_id": GATE_ID,
            "pr_number": PR_NUMBER,
            "four_state_max": "TEST_VERIFIED",
        }


def bounded_mercury_fixtures() -> dict[str, dict[str, Any]]:
    """Fixed mock response shapes for Live-proof prep (bounded, no secrets)."""
    return {
        "json_answer": {
            "content": '{"answer": 42}',
            "reasoning": "hermetic mock: bounded JSON answer fixture",
        },
        "think_token": {
            "content": '{"status": "ok"}',
            "reasoning": "THINK hermetic stub — not live Mercury",
        },
        "live_proof_prep": {
            "content": '{"kilo_live_proof_prep": true}',
            "reasoning": "prep shape only; live_api_called remains false",
        },
    }


def mock_client_configured(environ: Mapping[str, str]) -> bool:
    """True when hermetic Mercury mock mode or mock:// provider URL is set."""
    mock_flag = (environ.get(_MOCK_ENV_KEY) or "").strip().lower()
    if mock_flag in ("1", "true", "yes", "hermetic", "bounded"):
        return True
    for key in ("THINKBOX_MERCURY_BASE_URL", "THINKBOX_PROVIDER_BASE_URL"):
        value = (environ.get(key) or "").strip()
        if value.startswith("mock://"):
            return True
        if value.startswith("http://127.0.0.1") or value.startswith("http://localhost"):
            return True
    return False


class BoundedMercuryMockClient:
    """Sync-only bounded Mercury mock — never performs HTTP."""

    def __init__(
        self,
        *,
        fixture_id: str = "json_answer",
        model: str = MERCURY_HERMETIC_MODEL,
    ) -> None:
        fixtures = bounded_mercury_fixtures()
        if fixture_id not in fixtures:
            raise ValueError(f"unknown mercury fixture: {fixture_id}")
        self._fixture_id = fixture_id
        self._model = model
        self._fixture = fixtures[fixture_id]

    def complete(self, prompt: str) -> MercuryHermeticCallResult:
        """Return a bounded completion for *prompt* without network I/O."""
        content = str(self._fixture["content"])
        reasoning = self._fixture.get("reasoning")
        if isinstance(reasoning, str):
            reasoning_out: str | None = reasoning
        else:
            reasoning_out = None
        return MercuryHermeticCallResult(
            model=self._model,
            content=content,
            reasoning=reasoning_out,
            prompt_chars=len(prompt),
            fixture_id=self._fixture_id,
            live_api_called=False,
        )


def align_live_gate_stub(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Merge ``cli_live_gate`` authorization report with mercury-hermetic metadata."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    ack = (env.get("THINKBOX_SWARM_LIVE_ACK") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "accept",
    )
    provider_present = any((env.get(k) or "").strip() for k in _PROVIDER_KEYS)
    missing: list[str] = []
    if not provider_present:
        missing.append(f"one of: {', '.join(_PROVIDER_KEYS)}")
    if not ack:
        missing.append("THINKBOX_SWARM_LIVE_ACK=1 (founder explicit live ack)")
    report: dict[str, Any] = {
        "authorized": provider_present and ack,
        "provider_credential_present": provider_present,
        "founder_ack_present": ack,
        "missing": missing,
        "mode": "authorization_check_only",
        "live_api_called": False,
        "evidence_label": "inferred",
    }
    report["gate_id"] = GATE_ID
    report["pr_number"] = PR_NUMBER
    report["mercury_network_io"] = False
    report["mock_client_configured"] = mock_client_configured(env)
    return report


def redact_mercury_summary(text: str) -> str:
    """Scrub provider key-like literals from serialized summaries."""
    scrubbed = text
    for key in _PROVIDER_KEYS:
        scrubbed = re.sub(
            rf'("{key}"\s*:\s*")[^"]+(")',
            rf"\1<redacted>\2",
            scrubbed,
        )
    return scrubbed


def _governance_violations_to_mercury(
    gov: GovernanceEvidenceResult,
) -> list[MercuryHermeticViolation]:
    return [
        MercuryHermeticViolation(
            code=f"governance_{v.code}",
            message=v.message,
            env_key=v.env_key,
        )
        for v in gov.violations
    ]


def _governance_summary_ref(gov: GovernanceEvidenceResult) -> dict[str, Any]:
    return {
        "mode": gov.mode.value,
        "ok": gov.ok,
        "env_matrix_ok": gov.env_matrix_ok,
        "substrate_checklist_ok": gov.substrate_checklist_ok,
        "violation_count": len(gov.violations),
        "gate_id": "governance-evidence",
    }


def _mode_from_matrix(
    mode: EnvMatrixMode | None,
    environ: Mapping[str, str],
) -> EnvMatrixMode:
    if mode is not None:
        return mode
    return detect_matrix_mode(environ)


def evaluate_mercury_hermetic(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    agent_id: str = "kilo-live-proof-agent",
    capability: str = "kilo:live_burst",
    policy_version: str = "kilo-live-proof-v1",
    token_value: str | None = None,
    tokens: GovernanceTokenService | None = None,
    identities: IdentityLedger | None = None,
    fixture_id: str = "json_answer",
    run_mock_call: bool = True,
    now: float | None = None,
) -> MercuryHermeticResult:
    """Evaluate mercury-hermetic gate for *mode* (fail-closed)."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved_mode = _mode_from_matrix(mode, env)
    violations: list[MercuryHermeticViolation] = []

    gov = evaluate_governance_evidence(
        resolved_mode,
        env,
        agent_id=agent_id,
        capability=capability,
        policy_version=policy_version,
        token_value=token_value,
        tokens=tokens,
        identities=identities,
        now=now,
    )
    if not gov.ok:
        violations.extend(_governance_violations_to_mercury(gov))

    mock_ok = mock_client_configured(env)
    if not mock_ok:
        violations.append(
            MercuryHermeticViolation(
                code="mercury_mock_not_configured",
                message=(
                    f"{_MOCK_ENV_KEY}=hermetic or mock:// provider URL required "
                    "in hermetic mercury paths"
                ),
                env_key=_MOCK_ENV_KEY,
            )
        )

    mock_call: MercuryHermeticCallResult | None = None
    if mock_ok and run_mock_call:
        try:
            client = BoundedMercuryMockClient(fixture_id=fixture_id)
            mock_call = client.complete("kilo mercury hermetic probe")
        except ValueError as exc:
            violations.append(
                MercuryHermeticViolation(
                    code="mercury_mock_fixture_invalid",
                    message=str(exc),
                )
            )

    live_gate = align_live_gate_stub(env)
    if live_gate.get("live_api_called"):
        violations.append(
            MercuryHermeticViolation(
                code="live_api_called_forbidden",
                message="live_api_called must be false in mercury-hermetic hermetic modes",
            )
        )

    evidence = MercuryHermeticEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        governance_evidence_ok=gov.ok,
        governance_summary_ref=_governance_summary_ref(gov),
        live_gate_report=live_gate,
        mock_client_configured=mock_ok,
        mock_call=mock_call,
        model=MERCURY_HERMETIC_MODEL,
        evidence_label="inferred",
        live_api_called=False,
        governance_evidence=gov.evidence,
    )

    ok = gov.ok and mock_ok and len(violations) == 0
    return MercuryHermeticResult(
        mode=resolved_mode,
        ok=ok,
        governance_evidence_ok=gov.ok,
        env_matrix_ok=gov.env_matrix_ok,
        substrate_checklist_ok=gov.substrate_checklist_ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def _forbidden_live_provider_key_in_hermetic(
    env: Mapping[str, str],
) -> list[MercuryHermeticViolation]:
    """Fail-closed when a production-shaped provider key is set without mock mode."""
    if mock_client_configured(env):
        return []
    hits: list[MercuryHermeticViolation] = []
    for key in _PROVIDER_KEYS:
        raw = (env.get(key) or "").strip()
        if not raw or len(raw) < _KEY_MIN_LEN:
            continue
        if raw.startswith("mock_") or raw.startswith("test_"):
            continue
        hits.append(
            MercuryHermeticViolation(
                code="forbidden_live_provider_without_mock",
                message=(
                    f"{key} present without {_MOCK_ENV_KEY} or mock:// URL "
                    "in hermetic operator paths"
                ),
                env_key=key,
            )
        )
    return hits


def hermetic_mercury_operator_check(
    environ: Mapping[str, str] | None = None,
) -> MercuryHermeticResult:
    """Spine/CI operator check: governance operator + mercury mock contract."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    gov_op = hermetic_governance_operator_check(env)
    violations: list[MercuryHermeticViolation] = []
    if not gov_op.ok:
        violations.extend(_governance_violations_to_mercury(gov_op))
    violations.extend(_forbidden_live_provider_key_in_hermetic(env))

    live_gate = align_live_gate_stub(env)
    mock_ok = mock_client_configured(env) or not any(
        (env.get(k) or "").strip() for k in _PROVIDER_KEYS
    )

    evidence = MercuryHermeticEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        governance_evidence_ok=gov_op.ok,
        governance_summary_ref=_governance_summary_ref(gov_op),
        live_gate_report=live_gate,
