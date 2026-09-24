"""Hermetic KILO dashboard / control-plane slot bindings (PR #149, ``dashboard-slots``).

Layers on PR #148 ``proof-schema``. Slots are hermetic placeholders for future Live-proof
UI surfaces — not live HTTP dashboard calls. Binds receipt keys and etags to slot ids,
multiplex-safe digest identity (aligned with Think Job #139–#140), fail-closed when
unbound or stale, and proof-schema cross-fields (``depends_on``, ``prior_gate_ids``, cues).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_governance_evidence import redact_secret_value
from thinkbox.kilo_live_proof_readiness import REPO_ROOT, gate_for_pr, gate_ids
from thinkbox.kilo_proof_schema import (
    CUE_TYPES,
    INJECTED_CUE_TYPES,
    ProofSchemaResult,
    detect_dependency_cycle,
    hermetic_proof_schema_operator_check,
    minimal_proof_schema_environ,
    redact_proof_summary,
    topological_gate_order,
    validate_proof_document,
)
from thinkbox.kilo_substrate_checklist import redact_box_token, redact_box_url
from thinkbox.think_job_status_ui import normalize_receipt_key

__all__ = (
    "GATE_ID",
    "PR_NUMBER",
    "SLOT_KINDS",
    "OccupancyState",
    "SharePolicy",
    "SlotKind",
    "DashboardSlotsEvidence",
    "DashboardSlotsResult",
    "DashboardSlotsViolation",
    "DashboardSlotsMode",
    "build_multiplex_digest_identity",
    "dashboard_slots_contract_summary",
    "dashboard_slots_gate_closed",
    "detect_slot_dependency_cycle",
    "evaluate_dashboard_slots",
    "fixtures_dir",
    "hermetic_dashboard_slots_operator_check",
    "list_fixture_paths",
    "load_fixture",
    "minimal_dashboard_slots_environ",
    "minimal_valid_slot_registry_document",
    "redact_dashboard_slots_summary",
    "run_fixture_suite",
    "slot_registry_json_schema",
    "validate_slot_registry_document",
)

GATE_ID = "dashboard-slots"
PR_NUMBER = 149

_FIXTURES_REL = Path("data/kilo_dashboard_slots/fixtures")
_VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_dashboard_slots.py")

_FORBIDDEN_LITERAL_CLAIMS = (
    "KILO LIVE VERIFIED",
    "KILO PRODUCTION READY",
    "KILO live build verified",
)

_SECRET_PATTERN = re.compile(
    r"(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._-]{20,})",
    re.IGNORECASE,
)


class SlotKind(str, Enum):
    """Hermetic dashboard slot kinds (no live HTTP in this gate)."""

    PROOF_RECEIPT = "proof_receipt"
    GATE_STATUS = "gate_status"
    SWARM_DIGEST = "swarm_digest"
    GOVERNANCE_EVIDENCE = "governance_evidence"
    MERCURY_HERMETIC = "mercury_hermetic"
    CUE_INBOX = "cue_inbox"
    DOD_CHECKLIST = "dod_checklist"
    RECEIPT_CHAIN_END_LINK = "receipt_chain_end_link"


SLOT_KINDS: frozenset[str] = frozenset(m.value for m in SlotKind)


class OccupancyState(str, Enum):
    """Whether a slot is ready to render hermetic UI state."""

    UNBOUND = "unbound"
    BOUND = "bound"
    STALE = "stale"
    MULTIPLEX_CONFLICT = "multiplex_conflict"


class SharePolicy(str, Enum):
    """How receipt keys may bind across exclusive slots."""

    EXCLUSIVE = "exclusive"
    SHARED_EXPLICIT = "shared_explicit"


class DashboardSlotsMode(str, Enum):
    """Alias of env-matrix modes for dashboard-slots reporting."""

    HERMETIC_UNIT = EnvMatrixMode.HERMETIC_UNIT.value
    HERMETIC_CI = EnvMatrixMode.HERMETIC_CI.value
    LIVE_PROOF_PREP = EnvMatrixMode.LIVE_PROOF_PREP.value


@dataclass(frozen=True)
class DashboardSlotsViolation:
    """Single fail-closed dashboard-slots violation."""

    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class SlotValidationResult:
    """Outcome of validating one slot registry document."""

    ok: bool
    violations: tuple[DashboardSlotsViolation, ...] = ()
    ordered_slot_ids: tuple[str, ...] = ()
    occupancy: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "violations": [
                {"code": v.code, "message": v.message, "path": v.path} for v in self.violations
            ],
            "ordered_slot_ids": list(self.ordered_slot_ids),
            "occupancy": dict(self.occupancy),
        }


@dataclass(frozen=True)
class DashboardSlotsEvidence:
    """Hermetic evidence bundle for dashboard-slots gate."""

    gate_id: str
    pr_number: int
    proof_schema_ok: bool
    proof_schema_gate_id: str
    fixture_pass_count: int
    fixture_negative_reject_count: int
    registry_contract_ok: bool
    live_api_called: bool
    evidence_label: str


@dataclass(frozen=True)
class DashboardSlotsResult:
    """Full dashboard-slots evaluation outcome."""

    mode: EnvMatrixMode
    ok: bool
    proof_schema_ok: bool
    violations: tuple[DashboardSlotsViolation, ...] = ()
    evidence: DashboardSlotsEvidence | None = None


def fixtures_dir() -> Path:
    return REPO_ROOT / _FIXTURES_REL


def list_fixture_paths() -> list[Path]:
    root = fixtures_dir()
    if not root.is_dir():
        return []
    return sorted(p for p in root.glob("*.json") if p.is_file())


def load_fixture(name: str) -> dict[str, Any]:
    path = fixtures_dir() / name
    return json.loads(path.read_text(encoding="utf-8"))


def build_multiplex_digest_identity(
    receipt_key: str,
    etag: str,
    *,
    dashboard_revision: int = 0,
) -> str:
    """Stable multiplex digest id — same receipt+etag must not fork exclusive slots."""
    rk = normalize_receipt_key(receipt_key)
    et = (etag or "").strip()
    if not et:
        raise ValueError("etag_required")
    payload = json.dumps(
        {
            "receipt_key": rk,
            "etag": et,
            "dashboard_revision": int(dashboard_revision),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def _normalize_slot_id(raw: str) -> str:
    sid = (raw or "").strip()
    if not sid:
        raise ValueError("slot_id_required")
    if len(sid) > 128:
        raise ValueError("slot_id_too_long")
    if not re.match(r"^[a-z][a-z0-9_-]{0,127}$", sid):
        raise ValueError("slot_id_invalid")
    return sid


def _slot_nodes_from_doc(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    slots = doc.get("slots")
    if not isinstance(slots, list):
        return []
    return [s for s in slots if isinstance(s, dict)]


def detect_slot_dependency_cycle(slots: Sequence[Mapping[str, Any]]) -> bool:
    """True when slot ``depends_on`` (by slot_id) contains a cycle."""
    nodes: list[dict[str, Any]] = []
    for slot in slots:
        sid = str(slot.get("slot_id") or "")
        deps = slot.get("depends_on")
        dep_list = deps if isinstance(deps, list) else []
        nodes.append({"node_id": sid, "depends_on": [str(d) for d in dep_list]})
    return detect_dependency_cycle(nodes)


def _forbidden_live_dashboard_claim(text: str) -> bool:
    lowered = text.lower()
    if "live_verified" in lowered and "true" in lowered:
        return True
    for lit in _FORBIDDEN_LITERAL_CLAIMS:
        if lit in text:
            return True
    return False


def validate_slot_registry_document(
    doc: Mapping[str, Any],
    *,
    proof_document: Mapping[str, Any] | None = None,
) -> SlotValidationResult:
    """Validate hermetic slot registry; optional proof doc cross-check."""
    violations: list[DashboardSlotsViolation] = []
    occupancy: dict[str, str] = {}

    required_top = (
        "schema_version",
        "registry_id",
        "gate_id",
        "pr_number",
        "four_state_max",
        "live_verified",
        "live_api_called",
        "evidence_label",
        "slots",
    )
    for key in required_top:
        if key not in doc:
            violations.append(
                DashboardSlotsViolation(code="missing_required", message=f"missing {key}", path=key)
            )

    if doc.get("gate_id") != GATE_ID:
        violations.append(
            DashboardSlotsViolation(
                code="gate_id_mismatch",
                message="registry gate_id must be dashboard-slots",
                path="gate_id",
            )
        )

    if doc.get("live_api_called") is True:
        violations.append(
            DashboardSlotsViolation(
                code="live_api_forbidden",
                message="live_api_called must be false in hermetic gate",
                path="live_api_called",
            )
        )

    if doc.get("live_verified") is True:
        violations.append(
            DashboardSlotsViolation(
                code="live_verified_forbidden",
                message="dashboard slots cannot claim live_verified",
                path="live_verified",
            )
        )

    four_max = str(doc.get("four_state_max") or "")
    if four_max not in ("CODE_COMPLETE", "TEST_VERIFIED"):
        violations.append(
            DashboardSlotsViolation(
                code="four_state_cap",
                message="four_state_max must cap at TEST_VERIFIED for this gate",
                path="four_state_max",
            )
        )

    dumped = json.dumps(doc)
    if _SECRET_PATTERN.search(dumped):
        violations.append(
            DashboardSlotsViolation(
                code="secret_like_literal", message="secret pattern in document"
            )
        )

    slot_nodes = _slot_nodes_from_doc(doc)
    if not slot_nodes:
        violations.append(
            DashboardSlotsViolation(code="slots_empty", message="slots list required", path="slots")
        )

    seen_ids: set[str] = set()
    receipt_exclusive: dict[str, str] = {}
    ordered_ids: list[str] = []

    for idx, slot in enumerate(slot_nodes):
        path = f"slots[{idx}]"
        try:
            sid = _normalize_slot_id(str(slot.get("slot_id") or ""))
        except ValueError as exc:
            violations.append(
                DashboardSlotsViolation(code="slot_id_invalid", message=str(exc), path=path)
            )
            continue

        if sid in seen_ids:
            violations.append(
                DashboardSlotsViolation(code="duplicate_slot_id", message=sid, path=path)
            )
        seen_ids.add(sid)
        ordered_ids.append(sid)

        kind = str(slot.get("kind") or "")
        if kind not in SLOT_KINDS:
            violations.append(
                DashboardSlotsViolation(code="unknown_slot_kind", message=kind, path=f"{path}.kind")
            )

        share = str(slot.get("share_policy") or SharePolicy.EXCLUSIVE.value)
        if share not in (SharePolicy.EXCLUSIVE.value, SharePolicy.SHARED_EXPLICIT.value):
            violations.append(
                DashboardSlotsViolation(
                    code="invalid_share_policy",
                    message=share,
                    path=f"{path}.share_policy",
                )
            )

        bind = slot.get("bind")
        if not isinstance(bind, dict):
            violations.append(
                DashboardSlotsViolation(
                    code="bind_missing", message="bind object required", path=path
                )
            )
            occupancy[sid] = OccupancyState.UNBOUND.value
            continue

        receipt_raw = str(bind.get("receipt_key") or "")
        etag = str(bind.get("etag") or "").strip()
        try:
            rk = normalize_receipt_key(receipt_raw) if receipt_raw else ""
        except ValueError as exc:
            violations.append(
                DashboardSlotsViolation(code="receipt_key_invalid", message=str(exc), path=path)
            )
            rk = ""

        if not rk or not etag:
            violations.append(
                DashboardSlotsViolation(
                    code="slot_unbound",
                    message="receipt_key and etag required for bound slot",
                    path=path,
                )
            )
            occupancy[sid] = OccupancyState.UNBOUND.value
            continue

        digest_id = str(bind.get("multiplex_digest_id") or "")
        try:
            expected_digest = build_multiplex_digest_identity(
                rk,
                etag,
                dashboard_revision=int(bind.get("dashboard_revision") or 0),
            )
        except ValueError as exc:
            violations.append(
                DashboardSlotsViolation(code="digest_identity_invalid", message=str(exc), path=path)
            )
            expected_digest = ""

        if digest_id and digest_id != expected_digest:
            violations.append(
                DashboardSlotsViolation(
                    code="multiplex_digest_mismatch",
                    message="multiplex_digest_id does not match receipt+etag",
                    path=path,
                )
            )

        stale_after = bind.get("stale_after_etag")
        is_stale = stale_after is not None and str(stale_after).strip() == etag
        if is_stale:
            violations.append(
                DashboardSlotsViolation(
                    code="etag_stale",
                    message="etag matches stale_after_etag",
                    path=f"{path}.bind",
                )
            )
            occupancy[sid] = OccupancyState.STALE.value
        elif rk and etag:
            occupancy[sid] = OccupancyState.BOUND.value

        if share == SharePolicy.EXCLUSIVE.value and rk:
            prior = receipt_exclusive.get(rk)
            if prior and prior != sid:
                violations.append(
                    DashboardSlotsViolation(
                        code="multiplex_exclusive_conflict",
                        message=f"receipt {rk[:16]}… binds {prior} and {sid}",
                        path=path,
                    )
                )
                occupancy[sid] = OccupancyState.MULTIPLEX_CONFLICT.value
            else:
                receipt_exclusive[rk] = sid

        prior_gates = slot.get("prior_gate_ids")
        if prior_gates is not None:
            if not isinstance(prior_gates, list):
                violations.append(
                    DashboardSlotsViolation(
                        code="prior_gate_ids_invalid",
                        message="must be list",
                        path=f"{path}.prior_gate_ids",
                    )
                )
            else:
                for gid in prior_gates:
                    if str(gid) not in gate_ids():
                        violations.append(
                            DashboardSlotsViolation(
                                code="unknown_prior_gate",
                                message=str(gid),
                                path=f"{path}.prior_gate_ids",
                            )
                        )

        depends = slot.get("depends_on")
        if depends is not None and not isinstance(depends, list):
            violations.append(
                DashboardSlotsViolation(
                    code="depends_on_invalid",
                    message="depends_on must be list of slot_id",
                    path=f"{path}.depends_on",
                )
            )

        dod = slot.get("definition_of_done_display")
        if dod is not None:
            if not isinstance(dod, list):
                violations.append(
                    DashboardSlotsViolation(
                        code="dod_display_invalid",
                        message="definition_of_done_display must be list",
                        path=f"{path}.definition_of_done_display",
                    )
                )
            else:
                for item in dod:
                    if not isinstance(item, dict):
                        continue
                    if (
                        item.get("met") is True
                        and str(item.get("predicate") or "").lower().find("live") >= 0
                    ):
                        violations.append(
                            DashboardSlotsViolation(
                                code="dod_display_live_claim",
                                message="DoD display cannot assert live proof",
                                path=f"{path}.definition_of_done_display",
                            )
                        )

        cues = slot.get("cues")
        if cues is not None:
            if not isinstance(cues, list):
                violations.append(
                    DashboardSlotsViolation(
                        code="cues_invalid",
                        message="cues must be list",
                        path=f"{path}.cues",
                    )
                )
            else:
                for ci, cue in enumerate(cues):
                    if not isinstance(cue, dict):
                        continue
                    ctype = str(cue.get("cue_type") or "")
                    if ctype not in CUE_TYPES:
                        violations.append(
                            DashboardSlotsViolation(
                                code="unknown_cue_type",
                                message=ctype,
                                path=f"{path}.cues[{ci}]",
                            )
                        )
                    counts_user = cue.get("counts_as_user_intent")
                    if ctype in INJECTED_CUE_TYPES and counts_user is True:
                        violations.append(
                            DashboardSlotsViolation(
                                code="injected_cue_not_user_intent",
                                message=ctype,
                                path=f"{path}.cues[{ci}]",
                            )
                        )

    if slot_nodes and detect_slot_dependency_cycle(slot_nodes):
        violations.append(
            DashboardSlotsViolation(
                code="slot_dependency_cycle",
                message="depends_on cycle among slots",
                path="slots",
            )
        )

    # depends_on targets must exist
    id_set = set(ordered_ids)
    for idx, slot in enumerate(slot_nodes):
        deps = slot.get("depends_on")
        if not isinstance(deps, list):
            continue
        for dep in deps:
            if str(dep) not in id_set:
                violations.append(
                    DashboardSlotsViolation(
                        code="depends_on_unknown_slot",
                        message=str(dep),
                        path=f"slots[{idx}].depends_on",
                    )
                )

    if ordered_ids:
        try:
            nodes = [
                {
                    "node_id": s["slot_id"],
                    "gate_id": s["slot_id"],
                    "depends_on": list(s.get("depends_on") or []),
                }
                for s in slot_nodes
                if s.get("slot_id")
            ]
            topological_gate_order(nodes)
        except ValueError:
            violations.append(
                DashboardSlotsViolation(
                    code="slot_dependency_order_failed",
                    message="topological order failed",
                    path="slots",
                )
            )

    if proof_document is not None:
        proof_val = validate_proof_document(proof_document)
        if not proof_val.ok:
            violations.append(
                DashboardSlotsViolation(
                    code="proof_document_invalid",
                    message="linked proof document failed validation",
                    path="proof_ref",
                )
            )
        else:
            proof_rk = str(proof_document.get("receipt_key") or "")
            proof_etag = str(proof_document.get("etag") or "")
            for slot in slot_nodes:
                bind = slot.get("bind")
                if not isinstance(bind, dict):
                    continue
                if proof_rk and str(bind.get("receipt_key") or "") != proof_rk:
                    violations.append(
                        DashboardSlotsViolation(
                            code="proof_receipt_mismatch",
                            message="slot bind receipt_key must match proof document",
                            path=str(slot.get("slot_id")),
                        )
                    )
                if proof_etag and str(bind.get("etag") or "") != proof_etag:
                    violations.append(
                        DashboardSlotsViolation(
                            code="proof_etag_mismatch",
                            message="slot bind etag must match proof document",
                            path=str(slot.get("slot_id")),
                        )
                    )

    claims = doc.get("dashboard_live_claim")
    if claims is not None and _forbidden_live_dashboard_claim(json.dumps(claims)):
        violations.append(
            DashboardSlotsViolation(
                code="dashboard_live_claim_forbidden",
                message="cannot claim LIVE VERIFIED from dashboard slots alone",
                path="dashboard_live_claim",
            )
        )

    ok = len(violations) == 0
    return SlotValidationResult(
        ok=ok,
        violations=tuple(violations),
        ordered_slot_ids=tuple(ordered_ids),
        occupancy=occupancy,
    )


def minimal_valid_slot_registry_document() -> dict[str, Any]:
    """Minimal passing registry for hermetic tests."""
    receipt = "rcpt_kilo_dashboard_slots_hermetic"
    etag = "etag_dashboard_slots_v1"
    digest = build_multiplex_digest_identity(receipt, etag, dashboard_revision=1)
    return {
        "schema_version": "kilo-dashboard-slots-v1",
        "registry_id": "kilo_slots_fixture_minimal",
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "four_state_max": "TEST_VERIFIED",
        "live_verified": False,
        "live_api_called": False,
        "evidence_label": "inferred",
        "prior_gate_ids": [
            "spine-docs",
            "env-matrix",
            "substrate-checklist",
            "governance-evidence",
            "mercury-hermetic",
            "swarm-instrumentation",
            "proof-schema",
        ],
        "slots": [
            {
                "slot_id": "slot-proof-receipt",
                "kind": SlotKind.PROOF_RECEIPT.value,
                "share_policy": SharePolicy.EXCLUSIVE.value,
                "prior_gate_ids": ["proof-schema"],
                "depends_on": [],
                "bind": {
                    "receipt_key": receipt,
                    "etag": etag,
                    "dashboard_revision": 1,
                    "multiplex_digest_id": digest,
                },
                "definition_of_done_display": [
                    {
                        "id": "dod-display-1",
                        "predicate": "hermetic bind visible (display only)",
                        "met": True,
                    }
                ],
                "cues": [
                    {
                        "cue_id": "cue-gate-ready",
                        "cue_type": "gate_ready",
                        "counts_as_user_intent": False,
                        "text_ref": "logical://slots/minimal",
                    }
                ],
            },
            {
                "slot_id": "slot-gate-status",
                "kind": SlotKind.GATE_STATUS.value,
                "share_policy": SharePolicy.SHARED_EXPLICIT.value,
                "depends_on": ["slot-proof-receipt"],
                "prior_gate_ids": ["proof-schema"],
                "bind": {
                    "receipt_key": receipt,
                    "etag": etag,
                    "dashboard_revision": 1,
                    "multiplex_digest_id": digest,
                },
            },
            {
                "slot_id": "slot-swarm-digest",
                "kind": SlotKind.SWARM_DIGEST.value,
                "share_policy": SharePolicy.SHARED_EXPLICIT.value,
                "depends_on": ["slot-gate-status"],
                "bind": {
                    "receipt_key": receipt,
                    "etag": etag,
                    "dashboard_revision": 1,
                    "multiplex_digest_id": digest,
                },
            },
        ],
    }


def slot_registry_json_schema() -> dict[str, Any]:
    """Hermetic JSON schema dict for operator tooling."""
    return {
        "title": "KILO Dashboard Slot Registry",
        "schema_version": "kilo-dashboard-slots-v1",
        "gate_id": GATE_ID,
        "slot_kinds": sorted(SLOT_KINDS),
        "occupancy_states": [s.value for s in OccupancyState],
        "share_policies": [s.value for s in SharePolicy],
        "required_top_level": [
            "schema_version",
            "registry_id",
            "gate_id",
            "pr_number",
            "four_state_max",
            "live_verified",
            "live_api_called",
            "evidence_label",
            "slots",
        ],
    }


def run_fixture_suite() -> tuple[int, int, list[str]]:
    """Load fixtures; valid_* must pass, invalid_* must fail."""
    positive = negative = 0
    errors: list[str] = []
    for path in list_fixture_paths():
        name = path.name
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{name}: json error {exc}")
            continue
        result = validate_slot_registry_document(doc)
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


def _proof_schema_summary_ref(proof: ProofSchemaResult) -> dict[str, Any]:
    return {
        "ok": proof.ok,
        "gate_id": "proof-schema",
        "violation_count": len(proof.violations),
    }


def _registry_contract_check() -> tuple[bool, str]:
    path = REPO_ROOT / _VERIFY_SCRIPT_REL
    if not path.is_file():
        return False, f"missing operator script {_VERIFY_SCRIPT_REL}"
    schema = slot_registry_json_schema()
    if schema.get("gate_id") != GATE_ID:
        return False, "schema gate_id mismatch"
    gate = gate_for_pr(PR_NUMBER)
    if gate is None or gate.gate_id != GATE_ID:
        return False, "arc gate missing for PR 149"
    return True, "registry contract present"


def evaluate_dashboard_slots(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    run_fixtures: bool = True,
) -> DashboardSlotsResult:
    """Evaluate dashboard-slots gate (fail-closed)."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved_mode = mode if mode is not None else detect_matrix_mode(env)
    violations: list[DashboardSlotsViolation] = []

    proof = hermetic_proof_schema_operator_check(env)
    if not proof.ok:
        for v in proof.violations:
            violations.append(
                DashboardSlotsViolation(
                    code=f"proof_{v.code}",
                    message=v.message,
                    path=v.path,
                )
            )

    contract_ok, contract_detail = _registry_contract_check()
    if not contract_ok:
        violations.append(
            DashboardSlotsViolation(code="registry_contract_failed", message=contract_detail)
        )

    pos = neg = 0
    fixture_errors: list[str] = []
    if run_fixtures:
        pos, neg, fixture_errors = run_fixture_suite()
        for err in fixture_errors:
            violations.append(DashboardSlotsViolation(code="fixture_suite_failed", message=err))

    minimal_doc = minimal_valid_slot_registry_document()
    minimal_val = validate_slot_registry_document(minimal_doc)
    if not minimal_val.ok:
        violations.append(
            DashboardSlotsViolation(
                code="minimal_registry_invalid",
                message=",".join(v.code for v in minimal_val.violations),
            )
        )

    evidence = DashboardSlotsEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        proof_schema_ok=proof.ok,
        proof_schema_gate_id="proof-schema",
        fixture_pass_count=pos,
        fixture_negative_reject_count=neg,
        registry_contract_ok=contract_ok,
        live_api_called=False,
        evidence_label="inferred",
    )

    ok = proof.ok and contract_ok and not fixture_errors and minimal_val.ok and len(violations) == 0
    return DashboardSlotsResult(
        mode=resolved_mode,
        ok=ok,
        proof_schema_ok=proof.ok,
        violations=tuple(violations) if not ok else (),
        evidence=evidence,
    )


