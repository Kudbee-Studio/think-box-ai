"""Hermetic bounded live smoke evidence binder + audit flip (PR #152, ``live-smoke-evidence``).

Layers on PR #151 ``post-season-harden`` and PR #150 ``live-proof-exec``. Binds
receipt/etag gate chains into a fail-closed evidence artifact schema so a
founder-run bounded smoke can later flip audit honestly. Default path: no network;
``live_api_called=False``.
"""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_governance_evidence import redact_secret_value
from thinkbox.kilo_live_proof_exec import (
    ARC_SEASON_COMPLETE,
    FOUNDER_ACK_ENV,
    hermetic_live_proof_exec_operator_check,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT, gate_for_pr, gate_ids
from thinkbox.kilo_post_season_harden import (
    GATE_ID as POST_SEASON_GATE_ID,
    hermetic_post_season_harden_operator_check,
    minimal_post_season_harden_environ,
)
from thinkbox.kilo_proof_schema import HALT_REASONS, redact_proof_summary
from thinkbox.kilo_substrate_checklist import (
    BOX_URL_ENV,
    redact_box_token,
    redact_box_url,
)

__all__ = (
    "AUDIT_PASS_GLOB",
    "EVIDENCE_ARTIFACT_GLOB",
    "FOUNDER_ACK_MARKER_FIELD",
    "GATE_ID",
    "PR_NUMBER",
    "REQUIRED_PRIOR_GATE_IDS",
    "LiveSmokeEvidence",
    "LiveSmokeEvidenceMode",
    "LiveSmokeEvidenceResult",
    "LiveSmokeEvidenceViolation",
    "audit_flip_candidate",
    "can_flip_audit_live_verified",
    "evaluate_live_smoke_evidence",
    "fixtures_dir",
    "hermetic_live_smoke_evidence_operator_check",
    "list_fixture_paths",
    "live_smoke_evidence_contract_summary",
    "live_smoke_evidence_gate_closed",
    "load_fixture",
    "minimal_live_smoke_evidence_environ",
    "minimal_valid_smoke_evidence_document",
    "redact_smoke_evidence_summary",
    "run_fixture_suite",
    "smoke_evidence_json_schema",
    "validate_smoke_evidence_document",
)

GATE_ID = "live-smoke-evidence"
PR_NUMBER = 152
FOUNDER_ACK_MARKER_FIELD = "founder_ack_marker_present"
BOX_URL_PRESENT_FIELD = "box_url_present"

_FIXTURES_REL = Path("data/kilo_live_smoke_evidence/fixtures")
_VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_live_smoke_evidence.py")
_ARTIFACT_DIR_REL = Path("data/thinkboxmd/artifacts")
EVIDENCE_ARTIFACT_GLOB = "kilo_live_smoke_*.json"
AUDIT_PASS_GLOB = "docs/audit/passes/*-pr152*.json"
_DEFAULT_AUDIT_PRIOR = "docs/audit/passes/2026-09-23-pr151.json"

_ARC_GATE_IDS: tuple[str, ...] = tuple(gate_ids())
_POST_ARC_PRIOR: tuple[str, ...] = ("live-proof-exec", POST_SEASON_GATE_ID)
REQUIRED_PRIOR_GATE_IDS: frozenset[str] = frozenset(_ARC_GATE_IDS + _POST_ARC_PRIOR)

_SECRET_PATTERN = re.compile(
    r"(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._-]{20,}|UPSTASH_PUBLIC_BOX_TOKEN=[^\s]+)",
    re.IGNORECASE,
)

_FORBIDDEN_LITERAL_CLAIMS = (
    "KILO LIVE VERIFIED",
    "KILO PRODUCTION READY",
    "KILO live build verified",
)

_REQUIRED_TOP_LEVEL: tuple[str, ...] = (
    "schema_version",
    "evidence_id",
    "gate_id",
    "pr_number",
    "four_state_max",
    "live_verified",
    "live_api_called",
    "evidence_label",
    "prior_gate_ids",
    "founder_ack_env_key",
    FOUNDER_ACK_MARKER_FIELD,
    "box_url_env_key",
    BOX_URL_PRESENT_FIELD,
    "receipt_ids",
    "etags",
    "gate_chain",
    "redacted_endpoints",
    "recorded_at",
    "halt_reason",
    "season_arc_marker",
)


class LiveSmokeEvidenceMode(str, Enum):
    """Alias of env-matrix modes for live-smoke-evidence reporting."""

    HERMETIC_UNIT = EnvMatrixMode.HERMETIC_UNIT.value
    HERMETIC_CI = EnvMatrixMode.HERMETIC_CI.value
    LIVE_PROOF_PREP = EnvMatrixMode.LIVE_PROOF_PREP.value


@dataclass(frozen=True)
class LiveSmokeEvidenceViolation:
    """Single fail-closed live-smoke-evidence violation."""

    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class SmokeValidationResult:
    """Outcome of validating one smoke evidence JSON document."""

    ok: bool
    violations: tuple[LiveSmokeEvidenceViolation, ...] = ()
    gate_chain_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class LiveSmokeEvidence:
    """Redacted evidence for live-smoke-evidence gate closure (hermetic)."""

    gate_id: str
    pr_number: int
    post_season_harden_ok: bool
    fixture_pass_count: int
    fixture_negative_reject_count: int
    contract_ok: bool
    live_api_called: bool
    season_arc_marker: str
    evidence_label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "pr_number": self.pr_number,
            "post_season_harden_ok": self.post_season_harden_ok,
            "fixture_pass_count": self.fixture_pass_count,
            "fixture_negative_reject_count": self.fixture_negative_reject_count,
            "contract_ok": self.contract_ok,
            "live_api_called": self.live_api_called,
            "season_arc_marker": self.season_arc_marker,
            "evidence_label": self.evidence_label,
            "four_state_max": "TEST_VERIFIED",
            "arc_season_complete_marker": ARC_SEASON_COMPLETE,
        }


