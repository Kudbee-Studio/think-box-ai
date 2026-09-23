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