def hermetic_dashboard_slots_operator_check(
    environ: Mapping[str, str] | None = None,
) -> DashboardSlotsResult:
    """Spine/CI operator: proof-schema layer + fixture suite + registry contract."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_dashboard_slots(detect_matrix_mode(env), env, run_fixtures=True)


def dashboard_slots_gate_closed() -> bool:
    """True when PR #149 gate passes under hermetic operator + unit evaluation."""
    gate = gate_for_pr(PR_NUMBER)
    if gate is None or gate.gate_id != GATE_ID:
        return False
    env = minimal_dashboard_slots_environ()
    op = hermetic_dashboard_slots_operator_check(env)
    unit = evaluate_dashboard_slots(EnvMatrixMode.HERMETIC_UNIT, env, run_fixtures=True)
    return op.ok and unit.ok


def redact_dashboard_slots_summary(text: str) -> str:
    return redact_proof_summary(text)


def dashboard_slots_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Hermetic summary for CLI and spine consumers (redacted)."""
    env = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    operator = hermetic_dashboard_slots_operator_check(env)
    prep_env = dict(env)
    prep_env.setdefault("THINKBOX_KILO_MATRIX_MODE", EnvMatrixMode.LIVE_PROOF_PREP.value)
    prep = evaluate_dashboard_slots(EnvMatrixMode.LIVE_PROOF_PREP, prep_env, run_fixtures=False)
    gate = gate_for_pr(PR_NUMBER)
    redacted_env_sample = {
        k: redact_secret_value(k, env.get(k))
        for k in sorted(env.keys())
        if k.startswith(("INCEPTION", "THINKBOX_", "UPSTASH_", "GOVERNANCE"))
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
        "proof_schema_layer": True,
        "hermetic_operator_ok": operator.ok,
        "proof_schema_ok": operator.proof_schema_ok,
        "fixture_paths": [p.name for p in list_fixture_paths()],
        "schema_version": "kilo-dashboard-slots-v1",
        "slot_kinds": sorted(SLOT_KINDS),
        "live_proof_prep_ok": prep.ok,
        "live_proof_prep_violation_codes": sorted({v.code for v in prep.violations}),
        "hermetic_violation_codes": sorted({v.code for v in operator.violations}),
        "redacted_env_sample": redacted_env_sample,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "arc_gate_theme": gate.theme if gate else None,
        "gate_closed_default": dashboard_slots_gate_closed(),
        "verify_script": str(_VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / _VERIFY_SCRIPT_REL).is_file(),
        "multiplex_digest_helper": "build_multiplex_digest_identity",
        "think_job_receipt_normalize": "normalize_receipt_key",
    }


def minimal_dashboard_slots_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Clean hermetic env for dashboard-slots unit tests."""
    base: MutableMapping[str, str] = dict(minimal_proof_schema_environ())
    if extra:
        base.update(extra)
    return dict(base)