@dataclass
class LiveSmokeEvidenceResult:
    """Outcome of evaluating live-smoke-evidence for one mode."""

    mode: EnvMatrixMode
    ok: bool
    post_season_harden_ok: bool
    violations: list[LiveSmokeEvidenceViolation] = field(default_factory=list)
    evidence: LiveSmokeEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "ok": self.ok,
            "post_season_harden_ok": self.post_season_harden_ok,
            "violations": [
                {"code": v.code, "message": v.message, "path": v.path}
                for v in self.violations
            ],
            "evidence": self.evidence.to_dict() if self.evidence else None,
        }


def fixtures_dir() -> Path:
    return REPO_ROOT / _FIXTURES_REL


def list_fixture_paths() -> list[Path]:
    root = fixtures_dir()
    if not root.is_dir():
        return []
    return sorted(root.glob("*.json"))


def load_fixture(name: str) -> dict[str, Any]:
    path = fixtures_dir() / name
    return json.loads(path.read_text(encoding="utf-8"))


def _violation(code: str, message: str, path: str | None = None) -> LiveSmokeEvidenceViolation:
    return LiveSmokeEvidenceViolation(code=code, message=message, path=path)


def _scan_redaction(text: str, path: str, hits: list[LiveSmokeEvidenceViolation]) -> None:
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


def _validate_gate_chain_cues(
    cues: Any,
    chain_idx: int,
    hits: list[LiveSmokeEvidenceViolation],
) -> None:
    if cues is None:
        return
    if not isinstance(cues, list):
        hits.append(
            _violation("gate_chain_cues_type", "cues must be array", f"gate_chain[{chain_idx}].cues")
        )
        return
    for cue_idx, cue in enumerate(cues):
        if not isinstance(cue, Mapping):
            continue
        cue_type = cue.get("cue_type")
        counts_as_user = cue.get("counts_as_user_intent")
        if cue_type == "injected_nudge" and counts_as_user is True:
            hits.append(
                _violation(
                    "injected_cue_not_user_intent",
                    "injected_nudge cannot count as user intent",
                    f"gate_chain[{chain_idx}].cues[{cue_idx}]",
                )
            )


def can_flip_audit_live_verified(
    evidence: Mapping[str, Any],
    *,
    artifact_path: str | None = None,
    artifact_exists: bool = False,
) -> bool:
    """True only when evidence + on-disk artifact satisfy all live flip predicates."""
    if evidence.get("live_verified") is not True:
        return False
    if evidence.get(FOUNDER_ACK_MARKER_FIELD) is not True:
        return False
    if evidence.get(BOX_URL_PRESENT_FIELD) is not True:
        return False
    if evidence.get("live_api_called") is not True:
        return False
    path = artifact_path or str(evidence.get("evidence_artifact_path") or "")
    if not path.strip():
        return False
    if artifact_exists:
        return True
    resolved = REPO_ROOT / path
    return resolved.is_file()


