"""Hermetic KILO Live-proof execution plan contracts (PR #150, ``live-proof-exec``).

Season-closer for arc #141–#150. Layers on PR #149 ``dashboard-slots``. Defines a
fail-closed **execution plan** for a future bounded Live proof — not Live proof itself.
Default path: no network; ``live_api_called=False``. Founder ack ``THINKBOX_SWARM_LIVE_ACK``
and public Box URL ``UPSTASH_PUBLIC_BOX_URL`` are required only for optional live prep paths;
hermetic operator verify stays closed without them.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from thinkbox.kilo_dashboard_slots import (
    DashboardSlotsResult,
    hermetic_dashboard_slots_operator_check,
    minimal_dashboard_slots_environ,
    redact_dashboard_slots_summary,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_governance_evidence import redact_secret_value
from thinkbox.kilo_live_proof_readiness import REPO_ROOT, gate_for_pr, gate_ids
from thinkbox.kilo_proof_schema import HALT_REASONS, redact_proof_summary
from thinkbox.kilo_substrate_checklist import (
    BOX_URL_ENV,
    redact_box_token,
    redact_box_url,
)

__all__ = (
    "ARC_SEASON_COMPLETE",
    "CLOUD_BOT_STANDBY_AFTER_MERGE",
    "FOUNDER_ACK_ENV",
    "GATE_ID",
    "PR_NUMBER",
    "REQUIRED_PRIOR_GATE_IDS",
    "LiveProofExecEvidence",
    "LiveProofExecMode",
    "LiveProofExecResult",
    "LiveProofExecViolation",
    "audit_flip_procedure",
    "bounded_smoke_steps",
    "can_claim_live_verified",
    "default_artifact_glob",
    "evaluate_live_proof_exec",
    "execution_plan_json_schema",
    "fixtures_dir",
    "hermetic_live_proof_exec_operator_check",
    "list_fixture_paths",
    "live_exec_env_ready",
    "live_proof_exec_contract_summary",
    "live_proof_exec_gate_closed",
    "load_fixture",
    "minimal_live_proof_exec_environ",
    "minimal_valid_execution_plan_document",
    "redact_live_proof_exec_summary",
    "run_fixture_suite",
    "validate_execution_plan_document",
)

GATE_ID = "live-proof-exec"
PR_NUMBER = 150
FOUNDER_ACK_ENV = "THINKBOX_SWARM_LIVE_ACK"

ARC_SEASON_COMPLETE = "kilo-live-proof-arc-141-150-season-closed"
CLOUD_BOT_STANDBY_AFTER_MERGE = (
    "After PR #150 merge: Cloud Bot on standby — no #151 unless founder asks."
)

_FIXTURES_REL = Path("data/kilo_live_proof_exec/fixtures")
_VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_live_proof_exec.py")
_ARTIFACT_DIR_REL = Path("data/thinkboxmd/artifacts")
_ARTIFACT_GLOB = "kilo_live_proof_*.json"
_AUDIT_PASS_GLOB = "docs/audit/passes/*-pr150.json"

_REQUIRED_PRIOR: tuple[str, ...] = tuple(gid for gid in gate_ids() if gid != GATE_ID)
REQUIRED_PRIOR_GATE_IDS: frozenset[str] = frozenset(_REQUIRED_PRIOR)

_SECRET_PATTERN = re.compile(
    r"(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._-]{20,})",
    re.IGNORECASE,
)

_FORBIDDEN_LITERAL_CLAIMS = (
    "KILO LIVE VERIFIED",
    "KILO PRODUCTION READY",
    "KILO live build verified",
)

_REQUIRED_TOP_LEVEL: tuple[str, ...] = (
    "schema_version",
    "plan_id",
    "gate_id",
    "pr_number",
    "four_state_max",
    "live_verified",
    "live_api_called",
    "evidence_label",
    "prior_gate_ids",
    "founder_ack_env_key",
    "box_url_env_key",
    "steps",
    "artifact_paths",
    "halt_reasons_allowed",
    "season_arc_marker",
)


class LiveProofExecMode(str, Enum):
    """Alias of env-matrix modes for live-proof-exec reporting."""

    HERMETIC_UNIT = EnvMatrixMode.HERMETIC_UNIT.value
    HERMETIC_CI = EnvMatrixMode.HERMETIC_CI.value
    LIVE_PROOF_PREP = EnvMatrixMode.LIVE_PROOF_PREP.value


@dataclass(frozen=True)
class LiveProofExecViolation:
    """Single fail-closed live-proof-exec violation."""

    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class PlanValidationResult:
    """Outcome of validating one execution plan JSON document."""

    ok: bool
    violations: tuple[LiveProofExecViolation, ...] = ()
    ordered_step_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "violations": [
                {"code": v.code, "message": v.message, "path": v.path} for v in self.violations
            ],
            "ordered_step_ids": list(self.ordered_step_ids),
        }


@dataclass(frozen=True)
class LiveProofExecEvidence:
    """Redacted evidence for live-proof-exec gate closure (hermetic)."""

    gate_id: str
    pr_number: int
    dashboard_slots_ok: bool
    fixture_pass_count: int
    fixture_negative_reject_count: int
    plan_contract_ok: bool
    live_api_called: bool
    live_exec_env_ready: bool
    season_arc_marker: str
    evidence_label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "pr_number": self.pr_number,
            "dashboard_slots_ok": self.dashboard_slots_ok,
            "fixture_pass_count": self.fixture_pass_count,
            "fixture_negative_reject_count": self.fixture_negative_reject_count,
            "plan_contract_ok": self.plan_contract_ok,
            "live_api_called": self.live_api_called,
            "live_exec_env_ready": self.live_exec_env_ready,
            "season_arc_marker": self.season_arc_marker,
            "evidence_label": self.evidence_label,
            "four_state_max": "TEST_VERIFIED",
            "arc_season_complete_marker": ARC_SEASON_COMPLETE,
        }


@dataclass
class LiveProofExecResult:
    """Outcome of evaluating live-proof-exec for one mode."""

    mode: EnvMatrixMode
    ok: bool
    dashboard_slots_ok: bool
    violations: list[LiveProofExecViolation] = field(default_factory=list)
    evidence: LiveProofExecEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "ok": self.ok,
            "dashboard_slots_ok": self.dashboard_slots_ok,
            "violations": [
                {"code": v.code, "message": v.message, "path": v.path} for v in self.violations
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


def default_artifact_glob() -> str:
    return str(_ARTIFACT_DIR_REL / _ARTIFACT_GLOB)


def bounded_smoke_steps() -> tuple[dict[str, str], ...]:
    """Canonical bounded Live smoke steps (documentation contract; hermetic default)."""
    return (
        {
            "step_id": "spine-verify",
            "action": "python3 scripts/verify_kilo_spine.py",
            "network": "none",
        },
        {
            "step_id": "live-proof-exec-verify",
            "action": "python3 scripts/verify_kilo_live_proof_exec.py",
            "network": "none",
        },
        {
            "step_id": "substrate-shape",
            "action": "confirm UPSTASH_PUBLIC_BOX_URL host *.box.upstash.com",
            "network": "none",
        },
        {
            "step_id": "founder-ack",
            "action": f"export {FOUNDER_ACK_ENV}=1 (founder only)",
            "network": "none",
        },
        {
            "step_id": "bounded-mercury-smoke",
            "action": "single bounded call via governed path (founder-run only)",
            "network": "live_optional",
        },
        {
            "step_id": "write-artifact",
            "action": f"write {default_artifact_glob()}",
            "network": "none",
        },
        {
            "step_id": "audit-flip",
            "action": "docs/audit/passes/*-pr150-live.json with live_verified true",
            "network": "none",
        },
    )


def audit_flip_procedure() -> tuple[str, ...]:
    """Steps to flip audit live_verified only after physical evidence exists."""
    return (
        "Run bounded smoke with founder ack + Box URL; capture artifact SHA256.",
        f"Write proof JSON under {_ARTIFACT_DIR_REL}/ matching proof-schema.",
        "Add audit pass under docs/audit/passes/ with live_verified: true only for KILO scope.",
        "Reference artifact path + hash in docs/CONTINUITY.md.",
        "Never set live_verified in hermetic PR #150 branch without those artifacts.",
    )


def _violation(code: str, message: str, path: str | None = None) -> LiveProofExecViolation:
    return LiveProofExecViolation(code=code, message=message, path=path)


def _scan_redaction(text: str, path: str, hits: list[LiveProofExecViolation]) -> None:
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


def _founder_ack_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "accept")


def live_exec_env_ready(environ: Mapping[str, str]) -> bool:
    """True when founder ack and public Box URL are both present (live prep only)."""
    ack = _founder_ack_truthy(environ.get(FOUNDER_ACK_ENV))
    url = (environ.get(BOX_URL_ENV) or "").strip()
    return ack and bool(url) and ".box.upstash.com" in url


def can_claim_live_verified(
    doc: Mapping[str, Any],
    *,
    evidence_artifact_path: str | None = None,
    artifact_exists: bool = False,
) -> bool:
    """Four-state rule: LIVE VERIFIED requires recorded evidence artifact on disk."""
    if doc.get("live_verified") is not True:
        return False
    path = evidence_artifact_path or str(doc.get("evidence_artifact_path") or "")
    if not path.strip():
        return False
    if artifact_exists:
        return True
    resolved = REPO_ROOT / path
    return resolved.is_file()


def validate_execution_plan_document(doc: Mapping[str, Any]) -> PlanValidationResult:
    """Fail-closed validator for KILO live-proof execution plan JSON."""
    hits: list[LiveProofExecViolation] = []
    serialized = json.dumps(doc, sort_keys=True)
    _scan_redaction(serialized, "$", hits)

    if not isinstance(doc, Mapping):
        return PlanValidationResult(False, tuple(hits))

    for key in _REQUIRED_TOP_LEVEL:
        if key not in doc:
            hits.append(_violation("missing_required", f"missing {key}", key))

    if doc.get("schema_version") != "kilo-live-proof-exec-v1":
        hits.append(
            _violation(
                "schema_version", "schema_version must be kilo-live-proof-exec-v1", "schema_version"
            )
        )

    if doc.get("gate_id") != GATE_ID:
        hits.append(_violation("gate_id_mismatch", f"gate_id must be {GATE_ID}", "gate_id"))

    pr = doc.get("pr_number")
    if pr != PR_NUMBER:
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
            _violation(
                "box_url_env_key", f"box_url_env_key must be {BOX_URL_ENV}", "box_url_env_key"
            )
        )

    if doc.get("live_api_called") is True:
        hits.append(
            _violation(
                "live_api_forbidden",
                "live_api_called must be false in hermetic plans",
                "live_api_called",
            )
        )

    four_state = doc.get("four_state_max")
    if four_state not in ("TEST_VERIFIED", "CODE_COMPLETE"):
        if four_state in ("LIVE_VERIFIED", "PRODUCTION_READY"):
            hits.append(
                _violation(
                    "four_state_cap_exceeded",
                    "hermetic plan four_state_max must not claim LIVE/PRODUCTION",
                    "four_state_max",
                )
            )

    if doc.get("live_verified") is True:
        hits.append(
            _violation(
                "live_verified_forbidden",
                "live_verified true forbidden without founder-run evidence artifact",
                "live_verified",
            )
        )
        if not can_claim_live_verified(doc, artifact_exists=False):
            hits.append(
                _violation(
                    "live_verified_without_evidence",
                    "live_verified requires evidence_artifact_path file on disk",
                    "live_verified",
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
        for idx, gid in enumerate(prior):
            if gid not in gate_ids():
                hits.append(
                    _violation(
                        "unknown_prior_gate", f"unknown gate {gid}", f"prior_gate_ids[{idx}]"
                    )
                )
        if GATE_ID in prior_set:
            hits.append(
                _violation(
                    "prior_includes_self",
                    "prior_gate_ids must not include live-proof-exec",
                    "prior_gate_ids",
                )
            )
    else:
        hits.append(
            _violation("prior_gate_ids_type", "prior_gate_ids must be array", "prior_gate_ids")
        )

    halt_allowed = doc.get("halt_reasons_allowed") or []
    if isinstance(halt_allowed, list):
        for idx, reason in enumerate(halt_allowed):
            if reason not in HALT_REASONS:
                hits.append(
                    _violation(
                        "unknown_halt_reason",
                        f"halt reason {reason} not in proof-schema HALT_REASONS",
                        f"halt_reasons_allowed[{idx}]",
                    )
                )
    else:
        hits.append(
            _violation(
                "halt_reasons_type", "halt_reasons_allowed must be array", "halt_reasons_allowed"
            )
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

    steps = doc.get("steps") or []
    ordered: list[str] = []
    if isinstance(steps, list):
        if len(steps) < 3:
            hits.append(
                _violation("steps_too_few", "steps must include bounded smoke chain", "steps")
            )
        for idx, step in enumerate(steps):
            if not isinstance(step, Mapping):
                hits.append(_violation("step_shape", f"step {idx} not object", f"steps[{idx}]"))
                continue
            sid = step.get("step_id")
            if not sid:
                hits.append(
                    _violation("step_id_missing", "step_id required", f"steps[{idx}].step_id")
                )
            else:
                ordered.append(str(sid))
            net = step.get("network")
            if net == "live" and doc.get("live_api_called") is not True:
                hits.append(
                    _violation(
                        "step_live_network_mismatch",
                        "live network step requires documented founder-run (not hermetic plan)",
                        f"steps[{idx}].network",
                    )
                )
    else:
        hits.append(_violation("steps_type", "steps must be array", "steps"))

    artifacts = doc.get("artifact_paths") or []
    if not isinstance(artifacts, list) or not artifacts:
        hits.append(
            _violation("artifact_paths_empty", "artifact_paths must be non-empty", "artifact_paths")
        )
    else:
        for idx, ap in enumerate(artifacts):
            if not isinstance(ap, str) or not ap.startswith("data/thinkboxmd/"):
                hits.append(
                    _violation(
                        "artifact_path_invalid",
                        "artifact paths must live under data/thinkboxmd/",
                        f"artifact_paths[{idx}]",
                    )
                )

    ok = len(hits) == 0
    return PlanValidationResult(ok, tuple(hits), tuple(ordered))


def minimal_valid_execution_plan_document() -> dict[str, Any]:
    """Minimal hermetic execution plan (no live_verified, no live API)."""
    steps = [
        {"step_id": s["step_id"], "action": s["action"], "network": s["network"]}
        for s in bounded_smoke_steps()
    ]
    return {
        "schema_version": "kilo-live-proof-exec-v1",
        "plan_id": "kilo_live_proof_exec_plan_hermetic_minimal",
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "four_state_max": "TEST_VERIFIED",
        "live_verified": False,
        "live_api_called": False,
        "evidence_label": "inferred",
        "prior_gate_ids": list(_REQUIRED_PRIOR),
        "founder_ack_env_key": FOUNDER_ACK_ENV,
        "box_url_env_key": BOX_URL_ENV,
        "steps": steps,
        "artifact_paths": [default_artifact_glob()],
        "evidence_artifact_path": "",
        "halt_reasons_allowed": sorted(HALT_REASONS),
        "season_arc_marker": ARC_SEASON_COMPLETE,
        "cloud_bot_standby_note": CLOUD_BOT_STANDBY_AFTER_MERGE,
    }


def execution_plan_json_schema() -> dict[str, Any]:
    return {
        "title": "KILO Live Proof Execution Plan",
        "schema_version": "kilo-live-proof-exec-v1",
        "gate_id": GATE_ID,
        "required_top_level": list(_REQUIRED_TOP_LEVEL),
        "required_prior_gate_ids": sorted(REQUIRED_PRIOR_GATE_IDS),
        "founder_ack_env": FOUNDER_ACK_ENV,
        "box_url_env": BOX_URL_ENV,
        "halt_reasons": sorted(HALT_REASONS),
        "season_arc_marker": ARC_SEASON_COMPLETE,
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
        result = validate_execution_plan_document(doc)
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


def _plan_contract_check() -> tuple[bool, str]:
    path = REPO_ROOT / _VERIFY_SCRIPT_REL
    if not path.is_file():
        return False, f"missing operator script {_VERIFY_SCRIPT_REL}"
    gate = gate_for_pr(PR_NUMBER)
    if gate is None or gate.gate_id != GATE_ID:
        return False, "arc gate missing for PR 150"
    schema = execution_plan_json_schema()
    if schema.get("gate_id") != GATE_ID:
        return False, "schema gate_id mismatch"
    return True, "execution plan contract present"


def evaluate_live_proof_exec(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    run_fixtures: bool = True,
) -> LiveProofExecResult:
    """Evaluate live-proof-exec gate (fail-closed; no network)."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved_mode = mode if mode is not None else detect_matrix_mode(env)
    violations: list[LiveProofExecViolation] = []

    slots: DashboardSlotsResult = hermetic_dashboard_slots_operator_check(env)
    if not slots.ok:
        for v in slots.violations:
            violations.append(
                LiveProofExecViolation(
                    code=f"dashboard_{v.code}",
                    message=v.message,
                    path=v.path,
                )
            )

    contract_ok, contract_detail = _plan_contract_check()
    if not contract_ok:
        violations.append(
            LiveProofExecViolation(code="plan_contract_failed", message=contract_detail)
        )

    pos = neg = 0
    fixture_errors: list[str] = []
    if run_fixtures:
        pos, neg, fixture_errors = run_fixture_suite()
        for err in fixture_errors:
            violations.append(LiveProofExecViolation(code="fixture_suite_failed", message=err))

    minimal_doc = minimal_valid_execution_plan_document()
    minimal_val = validate_execution_plan_document(minimal_doc)
    if not minimal_val.ok:
        violations.append(
            LiveProofExecViolation(
                code="minimal_plan_invalid",
                message=",".join(v.code for v in minimal_val.violations),
            )
        )

    if resolved_mode in (EnvMatrixMode.HERMETIC_UNIT, EnvMatrixMode.HERMETIC_CI):
        if live_exec_env_ready(env):
            violations.append(
                LiveProofExecViolation(
                    code="live_env_in_hermetic_mode",
                    message="founder ack + Box URL must not satisfy live prep in hermetic modes",
                )
            )

    exec_ready = live_exec_env_ready(env)

    evidence = LiveProofExecEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        dashboard_slots_ok=slots.ok,
        fixture_pass_count=pos,
        fixture_negative_reject_count=neg,
        plan_contract_ok=contract_ok,
        live_api_called=False,
        live_exec_env_ready=exec_ready,
        season_arc_marker=ARC_SEASON_COMPLETE,
        evidence_label="inferred",
    )

    ok = slots.ok and contract_ok and not fixture_errors and minimal_val.ok and len(violations) == 0
    return LiveProofExecResult(
        mode=resolved_mode,
        ok=ok,
        dashboard_slots_ok=slots.ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_live_proof_exec_operator_check(
    environ: Mapping[str, str] | None = None,
) -> LiveProofExecResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_live_proof_exec(detect_matrix_mode(env), env, run_fixtures=True)


def live_proof_exec_gate_closed() -> bool:
    gate = gate_for_pr(PR_NUMBER)
    if gate is None or gate.gate_id != GATE_ID:
        return False
    env = minimal_live_proof_exec_environ()
    op = hermetic_live_proof_exec_operator_check(env)
    unit = evaluate_live_proof_exec(EnvMatrixMode.HERMETIC_UNIT, env, run_fixtures=True)
    return op.ok and unit.ok


def redact_live_proof_exec_summary(text: str) -> str:
    return redact_proof_summary(redact_dashboard_slots_summary(text))


def live_proof_exec_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    operator = hermetic_live_proof_exec_operator_check(env)
    gate = gate_for_pr(PR_NUMBER)
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
        "detected_mode": mode.value,
        "dashboard_slots_layer": True,
        "hermetic_operator_ok": operator.ok,
        "dashboard_slots_ok": operator.dashboard_slots_ok,
        "fixture_paths": [p.name for p in list_fixture_paths()],
        "schema_version": "kilo-live-proof-exec-v1",
        "bounded_smoke_step_ids": [s["step_id"] for s in bounded_smoke_steps()],
        "required_prior_gate_count": len(REQUIRED_PRIOR_GATE_IDS),
        "founder_ack_env": FOUNDER_ACK_ENV,
        "box_url_env": BOX_URL_ENV,
        "live_exec_env_ready": live_exec_env_ready(env),
        "hermetic_violation_codes": sorted({v.code for v in operator.violations}),
        "redacted_env_sample": redacted_env_sample,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "arc_season_complete": True,
        "season_arc_marker": ARC_SEASON_COMPLETE,
        "cloud_bot_standby_note": CLOUD_BOT_STANDBY_AFTER_MERGE,
        "arc_gate_theme": gate.theme if gate else None,
        "gate_closed_default": live_proof_exec_gate_closed(),
        "verify_script": str(_VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / _VERIFY_SCRIPT_REL).is_file(),
        "default_artifact_glob": default_artifact_glob(),
        "audit_flip_steps": list(audit_flip_procedure()),
    }


def minimal_live_proof_exec_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_dashboard_slots_environ())
    if extra:
        base.update(extra)
    return dict(base)
