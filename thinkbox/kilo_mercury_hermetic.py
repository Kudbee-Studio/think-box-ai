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