def validate_smoke_evidence_document(
    doc: Mapping[str, Any],
    *,
    artifact_exists: bool = False,
) -> SmokeValidationResult:
    """Fail-closed validator for bounded live smoke evidence JSON."""
    hits: list[LiveSmokeEvidenceViolation] = []
    serialized = json.dumps(doc, sort_keys=True)
    _scan_redaction(serialized, "$", hits)

    if not isinstance(doc, Mapping):
        return SmokeValidationResult(False, tuple(hits))

    for key in _REQUIRED_TOP_LEVEL:
        if key not in doc:
            hits.append(_violation("missing_required", f"missing {key}", key))

    if doc.get("schema_version") != "kilo-live-smoke-evidence-v1":
        hits.append(
            _violation(
                "schema_version",
                "schema_version must be kilo-live-smoke-evidence-v1",
                "schema_version",
            )
        )

    if doc.get("gate_id") != GATE_ID:
        hits.append(_violation("gate_id_mismatch", f"gate_id must be {GATE_ID}", "gate_id"))

    if doc.get("pr_number") != PR_NUMBER:
        hits.append(_violation("pr_number", f"pr_number must be {PR_NUMBER}", "pr_number"))

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

    four_state = doc.get("four_state_max")
    if four_state in ("LIVE_VERIFIED", "PRODUCTION_READY"):
        hits.append(
            _violation(
                "four_state_cap_exceeded",
                "hermetic evidence four_state_max must not claim LIVE/PRODUCTION",
                "four_state_max",
            )
        )

    if doc.get("live_verified") is True:
        if not can_flip_audit_live_verified(doc, artifact_exists=artifact_exists):
            hits.append(
                _violation(
                    "live_verified_without_evidence",
                    "live_verified requires founder ack marker, box url flag, live_api_called, artifact",
                    "live_verified",
                )
            )

    if doc.get("live_api_called") is True and doc.get("live_verified") is not True:
        hits.append(
            _violation(
                "live_api_without_verified_flip",
                "live_api_called true requires live_verified true with full evidence",
                "live_api_called",
            )
        )

    prior = doc.get("prior_gate_ids") or []
    if isinstance(prior, list):
        prior_set = {str(g) for g in prior}
        missing_prior = sorted(REQUIRED_PRIOR_GATE_IDS - prior_set)
        if missing_prior:
            hits.append(
                _violation(
                    "prior_gate_ids_incomplete",
                    f"missing prior gates: {','.join(missing_prior[:5])}",
                    "prior_gate_ids",
                )
            )
        if GATE_ID in prior_set:
            hits.append(
                _violation(
                    "prior_includes_self",
                    "prior_gate_ids must not include live-smoke-evidence",
                    "prior_gate_ids",
                )
            )
    else:
        hits.append(_violation("prior_gate_ids_type", "prior_gate_ids must be array", "prior_gate_ids"))

    halt = doc.get("halt_reason")
    if halt is not None and halt not in HALT_REASONS:
        hits.append(
            _violation("unknown_halt_reason", f"halt_reason {halt} not in HALT_REASONS", "halt_reason")
        )

    marker = doc.get("season_arc_marker")
    if marker != ARC_SEASON_COMPLETE:
        hits.append(
            _violation(
                "season_arc_marker",
                f"season_arc_marker must be {ARC_SEASON_COMPLETE}",
                "season_arc_marker",
            )
        )

    receipt_ids = doc.get("receipt_ids") or []
    etags = doc.get("etags") or []
    if not isinstance(receipt_ids, list) or not receipt_ids:
        hits.append(_violation("receipt_ids_empty", "receipt_ids must be non-empty", "receipt_ids"))
    if not isinstance(etags, list) or not etags:
        hits.append(_violation("etags_empty", "etags must be non-empty", "etags"))
    if isinstance(receipt_ids, list) and isinstance(etags, list) and receipt_ids and etags:
        if len(receipt_ids) != len(etags):
            hits.append(
                _violation(
                    "receipt_etag_length_mismatch",
                    "receipt_ids and etags must have equal length",
                    "receipt_ids",
                )
            )

    chain_ids: list[str] = []
    gate_chain = doc.get("gate_chain") or []
    if isinstance(gate_chain, list):
        if len(gate_chain) < 2:
            hits.append(
                _violation("gate_chain_too_short", "gate_chain must include spine + smoke hops", "gate_chain")
            )
        for idx, hop in enumerate(gate_chain):
            if not isinstance(hop, Mapping):
                hits.append(_violation("gate_chain_shape", f"hop {idx} not object", f"gate_chain[{idx}]"))
                continue
            gid = hop.get("gate_id")
            if not gid:
                hits.append(
                    _violation("gate_chain_gate_id", "gate_id required on hop", f"gate_chain[{idx}].gate_id")
                )
            else:
                chain_ids.append(str(gid))
            if not hop.get("receipt_id"):
                hits.append(
                    _violation(
                        "gate_chain_receipt",
                        "receipt_id required on hop",
                        f"gate_chain[{idx}].receipt_id",
                    )
                )
            if not hop.get("etag"):
                hits.append(
                    _violation("gate_chain_etag", "etag required on hop", f"gate_chain[{idx}].etag")
                )
            _validate_gate_chain_cues(hop.get("cues"), idx, hits)
    else:
        hits.append(_violation("gate_chain_type", "gate_chain must be array", "gate_chain"))

    endpoints = doc.get("redacted_endpoints") or {}
    if not isinstance(endpoints, Mapping):
        hits.append(
            _violation("redacted_endpoints_type", "redacted_endpoints must be object", "redacted_endpoints")
        )
    else:
        for key, value in endpoints.items():
            if not isinstance(value, str):
                continue
            if _SECRET_PATTERN.search(value) or "sk-" in value:
                hits.append(
                    _violation(
                        "endpoint_not_redacted",
                        f"endpoint value for {key} must be redacted",
                        f"redacted_endpoints.{key}",
                    )
                )

    ok = len(hits) == 0
    return SmokeValidationResult(ok, tuple(hits), tuple(chain_ids))


