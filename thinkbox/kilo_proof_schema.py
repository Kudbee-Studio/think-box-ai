"""Hermetic KILO live-proof / ledger JSON schema gate (PR #148, ``proof-schema``).

Layers on PR #147 ``swarm-instrumentation``. Defines a fail-closed document contract
for KILO proof artifacts: gate chains, receipt keys, etag, cue types (injected vs user),
dependency graphs, definition-of-done, and four-state honesty. No network;
``live_api_called=False`` in hermetic modes.

Patterns absorbed from KudbeeZero/kudbee-kirocrew (dependency router, injected cues,
DoD checklist, halt sentinels) as hermetic contracts only — no kirocrew runtime import.
"""

from __future__ import annotations

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
from thinkbox.kilo_substrate_checklist import redact_box_token, redact_box_url
from thinkbox.kilo_swarm_instrumentation import (
    SwarmInstrumentationResult,
    hermetic_swarm_operator_check,
    minimal_swarm_instrumentation_environ,
    redact_swarm_summary,
)

__all__ = (
    "CUE_TYPES",
    "FOUR_STATE_VALUES",
    "GATE_ID",
    "HALT_REASONS",
    "KNOWN_ARC_GATE_IDS",
    "PR_NUMBER",
    "ProofSchemaEvidence",
    "ProofSchemaMode",
    "ProofSchemaResult",
    "ProofSchemaViolation",
    "ProofValidationResult",
    "detect_dependency_cycle",
    "evaluate_proof_schema",
    "fixtures_dir",
    "hermetic_proof_schema_operator_check",
    "kilo_proof_json_schema",
    "list_fixture_paths",
    "load_fixture",
    "minimal_proof_schema_environ",
    "minimal_valid_proof_document",
    "proof_schema_contract_summary",
    "proof_schema_gate_closed",
    "redact_proof_summary",
    "run_fixture_suite",
    "topological_gate_order",
    "validate_proof_document",
)

GATE_ID = "proof-schema"
PR_NUMBER = 148

_FIXTURES_REL = Path("data/kilo_proof_schema/fixtures")
_VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_proof_schema.py")

FOUR_STATE_VALUES: frozenset[str] = frozenset(
    {"CODE_COMPLETE", "TEST_VERIFIED", "LIVE_VERIFIED", "PRODUCTION_READY"}
)

CUE_TYPES: frozenset[str] = frozenset(
    {
        "user",
        "injected_nudge",
        "cron",
        "subagent_completion",
        "gate_ready",
        "blocker",
    }
)

HALT_REASONS: frozenset[str] = frozenset(
    {"sentinel", "dod_met", "max_cycles", "user_stop", "blocker"}
)

INJECTED_CUE_TYPES: frozenset[str] = frozenset(CUE_TYPES - {"user"})

KNOWN_ARC_GATE_IDS: frozenset[str] = frozenset(gate_ids())

_REQUIRED_TOP_LEVEL: tuple[str, ...] = (
    "schema_version",
    "proof_id",
    "gate_id",
    "pr_number",
    "four_state_max",
    "live_verified",
    "live_api_called",
    "evidence_label",
    "receipt_key",
    "etag",
    "prior_gate_ids",
    "gates",
    "cues",
)

_SECRET_PATTERN = re.compile(
    r"(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._-]{20,}|"
    r"UPSTASH_PUBLIC_BOX_TOKEN['\"]?\s*:\s*['\"][^'\"]{8,})",
    re.IGNORECASE,
)

_FORBIDDEN_LITERAL_CLAIMS = (
    "KILO LIVE VERIFIED",
    "KILO PRODUCTION READY",
    "KILO live build verified",
)


class ProofSchemaMode(str, Enum):
    """Alias of env-matrix modes for proof-schema reporting."""

    HERMETIC_UNIT = EnvMatrixMode.HERMETIC_UNIT.value
    HERMETIC_CI = EnvMatrixMode.HERMETIC_CI.value
    LIVE_PROOF_PREP = EnvMatrixMode.LIVE_PROOF_PREP.value


@dataclass(frozen=True)
class ProofSchemaViolation:
    """Single fail-closed proof-schema violation."""

    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ProofValidationResult:
    """Outcome of validating one proof JSON document."""

    ok: bool
    violations: tuple[ProofSchemaViolation, ...] = ()
    ordered_gate_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "violations": [
                {"code": v.code, "message": v.message, "path": v.path} for v in self.violations
            ],
            "ordered_gate_ids": list(self.ordered_gate_ids),
        }


