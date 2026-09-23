"""Governance-evidence Live-proof readiness helpers (PR #164).

Hermetic contracts for a future founder-run Live proof on the governance-evidence
path. Documents founder ack and Box URL prerequisites without performing live HTTP.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.kilo_governance_evidence import (
    GATE_ID as GOVERNANCE_EVIDENCE_GATE_ID,
    evaluate_governance_evidence,
    governance_evidence_contract_summary,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode
from thinkbox.kilo_live_proof_exec import FOUNDER_ACK_ENV
from thinkbox.kilo_substrate_checklist import BOX_URL_ENV

GOVERNANCE_EVIDENCE_LIVE_PROOF_READINESS_LABEL = "governance_evidence_live_proof_readiness"
GOVERNANCE_EVIDENCE_LIVE_PROOF_READINESS_VERSION = "1"
READINESS_SCHEMA_VERSION = "kilo-governance-evidence-live-proof-readiness-v1"

_FORBIDDEN_LITERAL_CLAIMS = (
    "KILO LIVE VERIFIED",
    "KILO PRODUCTION READY",
    "KILO live build verified",
)

_SECRET_PATTERN = re.compile(
    r"(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._-]{20,}|UPSTASH_PUBLIC_BOX_TOKEN=[^\s]+)",
    re.IGNORECASE,
)

_REQUIRED_TOP_LEVEL: tuple[str, ...] = (
    "schema_version",
    "readiness_id",
    "gate_id",
    "pr_number",
    "four_state_max",
    "live_verified",
    "live_api_called",
    "founder_ack_env_key",
    "founder_ack_documented",
    "box_url_env_key",
    "box_url_documented",
    "governance_evidence_gate_id",
    "prior_gate_ids",
    "readiness_checks",
    "recorded_at",
)


@dataclass(frozen=True)
class ReadinessViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ReadinessValidationResult:
    ok: bool
    violations: tuple[ReadinessViolation, ...]


def _violation(code: str, message: str, path: str | None = None) -> ReadinessViolation:
    return ReadinessViolation(code=code, message=message, path=path)


def _founder_ack_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "accept")


def live_proof_prereqs_satisfied(environ: Mapping[str, str]) -> bool:
    """True when founder ack and public Box URL are both present (live prep only)."""
    ack = _founder_ack_truthy(environ.get(FOUNDER_ACK_ENV))
    url = (environ.get(BOX_URL_ENV) or "").strip()
    return ack and bool(url) and ".box.upstash.com" in url


def documented_live_prereqs() -> dict[str, str]:
    """Operator-facing prereq keys (documented, not required for hermetic gate pass)."""
    return {
        "founder_ack_env_key": FOUNDER_ACK_ENV,
        "box_url_env_key": BOX_URL_ENV,
        "note": (
            "Founder ack and Box URL are required only for optional live_prep paths; "
            "hermetic verify stays closed without them and must not call live APIs."
        ),
    }


def governance_evidence_live_proof_readiness_contract_snippet() -> dict[str, Any]:
    """Small JSON-safe snippet embedded in guides and audit passes."""
    return {
        "label": GOVERNANCE_EVIDENCE_LIVE_PROOF_READINESS_LABEL,
        "version": GOVERNANCE_EVIDENCE_LIVE_PROOF_READINESS_VERSION,
        "schema_version": READINESS_SCHEMA_VERSION,
        "governance_evidence_gate_id": GOVERNANCE_EVIDENCE_GATE_ID,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "documented_prereqs": documented_live_prereqs(),
    }


def _scan_redaction(text: str, path: str, hits: list[ReadinessViolation]) -> None:
    for forbidden in _FORBIDDEN_LITERAL_CLAIMS:
        if forbidden in text:
            hits.append(
                _violation(
                    "forbidden_affirmative_claim",
                    f"forbidden literal: {forbidden}",
                    path,
                )
            )
    if _SECRET_PATTERN.search(text):
        hits.append(_violation("secret_like_literal", "secret-shaped literal", path))


def validate_readiness_document(doc: Mapping[str, Any]) -> ReadinessValidationResult:
    """Fail-closed validator for governance-evidence Live-proof readiness JSON."""
    hits: list[ReadinessViolation] = []
    serialized = json.dumps(doc, sort_keys=True)
    _scan_redaction(serialized, "$", hits)

    if not isinstance(doc, Mapping):
        return ReadinessValidationResult(False, tuple(hits))

    for key in _REQUIRED_TOP_LEVEL:
        if key not in doc:
            hits.append(_violation("missing_required", f"missing {key}", key))

    if doc.get("schema_version") != READINESS_SCHEMA_VERSION:
        hits.append(
            _violation(
                "schema_version",
                f"schema_version must be {READINESS_SCHEMA_VERSION}",
                "schema_version",
            )
        )

    if doc.get("founder_ack_env_key") != FOUNDER_ACK_ENV:
        hits.append(
            _violation(
                "founder_ack_env_key",
                f"founder_ack_env_key must be {FOUNDER_ACK_ENV}",
                "founder_ack_env_key",
            )
        )

    if doc.get("box_url_env_key") != BOX_URL_ENV:
        hits.append(
            _violation("box_url_env_key", f"box_url_env_key must be {BOX_URL_ENV}", "box_url_env_key")
        )

    if doc.get("governance_evidence_gate_id") != GOVERNANCE_EVIDENCE_GATE_ID:
        hits.append(
            _violation(
                "governance_evidence_gate_id",
                f"must reference {GOVERNANCE_EVIDENCE_GATE_ID}",
                "governance_evidence_gate_id",
            )
        )

    if doc.get("four_state_max") != "TEST_VERIFIED":
        hits.append(
            _violation("four_state_max", "four_state_max must be TEST_VERIFIED", "four_state_max")
        )

    if doc.get("live_verified") is True:
        hits.append(
            _violation(
                "live_verified_forbidden",
                "live_verified must remain false in hermetic readiness documents",
                "live_verified",
            )
        )

    if doc.get("live_api_called") is True:
        hits.append(
            _violation(
                "live_api_called_forbidden",
                "live_api_called must remain false in hermetic readiness documents",
                "live_api_called",
            )
        )

    if doc.get("founder_ack_documented") is not True:
        hits.append(
            _violation(
                "founder_ack_documented",
                "founder_ack_documented must be true (documented prereq, not satisfied in hermetic)",
                "founder_ack_documented",
            )
        )

    if doc.get("box_url_documented") is not True:
        hits.append(
            _violation(
                "box_url_documented",
                "box_url_documented must be true (documented prereq, not satisfied in hermetic)",
                "box_url_documented",
            )
        )

    checks = doc.get("readiness_checks")
    if not isinstance(checks, list) or not checks:
        hits.append(
            _violation("readiness_checks", "readiness_checks must be a non-empty array", "readiness_checks")
        )
    elif isinstance(checks, list):
        required_check_ids = {
            "governance_evidence_hermetic_unit",
            "documented_founder_ack",
            "documented_box_url",
            "no_live_api_in_hermetic",
        }
        seen = {str(c.get("check_id")) for c in checks if isinstance(c, Mapping)}
        missing_checks = sorted(required_check_ids - seen)
        if missing_checks:
            hits.append(
                _violation(
                    "readiness_checks_incomplete",
                    f"missing checks: {','.join(missing_checks)}",
                    "readiness_checks",
                )
            )

    return ReadinessValidationResult(len(hits) == 0, tuple(hits))


def minimal_valid_readiness_document(
    *,
    gate_id: str,
    pr_number: int,
    prior_gate_ids: list[str],
) -> dict[str, Any]:
    """Canonical hermetic readiness document (live_verified:false)."""
    return {
        "schema_version": READINESS_SCHEMA_VERSION,
        "readiness_id": f"kilo-gov-evidence-readiness-pr{pr_number}-hermetic",
        "gate_id": gate_id,
        "pr_number": pr_number,
        "four_state_max": "TEST_VERIFIED",
        "live_verified": False,
        "live_api_called": False,
        "founder_ack_env_key": FOUNDER_ACK_ENV,
        "founder_ack_documented": True,
        "box_url_env_key": BOX_URL_ENV,
        "box_url_documented": True,
        "governance_evidence_gate_id": GOVERNANCE_EVIDENCE_GATE_ID,
        "prior_gate_ids": prior_gate_ids,
        "readiness_checks": [
            {
                "check_id": "governance_evidence_hermetic_unit",
                "status": "pass",
                "live_api_called": False,
            },
            {
                "check_id": "documented_founder_ack",
                "status": "documented",
                "env_key": FOUNDER_ACK_ENV,
            },
            {
                "check_id": "documented_box_url",
                "status": "documented",
                "env_key": BOX_URL_ENV,
            },
            {
                "check_id": "no_live_api_in_hermetic",
                "status": "pass",
                "live_api_called": False,
            },
        ],
        "recorded_at": "2026-09-23T00:00:00+00:00",
    }


def evaluate_governance_evidence_hermetic_unit(
    environ: Mapping[str, str],
) -> tuple[bool, dict[str, Any]]:
    """Run PR #145 governance-evidence gate under hermetic_unit with in-memory token."""
    tokens = GovernanceTokenService(signing_key="hermetic-governance-evidence-readiness")
    identities = IdentityLedger()
    agent_id = "kilo-live-proof-agent"
    capability = "kilo:live_burst"
    policy_version = "kilo-live-proof-v1"
    identities.register(
        agent_id=agent_id,
        capabilities=[capability],
        policy_version=policy_version,
    )
    issued = tokens.issue(
        TokenRequest(
            agent_id=agent_id,
            capabilities=[capability],
            policy_version=policy_version,
            ttl_seconds=3600.0,
        )
    )
    result = evaluate_governance_evidence(
        EnvMatrixMode.HERMETIC_UNIT,
        environ,
        token_value=issued.token_value,
        tokens=tokens,
        identities=identities,
    )
    summary = governance_evidence_contract_summary(environ)
    payload = {
        "governance_evidence_ok": result.ok,
        "hermetic_operator_ok": summary.get("hermetic_operator_ok"),
        "live_api_called": False,
        "live_verified": False,
        "violation_codes": sorted({v.code for v in result.violations}),
    }
    return result.ok and bool(summary.get("hermetic_operator_ok")), payload