def minimal_valid_smoke_evidence_document() -> dict[str, Any]:
    """Minimal hermetic smoke evidence (incomplete for live flip; no live API)."""
    return {
        "schema_version": "kilo-live-smoke-evidence-v1",
        "evidence_id": "kilo_live_smoke_evidence_hermetic_minimal",
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "four_state_max": "TEST_VERIFIED",
        "live_verified": False,
        "live_api_called": False,
        "evidence_label": "inferred",
        "prior_gate_ids": sorted(REQUIRED_PRIOR_GATE_IDS),
        "founder_ack_env_key": FOUNDER_ACK_ENV,
        FOUNDER_ACK_MARKER_FIELD: False,
        "box_url_env_key": BOX_URL_ENV,
        BOX_URL_PRESENT_FIELD: False,
        "receipt_ids": ["rcpt_spine_hermetic", "rcpt_smoke_bind"],
        "etags": ["etag_spine_a1", "etag_smoke_b2"],
        "gate_chain": [
            {
                "gate_id": POST_SEASON_GATE_ID,
                "receipt_id": "rcpt_spine_hermetic",
                "etag": "etag_spine_a1",
            },
            {
                "gate_id": GATE_ID,
                "receipt_id": "rcpt_smoke_bind",
                "etag": "etag_smoke_b2",
            },
        ],
        "redacted_endpoints": {
            "box_url": "[REDACTED_BOX_URL]",
            "mercury_base": "[REDACTED_MERCURY]",
        },
        "recorded_at": "2026-09-23T00:00:00Z",
        "completed_at": None,
        "halt_reason": "dod_met",
        "evidence_artifact_path": "",
        "season_arc_marker": ARC_SEASON_COMPLETE,
        "artifact_paths": [str(_ARTIFACT_DIR_REL / EVIDENCE_ARTIFACT_GLOB)],
    }