@dataclass(frozen=True)
class ProofSchemaEvidence:
    """Redacted evidence for proof-schema gate closure."""

    gate_id: str
    pr_number: int
    swarm_instrumentation_ok: bool
    swarm_summary_ref: dict[str, Any]
    fixture_pass_count: int
    fixture_negative_reject_count: int
    schema_contract_ok: bool
    live_api_called: bool
    evidence_label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "pr_number": self.pr_number,
            "swarm_instrumentation_ok": self.swarm_instrumentation_ok,
            "swarm_summary_ref": self.swarm_summary_ref,
            "fixture_pass_count": self.fixture_pass_count,
            "fixture_negative_reject_count": self.fixture_negative_reject_count,
            "schema_contract_ok": self.schema_contract_ok,
            "live_api_called": self.live_api_called,
            "evidence_label": self.evidence_label,
            "four_state_max": "TEST_VERIFIED",
        }


@dataclass
class ProofSchemaResult:
    """Outcome of evaluating proof-schema for one mode."""

    mode: EnvMatrixMode
    ok: bool
    swarm_instrumentation_ok: bool
    violations: list[ProofSchemaViolation] = field(default_factory=list)
    evidence: ProofSchemaEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "ok": self.ok,
            "swarm_instrumentation_ok": self.swarm_instrumentation_ok,
            "violations": [
                {"code": v.code, "message": v.message, "path": v.path} for v in self.violations
            ],
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "gate_id": GATE_ID,
            "pr_number": PR_NUMBER,
            "four_state_max": "TEST_VERIFIED",
            "live_api_called": False,
        }