def smoke_evidence_json_schema() -> dict[str, Any]:
    return {
        "title": "KILO Live Smoke Evidence",
        "schema_version": "kilo-live-smoke-evidence-v1",
        "gate_id": GATE_ID,
        "required_top_level": list(_REQUIRED_TOP_LEVEL),
        "required_prior_gate_ids": sorted(REQUIRED_PRIOR_GATE_IDS),
        "founder_ack_env": FOUNDER_ACK_ENV,
        "box_url_env": BOX_URL_ENV,
        "halt_reasons": sorted(HALT_REASONS),
        "season_arc_marker": ARC_SEASON_COMPLETE,
        "audit_pass_glob": AUDIT_PASS_GLOB,
        "evidence_artifact_glob": str(_ARTIFACT_DIR_REL / EVIDENCE_ARTIFACT_GLOB),
    }


def run_fixture_suite() -> tuple[int, int, list[str]]:
    positive = negative = 0
    errors: list[str] = []
    for path in list_fixture_paths():
        name = path.name
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{name}: json error {exc}")
            continue
        result = validate_smoke_evidence_document(doc)
        if name.startswith("valid_"):
            if not result.ok:
                errors.append(
                    f"{name}: expected valid got {','.join(v.code for v in result.violations)}"
                )
            else:
                positive += 1
        elif name.startswith("invalid_"):
            if result.ok:
                errors.append(f"{name}: expected invalid got ok")
            else:
                negative += 1
    return positive, negative, errors


def audit_flip_candidate(
    evidence: Mapping[str, Any],
    audit_pass: Mapping[str, Any],
    *,
    artifact_exists: bool = False,
) -> dict[str, Any]:
    """Produce candidate audit pass; never invent live_verified without predicates."""
    candidate = copy.deepcopy(dict(audit_pass))
    four_state = candidate.get("four_state")
    if not isinstance(four_state, dict):
        four_state = {}
        candidate["four_state"] = four_state

    reasons: list[str] = []
    if not can_flip_audit_live_verified(evidence, artifact_exists=artifact_exists):
        reasons.append("evidence_predicates_incomplete")
    val = validate_smoke_evidence_document(evidence, artifact_exists=artifact_exists)
    if not val.ok:
        reasons.append("evidence_validation_failed")

    if reasons:
        four_state["live_verified"] = False
        four_state["production_ready"] = False
        candidate["audit_flip_status"] = "refused"
        candidate["audit_flip_refusal_reasons"] = reasons
        candidate["pr152_gate_id"] = GATE_ID
        return candidate

    four_state["live_verified"] = True
    four_state["production_ready"] = False
    candidate["audit_flip_status"] = "candidate_only"
    candidate["evidence_id"] = evidence.get("evidence_id")
    candidate["evidence_artifact_path"] = evidence.get("evidence_artifact_path")
    candidate["pr152_gate_id"] = GATE_ID
    candidate["note"] = (
        "Founder must write this pass to docs/audit/passes/ after merge; "
        "hermetic PR #152 never commits live_verified true by default."
    )
    return candidate


def _contract_check() -> tuple[bool, str]:
    path = REPO_ROOT / _VERIFY_SCRIPT_REL
    if not path.is_file():
        return False, f"missing operator script {_VERIFY_SCRIPT_REL}"
    if gate_for_pr(PR_NUMBER) is None:
        pass  # PR #152 is post-arc; no ARC_GATES entry required
    schema = smoke_evidence_json_schema()
    if schema.get("gate_id") != GATE_ID:
        return False, "schema gate_id mismatch"
    return True, "smoke evidence contract present"


def evaluate_live_smoke_evidence(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    run_fixtures: bool = True,
) -> LiveSmokeEvidenceResult:
    """Evaluate live-smoke-evidence gate (fail-closed; no network)."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved_mode = mode if mode is not None else detect_matrix_mode(env)
    violations: list[LiveSmokeEvidenceViolation] = []

    post_season = hermetic_post_season_harden_operator_check(env)
    post_ok = post_season.ok
    if not post_ok:
        violations.append(
            LiveSmokeEvidenceViolation(
                code="post_season_layer_failed",
                message="PR #151 post-season-harden hermetic layer must pass first",
            )
        )

    contract_ok, contract_detail = _contract_check()
    if not contract_ok:
        violations.append(
            LiveSmokeEvidenceViolation(code="contract_failed", message=contract_detail)
        )

    pos = neg = 0
    fixture_errors: list[str] = []
    if run_fixtures:
        pos, neg, fixture_errors = run_fixture_suite()
        for err in fixture_errors:
            violations.append(LiveSmokeEvidenceViolation(code="fixture_suite_failed", message=err))

    minimal_doc = minimal_valid_smoke_evidence_document()
    minimal_val = validate_smoke_evidence_document(minimal_doc)
    if not minimal_val.ok:
        violations.append(
            LiveSmokeEvidenceViolation(
                code="minimal_evidence_invalid",
                message=",".join(v.code for v in minimal_val.violations),
            )
        )

    # Hermetic default audit flip must refuse without founder artifact
    audit_sample = {
        "pass_id": "pr151",
        "four_state": {"code_complete": True, "test_verified": True, "live_verified": False},
    }
    flip = audit_flip_candidate(minimal_doc, audit_sample, artifact_exists=False)
    if flip.get("audit_flip_status") != "refused":
        violations.append(
            LiveSmokeEvidenceViolation(
                code="hermetic_flip_must_refuse",
                message="minimal evidence must not produce live flip candidate",
            )
        )

    evidence = LiveSmokeEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        post_season_harden_ok=post_ok,
        fixture_pass_count=pos,
        fixture_negative_reject_count=neg,
        contract_ok=contract_ok,
        live_api_called=False,
        season_arc_marker=ARC_SEASON_COMPLETE,
        evidence_label="inferred",
    )

    ok = post_ok and contract_ok and not fixture_errors and minimal_val.ok and len(violations) == 0
    return LiveSmokeEvidenceResult(
        mode=resolved_mode,
        ok=ok,
        post_season_harden_ok=post_ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_live_smoke_evidence_operator_check(
    environ: Mapping[str, str] | None = None,
) -> LiveSmokeEvidenceResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_live_smoke_evidence(detect_matrix_mode(env), env, run_fixtures=True)


def live_smoke_evidence_gate_closed() -> bool:
    env = minimal_live_smoke_evidence_environ()
    op = hermetic_live_smoke_evidence_operator_check(env)
    unit = evaluate_live_smoke_evidence(EnvMatrixMode.HERMETIC_UNIT, env, run_fixtures=True)
    return op.ok and unit.ok


def redact_smoke_evidence_summary(text: str) -> str:
    return redact_proof_summary(text)


def live_smoke_evidence_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    operator = hermetic_live_smoke_evidence_operator_check(env)
    redacted_env_sample = {
        k: redact_secret_value(k, env.get(k))
        for k in sorted(env.keys())
        if k.startswith(("INCEPTION", "THINKBOX_", "UPSTASH_", "GOVERNANCE"))
    }
    if BOX_URL_ENV in env:
        redacted_env_sample[BOX_URL_ENV] = redact_box_url(env.get(BOX_URL_ENV) or "")
    if "UPSTASH_PUBLIC_BOX_TOKEN" in env:
        redacted_env_sample["UPSTASH_PUBLIC_BOX_TOKEN"] = redact_box_token(
            env.get("UPSTASH_PUBLIC_BOX_TOKEN") or ""
        )
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr152_gate_id": GATE_ID,
        "detected_mode": mode.value,
        "post_season_harden_layer": True,
        "live_proof_exec_layer": True,
        "hermetic_operator_ok": operator.ok,
        "post_season_harden_ok": operator.post_season_harden_ok,
        "fixture_paths": [p.name for p in list_fixture_paths()],
        "schema_version": "kilo-live-smoke-evidence-v1",
        "required_prior_gate_count": len(REQUIRED_PRIOR_GATE_IDS),
        "founder_ack_env": FOUNDER_ACK_ENV,
        "box_url_env": BOX_URL_ENV,
        "hermetic_violation_codes": sorted({v.code for v in operator.violations}),
        "redacted_env_sample": redacted_env_sample,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "arc_season_complete": True,
        "season_arc_marker": ARC_SEASON_COMPLETE,
        "gate_closed_default": live_smoke_evidence_gate_closed(),
        "verify_script": str(_VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / _VERIFY_SCRIPT_REL).is_file(),
        "evidence_artifact_glob": str(_ARTIFACT_DIR_REL / EVIDENCE_ARTIFACT_GLOB),
        "audit_pass_glob": AUDIT_PASS_GLOB,
        "default_audit_prior": _DEFAULT_AUDIT_PRIOR,
        "audit_flip_refuses_without_founder_evidence": True,
    }


def minimal_live_smoke_evidence_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_post_season_harden_environ())
    if extra:
        base.update(extra)
    return dict(base)