def kilo_proof_json_schema() -> dict[str, Any]:
    """Hermetic JSON Schema (draft 2020-12 shape) for KILO proof documents."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://thinkbox.ai/schemas/kilo-proof-v1.json",
        "title": "KILO Live Proof Document",
        "type": "object",
        "additionalProperties": False,
        "required": list(_REQUIRED_TOP_LEVEL),
        "properties": {
            "schema_version": {"type": "string", "const": "kilo-proof-v1"},
            "proof_id": {"type": "string", "minLength": 8},
            "gate_id": {"type": "string", "enum": sorted(KNOWN_ARC_GATE_IDS)},
            "pr_number": {"type": "integer", "minimum": 141, "maximum": 150},
            "four_state_max": {
                "type": "string",
                "enum": sorted(FOUR_STATE_VALUES),
            },
            "live_verified": {"type": "boolean"},
            "live_api_called": {"type": "boolean"},
            "evidence_label": {
                "type": "string",
                "enum": ["simulated", "inferred", "verified", "physically_measured"],
            },
            "receipt_key": {"type": "string", "minLength": 8},
            "etag": {"type": "string", "minLength": 8},
            "north_star_ref": {"type": "string"},
            "roadmap_ref": {"type": "string"},
            "tasks_ref": {"type": "string"},
            "idle_secs": {"type": "integer", "minimum": 0},
            "max_cycles": {"type": "integer", "minimum": 1},
            "stop_sentinel": {"oneOf": [{"type": "boolean"}, {"type": "string"}]},
            "halt_reason": {"type": "string", "enum": sorted(HALT_REASONS)},
            "prior_gate_ids": {
                "type": "array",
                "items": {"type": "string", "enum": sorted(KNOWN_ARC_GATE_IDS)},
                "uniqueItems": True,
            },
            "gates": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["node_id", "gate_id", "hermetic_operator_ok"],
                    "properties": {
                        "node_id": {"type": "string"},
                        "gate_id": {"type": "string", "enum": sorted(KNOWN_ARC_GATE_IDS)},
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "hermetic_operator_ok": {"type": "boolean"},
                    },
                },
            },
            "cues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["cue_id", "cue_type", "counts_as_user_intent"],
                    "properties": {
                        "cue_id": {"type": "string"},
                        "cue_type": {"type": "string", "enum": sorted(CUE_TYPES)},
                        "counts_as_user_intent": {"type": "boolean"},
                        "text_ref": {"type": "string"},
                    },
                },
            },
            "definition_of_done": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "predicate", "met"],
                    "properties": {
                        "id": {"type": "string"},
                        "predicate": {"type": "string"},
                        "met": {"type": "boolean"},
                    },
                },
            },
        },
    }


def fixtures_dir() -> Path:
    """Absolute path to hermetic proof-schema fixtures."""
    return REPO_ROOT / _FIXTURES_REL


def list_fixture_paths() -> tuple[Path, ...]:
    """Sorted fixture JSON paths."""
    root = fixtures_dir()
    if not root.is_dir():
        return ()
    return tuple(sorted(root.glob("*.json")))


def load_fixture(name: str) -> dict[str, Any]:
    """Load one fixture by filename (e.g. ``valid_minimal.json``)."""
    path = fixtures_dir() / name
    return json.loads(path.read_text(encoding="utf-8"))


def minimal_valid_proof_document() -> dict[str, Any]:
    """Canonical minimal valid proof document for tests and operators."""
    return {
        "schema_version": "kilo-proof-v1",
        "proof_id": "kilo_proof_hermetic_minimal",
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "four_state_max": "TEST_VERIFIED",
        "live_verified": False,
        "live_api_called": False,
        "evidence_label": "inferred",
        "receipt_key": "rcpt_kilo_proof_schema_hermetic",
        "etag": "etag_kilo_proof_schema_v1",
        "prior_gate_ids": [
            "spine-docs",
            "env-matrix",
            "substrate-checklist",
            "governance-evidence",
            "mercury-hermetic",
            "swarm-instrumentation",
        ],
        "gates": [
            {
                "node_id": "gate-swarm",
                "gate_id": "swarm-instrumentation",
                "depends_on": ["gate-mercury"],
                "hermetic_operator_ok": True,
            },
            {
                "node_id": "gate-mercury",
                "gate_id": "mercury-hermetic",
                "depends_on": [],
                "hermetic_operator_ok": True,
            },
            {
                "node_id": "gate-proof-schema",
                "gate_id": GATE_ID,
                "depends_on": ["gate-swarm"],
                "hermetic_operator_ok": True,
            },
        ],
        "cues": [
            {
                "cue_id": "cue-gate-ready",
                "cue_type": "gate_ready",
                "counts_as_user_intent": False,
                "text_ref": "logical://readiness/proof-schema",
            }
        ],
        "definition_of_done": [
            {
                "id": "dod-schema-validates",
                "predicate": "validate_proof_document returns ok",
                "met": True,
            },
            {
                "id": "dod-hermetic-only",
                "predicate": "live_api_called is false",
                "met": True,
            },
        ],
    }


def detect_dependency_cycle(
    nodes: Sequence[Mapping[str, Any]],
    *,
    id_key: str = "node_id",
    depends_key: str = "depends_on",
) -> bool:
    """Return True when *nodes* contain a cycle via depends_on edges."""
    graph: dict[str, list[str]] = {}
    for node in nodes:
        node_id = str(node.get(id_key, ""))
        deps = list(node.get(depends_key) or [])
        graph[node_id] = [str(d) for d in deps]
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        for dep in graph.get(node_id, []):
            if dep not in graph:
                continue
            if dfs(dep):
                return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    return any(dfs(nid) for nid in graph)


def topological_gate_order(
    nodes: Sequence[Mapping[str, Any]],
    *,
    id_key: str = "node_id",
    depends_key: str = "depends_on",
) -> list[str]:
    """Return topological order of node ids; raise ValueError on cycle."""
    if detect_dependency_cycle(nodes, id_key=id_key, depends_key=depends_key):
        raise ValueError("dependency cycle detected")

    graph: dict[str, list[str]] = {}
    for node in nodes:
        node_id = str(node.get(id_key, ""))
        graph[node_id] = [str(d) for d in (node.get(depends_key) or [])]

    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            raise ValueError("dependency cycle detected")
        visiting.add(node_id)
        for dep in graph.get(node_id, []):
            if dep in graph:
                visit(dep)
        visiting.remove(node_id)
        visited.add(node_id)
        ordered.append(node_id)

    for node_id in sorted(graph.keys()):
        visit(node_id)
    return ordered


def _violation(code: str, message: str, path: str | None = None) -> ProofSchemaViolation:
    return ProofSchemaViolation(code=code, message=message, path=path)


def _check_type(value: Any, expected: str, path: str, hits: list[ProofSchemaViolation]) -> None:
    if expected == "string" and not isinstance(value, str):
        hits.append(_violation("type_mismatch", f"expected string at {path}", path))
    elif expected == "boolean" and not isinstance(value, bool):
        hits.append(_violation("type_mismatch", f"expected boolean at {path}", path))
    elif expected == "integer" and not isinstance(value, int):
        hits.append(_violation("type_mismatch", f"expected integer at {path}", path))
    elif expected == "array" and not isinstance(value, list):
        hits.append(_violation("type_mismatch", f"expected array at {path}", path))


def _scan_redaction(text: str, path: str, hits: list[ProofSchemaViolation]) -> None:
    for forbidden in _FORBIDDEN_LITERAL_CLAIMS:
        if forbidden in text:
            hits.append(
                _violation(
                    "forbidden_affirmative_claim",
                    f"forbidden literal in document: {forbidden}",
                    path,
                )
            )
    if _SECRET_PATTERN.search(text):
        hits.append(_violation("secret_like_literal", "secret-shaped literal in document", path))


def validate_proof_document(doc: Mapping[str, Any]) -> ProofValidationResult:
    """Fail-closed validator for KILO proof JSON (hermetic contract)."""
    hits: list[ProofSchemaViolation] = []
    serialized = json.dumps(doc, sort_keys=True)
    _scan_redaction(serialized, "$", hits)

    if not isinstance(doc, Mapping):
        return ProofValidationResult(False, tuple(hits))

    for key in _REQUIRED_TOP_LEVEL:
        if key not in doc:
            hits.append(_violation("missing_required", f"missing required field {key}", key))

    if doc.get("schema_version") != "kilo-proof-v1":
        hits.append(
            _violation("schema_version", "schema_version must be kilo-proof-v1", "schema_version")
        )

    gate_id = doc.get("gate_id")
    if gate_id is not None and gate_id not in KNOWN_ARC_GATE_IDS:
        hits.append(_violation("unknown_gate_id", f"unknown gate_id {gate_id}", "gate_id"))

    four_state = doc.get("four_state_max")
    if four_state is not None and four_state not in FOUR_STATE_VALUES:
        hits.append(_violation("four_state_invalid", "invalid four_state_max", "four_state_max"))

    live_verified = doc.get("live_verified")
    live_api = doc.get("live_api_called")
    if live_api is True:
        hits.append(
            _violation(
                "live_api_forbidden",
                "live_api_called must be false in hermetic proofs",
                "live_api_called",
            )
        )

    dod = doc.get("definition_of_done") or []
    dod_all_met = isinstance(dod, list) and all(
        isinstance(item, Mapping) and item.get("met") is True for item in dod
    )

    if four_state in ("LIVE_VERIFIED", "PRODUCTION_READY"):
        if live_verified is not True:
            hits.append(
                _violation(
                    "four_state_live_claim_without_flag",
                    "four_state_max LIVE/PRODUCTION requires live_verified true",
                    "four_state_max",
                )
            )
        if not dod_all_met:
            hits.append(
                _violation(
                    "four_state_dod_incomplete",
                    "four_state_max LIVE/PRODUCTION requires all DoD met",
                    "definition_of_done",
                )
            )

    if live_verified is True and (
        not dod_all_met or four_state not in ("LIVE_VERIFIED", "PRODUCTION_READY")
    ):
        hits.append(
            _violation(
                "live_verified_without_dod",
                "live_verified true requires DoD complete and four_state_max LIVE or PRODUCTION",
                "live_verified",
            )
        )

    prior = doc.get("prior_gate_ids") or []
    if isinstance(prior, list):
        for idx, gid in enumerate(prior):
            if gid not in KNOWN_ARC_GATE_IDS:
                hits.append(
                    _violation(
                        "unknown_prior_gate", f"unknown prior gate {gid}", f"prior_gate_ids[{idx}]"
                    )
                )
        if doc.get("gate_id") == GATE_ID and "swarm-instrumentation" not in prior:
            hits.append(
                _violation(
                    "prior_gate_ids_missing_swarm",
                    "proof-schema prior_gate_ids must include swarm-instrumentation",
                    "prior_gate_ids",
                )
            )

    gates = doc.get("gates") or []
    ordered: list[str] = []
    if isinstance(gates, list):
        if not gates:
            hits.append(_violation("gates_empty", "gates must be non-empty", "gates"))
        else:
            for idx, gate in enumerate(gates):
                if not isinstance(gate, Mapping):
                    hits.append(
                        _violation("gate_shape", f"gate entry {idx} not object", f"gates[{idx}]")
                    )
                    continue
                gid = gate.get("gate_id")
                if gid not in KNOWN_ARC_GATE_IDS:
                    hits.append(
                        _violation(
                            "unknown_gate_node", f"unknown gate {gid}", f"gates[{idx}].gate_id"
                        )
                    )
                if gate.get("hermetic_operator_ok") is not True:
                    hits.append(
                        _violation(
                            "gate_not_hermetic_ok",
                            "hermetic_operator_ok must be true for admitted gates",
                            f"gates[{idx}].hermetic_operator_ok",
                        )
                    )
            if detect_dependency_cycle(gates):
                hits.append(_violation("dependency_cycle", "gates depends_on cycle", "gates"))
            else:
                try:
                    ordered = topological_gate_order(gates)
                except ValueError:
                    hits.append(_violation("dependency_cycle", "gates depends_on cycle", "gates"))

    cues = doc.get("cues") or []
    if isinstance(cues, list):
        for idx, cue in enumerate(cues):
            if not isinstance(cue, Mapping):
                hits.append(_violation("cue_shape", f"cue {idx} not object", f"cues[{idx}]"))
                continue
            cue_type = cue.get("cue_type")
            if cue_type not in CUE_TYPES:
                hits.append(
                    _violation(
                        "unknown_cue_type", f"unknown cue_type {cue_type}", f"cues[{idx}].cue_type"
                    )
                )
                continue
            counts = cue.get("counts_as_user_intent")
            if cue_type == "user":
                if counts is not True:
                    hits.append(
                        _violation(
                            "user_cue_intent",
                            "user cue must set counts_as_user_intent true",
                            f"cues[{idx}].counts_as_user_intent",
                        )
                    )
            elif counts is True:
                hits.append(
                    _violation(
                        "injected_cue_not_user_intent",
                        "injected cues must not count as user intent",
                        f"cues[{idx}].counts_as_user_intent",
                    )
                )

    halt = doc.get("halt_reason")
    if halt is not None and halt not in HALT_REASONS:
        hits.append(_violation("unknown_halt_reason", f"unknown halt_reason {halt}", "halt_reason"))

    receipt = doc.get("receipt_key")
    etag = doc.get("etag")
    if isinstance(receipt, str) and len(receipt) < 8:
        hits.append(_violation("receipt_key_short", "receipt_key too short", "receipt_key"))
    if isinstance(etag, str) and len(etag) < 8:
        hits.append(_violation("etag_short", "etag too short", "etag"))

    ok = len(hits) == 0
    return ProofValidationResult(ok=ok, violations=tuple(hits), ordered_gate_ids=tuple(ordered))


def run_fixture_suite() -> tuple[int, int, list[str]]:
    """Validate fixtures: returns (positive_pass, negative_reject, errors)."""
    positive = 0
    negative = 0
    errors: list[str] = []
    for path in list_fixture_paths():
        raw = json.loads(path.read_text(encoding="utf-8"))
        expect_invalid = raw.get("_expect") == "invalid"
        data = {k: v for k, v in raw.items() if k != "_expect"}
        result = validate_proof_document(data)
        if expect_invalid:
            if result.ok:
                errors.append(f"{path.name}: expected invalid but validated ok")
            else:
                negative += 1
        else:
            if not result.ok:
                errors.append(
                    f"{path.name}: expected valid but failed: {[v.code for v in result.violations]}"
                )
            else:
                positive += 1
    return positive, negative, errors


def _swarm_summary_ref(swarm: SwarmInstrumentationResult) -> dict[str, Any]:
    return {
        "mode": swarm.mode.value,
        "ok": swarm.ok,
        "passed_count": swarm.passed_count,
        "gate_id": "swarm-instrumentation",
    }


def _schema_contract_check() -> tuple[bool, str]:
    path = REPO_ROOT / _VERIFY_SCRIPT_REL
    if not path.is_file():
        return False, f"missing operator script {_VERIFY_SCRIPT_REL}"
    schema = kilo_proof_json_schema()
    if schema.get("title") != "KILO Live Proof Document":
        return False, "schema title mismatch"
    if GATE_ID not in KNOWN_ARC_GATE_IDS:
        return False, "proof-schema gate not in arc"
    return True, "schema contract present"


def evaluate_proof_schema(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    run_fixtures: bool = True,
) -> ProofSchemaResult:
    """Evaluate proof-schema gate (fail-closed)."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved_mode = mode if mode is not None else detect_matrix_mode(env)
    violations: list[ProofSchemaViolation] = []

    swarm = hermetic_swarm_operator_check(env)
    if not swarm.ok:
        for v in swarm.violations:
            violations.append(
                ProofSchemaViolation(
                    code=f"swarm_{v.code}",
                    message=v.message,
                    path=v.check_id,
                )
            )

    contract_ok, contract_detail = _schema_contract_check()
    if not contract_ok:
        violations.append(
            ProofSchemaViolation(code="schema_contract_failed", message=contract_detail)
        )

    pos = neg = 0
    fixture_errors: list[str] = []
    if run_fixtures:
        pos, neg, fixture_errors = run_fixture_suite()
        for err in fixture_errors:
            violations.append(ProofSchemaViolation(code="fixture_suite_failed", message=err))

    minimal = validate_proof_document(minimal_valid_proof_document())
    if not minimal.ok:
        violations.append(
            ProofSchemaViolation(
                code="minimal_document_invalid",
                message=",".join(v.code for v in minimal.violations),
            )
        )

    evidence = ProofSchemaEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        swarm_instrumentation_ok=swarm.ok,
        swarm_summary_ref=_swarm_summary_ref(swarm),
        fixture_pass_count=pos,
        fixture_negative_reject_count=neg,
        schema_contract_ok=contract_ok,
        live_api_called=False,
        evidence_label="inferred",
    )

    ok = swarm.ok and contract_ok and not fixture_errors and minimal.ok and len(violations) == 0
    return ProofSchemaResult(
        mode=resolved_mode,
        ok=ok,
        swarm_instrumentation_ok=swarm.ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_proof_schema_operator_check(
    environ: Mapping[str, str] | None = None,
) -> ProofSchemaResult:
    """Spine/CI operator: swarm layer + fixture suite + schema contract."""
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_proof_schema(detect_matrix_mode(env), env, run_fixtures=True)


def proof_schema_gate_closed() -> bool:
    """True when PR #148 gate passes under hermetic operator + unit evaluation."""
    gate = gate_for_pr(PR_NUMBER)
    if gate is None or gate.gate_id != GATE_ID:
        return False
    env = minimal_proof_schema_environ()
    op = hermetic_proof_schema_operator_check(env)
    unit = evaluate_proof_schema(EnvMatrixMode.HERMETIC_UNIT, env, run_fixtures=True)
    return op.ok and unit.ok


def redact_proof_summary(text: str) -> str:
    """Scrub secret-like literals from serialized summaries."""
    return redact_swarm_summary(text)


def proof_schema_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Hermetic summary for CLI and spine consumers (redacted)."""
    env = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    operator = hermetic_proof_schema_operator_check(env)
    prep_env = dict(env)
    prep_env.setdefault("THINKBOX_KILO_MATRIX_MODE", EnvMatrixMode.LIVE_PROOF_PREP.value)
    prep = evaluate_proof_schema(EnvMatrixMode.LIVE_PROOF_PREP, prep_env, run_fixtures=False)
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
        "swarm_instrumentation_layer": True,
        "hermetic_operator_ok": operator.ok,
        "swarm_instrumentation_ok": operator.swarm_instrumentation_ok,
        "fixture_paths": [p.name for p in list_fixture_paths()],
        "schema_version": "kilo-proof-v1",
        "cue_types": sorted(CUE_TYPES),
        "halt_reasons": sorted(HALT_REASONS),
        "live_proof_prep_ok": prep.ok,
        "live_proof_prep_violation_codes": sorted({v.code for v in prep.violations}),
        "hermetic_violation_codes": sorted({v.code for v in operator.violations}),
        "redacted_env_sample": redacted_env_sample,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "arc_gate_theme": gate.theme if gate else None,
        "gate_closed_default": proof_schema_gate_closed(),
        "verify_script": str(_VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / _VERIFY_SCRIPT_REL).is_file(),
    }


def minimal_proof_schema_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Clean hermetic env for proof-schema unit tests."""
    base: MutableMapping[str, str] = dict(minimal_swarm_instrumentation_environ())
    if extra:
        base.update(extra)
    return dict(base)
