"""Hermetic live-smoke **operator** path (PR #153, ``live-smoke-operator``).

Extends PR #152 ``live-smoke-evidence`` binder with CLI-facing write + audit-flip
candidate helpers. Default path: no network; ``live_api_called=False``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_live_smoke_evidence import (
    GATE_ID as SMOKE_EVIDENCE_GATE_ID,
    audit_flip_candidate,
    hermetic_live_smoke_evidence_operator_check,
    minimal_live_smoke_evidence_environ,
    minimal_valid_smoke_evidence_document,
    validate_smoke_evidence_document,
)
from thinkbox.kilo_live_proof_exec import FOUNDER_ACK_ENV, live_exec_env_ready
from thinkbox.kilo_substrate_checklist import BOX_URL_ENV, redact_box_url

__all__ = (
    "ARTIFACT_DIR_REL",
    "AUDIT_CANDIDATE_NAME_SUFFIX",
    "DEFAULT_AUDIT_PRIOR_REL",
    "EVIDENCE_ARTIFACT_GLOB",
    "GATE_ID",
    "OPERATOR_CLI_REL",
    "PR_NUMBER",
    "REQUIRED_PRIOR_GATE_IDS",
    "SmokeOperatorEvidence",
    "SmokeOperatorResult",
    "SmokeOperatorViolation",
    "SmokeOperatorWriteResult",
    "audit_flip_candidate_path_for",
    "build_hermetic_smoke_evidence",
    "default_artifact_path",
    "evaluate_live_smoke_operator",
    "fixtures_dir",
    "hermetic_live_smoke_operator_check",
    "list_fixture_paths",
    "live_smoke_operator_contract_summary",
    "live_smoke_operator_gate_closed",
    "load_audit_prior_pass",
    "load_fixture",
    "load_json_file",
    "minimal_live_smoke_operator_environ",
    "parse_receipt_etag_pairs",
    "redact_operator_summary",
    "run_operator_fixture_suite",
    "write_audit_flip_candidate_file",
    "write_smoke_evidence_artifact",
)

GATE_ID = "live-smoke-operator"
PR_NUMBER = 153

ARTIFACT_DIR_REL = Path("data/thinkboxmd/artifacts")
EVIDENCE_ARTIFACT_GLOB = "kilo_live_smoke_*.json"
DEFAULT_AUDIT_PRIOR_REL = Path("docs/audit/passes/2026-09-23-pr152.json")
AUDIT_CANDIDATE_NAME_SUFFIX = "-live-candidate.json"
_FIXTURES_REL = Path("data/kilo_live_smoke_operator/fixtures")
_VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_live_smoke_operator.py")
OPERATOR_CLI_REL = Path("scripts/kilo_live_smoke_operator.py")

REQUIRED_PRIOR_GATE_IDS: frozenset[str] = frozenset({SMOKE_EVIDENCE_GATE_ID})

_SECRET_PATTERN = re.compile(
    r"(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9._-]{20,}|UPSTASH_PUBLIC_BOX_TOKEN=[^\s]+)",
    re.IGNORECASE,
)


class SmokeOperatorMode(str, Enum):
    """Reporting modes for live-smoke-operator."""

    HERMETIC_UNIT = EnvMatrixMode.HERMETIC_UNIT.value
    HERMETIC_CI = EnvMatrixMode.HERMETIC_CI.value
    LIVE_PROOF_PREP = EnvMatrixMode.LIVE_PROOF_PREP.value


@dataclass(frozen=True)
class SmokeOperatorViolation:
    """Single fail-closed operator-path violation."""

    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class SmokeOperatorWriteResult:
    """Outcome of writing one smoke evidence artifact."""

    ok: bool
    path: Path | None
    violations: tuple[SmokeOperatorViolation, ...] = ()
    document: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "path": str(self.path) if self.path else None,
            "violations": [
                {"code": v.code, "message": v.message, "path": v.path} for v in self.violations
            ],
        }


@dataclass(frozen=True)
class SmokeOperatorEvidence:
    """Redacted operator-path gate evidence (hermetic)."""

    gate_id: str
    pr_number: int
    smoke_evidence_layer_ok: bool
    fixture_pass_count: int
    fixture_negative_reject_count: int
    hermetic_write_ok: bool
    live_api_called: bool
    evidence_label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "pr_number": self.pr_number,
            "smoke_evidence_layer_ok": self.smoke_evidence_layer_ok,
            "fixture_pass_count": self.fixture_pass_count,
            "fixture_negative_reject_count": self.fixture_negative_reject_count,
            "hermetic_write_ok": self.hermetic_write_ok,
            "live_api_called": self.live_api_called,
            "evidence_label": self.evidence_label,
            "four_state_max": "TEST_VERIFIED",
        }


@dataclass
class SmokeOperatorResult:
    """Outcome of evaluating live-smoke-operator for one mode."""

    mode: EnvMatrixMode
    ok: bool
    smoke_evidence_layer_ok: bool
    violations: list[SmokeOperatorViolation] = field(default_factory=list)
    evidence: SmokeOperatorEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "ok": self.ok,
            "smoke_evidence_layer_ok": self.smoke_evidence_layer_ok,
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
    return json.loads((fixtures_dir() / name).read_text(encoding="utf-8"))


def load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def default_artifact_path(evidence_id: str | None = None) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = evidence_id or "hermetic"
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", slug)[:48]
    return REPO_ROOT / ARTIFACT_DIR_REL / f"kilo_live_smoke_{safe}_{stamp}.json"


def audit_flip_candidate_path_for(
    audit_prior: Path,
    *,
    out_dir: Path | None = None,
) -> Path:
    """Derive ``*-live-candidate.json`` beside the prior audit pass stem."""
    base_dir = out_dir or audit_prior.parent
    stem = audit_prior.stem
    return base_dir / f"{stem}{AUDIT_CANDIDATE_NAME_SUFFIX}"


def parse_receipt_etag_pairs(
    receipt_ids: Sequence[str],
    etags: Sequence[str],
) -> tuple[list[str], list[str], list[SmokeOperatorViolation]]:
    violations: list[SmokeOperatorViolation] = []
    r_list = list(receipt_ids)
    e_list = list(etags)
    if len(r_list) != len(e_list):
        violations.append(
            SmokeOperatorViolation(
                code="receipt_etag_length_mismatch",
                message="receipt_ids and etags must have equal length",
                path="receipt_ids",
            )
        )
    if not r_list:
        violations.append(
            SmokeOperatorViolation(code="receipt_ids_empty", message="receipt_ids required")
        )
    if not e_list:
        violations.append(
            SmokeOperatorViolation(code="etags_empty", message="etags required")
        )
    return r_list, e_list, violations


def build_hermetic_smoke_evidence(
    *,
    evidence_id: str | None = None,
    receipt_ids: Sequence[str] | None = None,
    etags: Sequence[str] | None = None,
    gate_chain: Sequence[Mapping[str, Any]] | None = None,
    redacted_endpoints: Mapping[str, str] | None = None,
    founder_ack_marker_present: bool = False,
    box_url_present: bool = False,
    live_api_called: bool = False,
    live_verified: bool = False,
    recorded_at: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], list[SmokeOperatorViolation]]:
    """Build a PR #152 evidence document for hermetic operator writes."""
    violations: list[SmokeOperatorViolation] = []
    if live_api_called and not live_verified:
        violations.append(
            SmokeOperatorViolation(
                code="live_api_without_verified",
                message="live_api_called requires live_verified in operator build",
            )
        )
    doc: dict[str, Any] = dict(minimal_valid_smoke_evidence_document())
    doc["operator_gate_id"] = GATE_ID
    doc["operator_pr_number"] = PR_NUMBER
    if evidence_id:
        doc["evidence_id"] = evidence_id
    if receipt_ids is not None and etags is not None:
        r_list, e_list, pair_v = parse_receipt_etag_pairs(receipt_ids, etags)
        violations.extend(pair_v)
        doc["receipt_ids"] = r_list
        doc["etags"] = e_list
    if gate_chain is not None:
        doc["gate_chain"] = [dict(h) for h in gate_chain]
    if redacted_endpoints is not None:
        doc["redacted_endpoints"] = dict(redacted_endpoints)
    doc["founder_ack_marker_present"] = founder_ack_marker_present
    doc["box_url_present"] = box_url_present
    doc["live_api_called"] = live_api_called
    doc["live_verified"] = live_verified
    if recorded_at:
        doc["recorded_at"] = recorded_at
    if extra:
        doc.update(dict(extra))
    return doc, violations


def _scan_write_payload(doc: Mapping[str, Any]) -> list[SmokeOperatorViolation]:
    hits: list[SmokeOperatorViolation] = []
    text = json.dumps(doc, sort_keys=True)
    if _SECRET_PATTERN.search(text):
        hits.append(
            SmokeOperatorViolation(
                code="secret_like_literal",
                message="refusing write: secret-shaped literal in document",
            )
        )
    return hits


def write_smoke_evidence_artifact(
    doc: Mapping[str, Any],
    *,
    path: Path | None = None,
    mkdir: bool = True,
) -> SmokeOperatorWriteResult:
    """Validate and write a kilo_live_smoke_*.json artifact (no HTTP)."""
    violations = list(_scan_write_payload(doc))
    if violations:
        return SmokeOperatorWriteResult(False, None, tuple(violations))

    out_path = path or default_artifact_path(str(doc.get("evidence_id") or "hermetic"))
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    mutable = dict(doc)
    try:
        rel_str = str(out_path.relative_to(REPO_ROOT))
    except ValueError:
        rel_str = str(out_path)
    mutable["evidence_artifact_path"] = rel_str

    val = validate_smoke_evidence_document(mutable, artifact_exists=False)
    if not val.ok:
        for v in val.violations:
            violations.append(
                SmokeOperatorViolation(code=v.code, message=v.message, path=v.path)
            )
        return SmokeOperatorWriteResult(False, None, tuple(violations), dict(mutable))

    if mkdir:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(mutable, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    post_val = validate_smoke_evidence_document(mutable, artifact_exists=True)
    if not post_val.ok:
        for v in post_val.violations:
            violations.append(
                SmokeOperatorViolation(code=v.code, message=v.message, path=v.path)
            )
        return SmokeOperatorWriteResult(False, out_path, tuple(violations), dict(mutable))

    return SmokeOperatorWriteResult(True, out_path, (), dict(mutable))


def load_audit_prior_pass(
    rel_path: Path | str = DEFAULT_AUDIT_PRIOR_REL,
) -> dict[str, Any]:
    path = REPO_ROOT / Path(rel_path)
    if not path.is_file():
        raise FileNotFoundError(f"audit prior missing: {rel_path}")
    return load_json_file(path)


def write_audit_flip_candidate_file(
    evidence: Mapping[str, Any],
    *,
    audit_prior_rel: Path | str = DEFAULT_AUDIT_PRIOR_REL,
    out_path: Path | None = None,
    artifact_exists: bool | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Run ``audit_flip_candidate`` and write candidate JSON (never mutates prior pass)."""
    prior = load_audit_prior_pass(audit_prior_rel)
    prior_path = REPO_ROOT / Path(audit_prior_rel)
    candidate_path = out_path or audit_flip_candidate_path_for(prior_path)
    if artifact_exists is None:
        art = evidence.get("evidence_artifact_path") or ""
        resolved = REPO_ROOT / str(art) if art else None
        artifact_exists = bool(resolved and resolved.is_file())
    candidate = audit_flip_candidate(evidence, prior, artifact_exists=artifact_exists)
    candidate["operator_gate_id"] = GATE_ID
    candidate["operator_pr_number"] = PR_NUMBER
    candidate["prior_pass"] = str(audit_prior_rel)
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return candidate_path, candidate


def run_operator_fixture_suite() -> tuple[int, int, list[str]]:
    positive = negative = 0
    errors: list[str] = []
    for path in list_fixture_paths():
        name = path.name
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{name}: json error {exc}")
            continue
        kind = payload.get("fixture_kind")
        if kind == "write_expect_ok":
            doc = payload.get("document") or {}
            result = write_smoke_evidence_artifact(doc, path=None)
            if not result.ok:
                errors.append(
                    f"{name}: expected write ok got {','.join(v.code for v in result.violations)}"
                )
            else:
                positive += 1
                if result.path and result.path.is_file():
                    result.path.unlink(missing_ok=True)
        elif kind == "write_expect_fail":
            doc = payload.get("document") or {}
            result = write_smoke_evidence_artifact(doc, path=None)
            if result.ok:
                errors.append(f"{name}: expected write fail got ok")
                if result.path and result.path.is_file():
                    result.path.unlink(missing_ok=True)
            else:
                negative += 1
        elif kind == "build_expect_fail":
            params = payload.get("build") or {}
            _, build_v = build_hermetic_smoke_evidence(**params)
            if not build_v:
                errors.append(f"{name}: expected build violations")
            else:
                negative += 1
        else:
            errors.append(f"{name}: unknown fixture_kind {kind}")
    return positive, negative, errors


def _hermetic_roundtrip_write() -> tuple[bool, str]:
    doc, build_v = build_hermetic_smoke_evidence(
        evidence_id="operator_hermetic_roundtrip",
        receipt_ids=["rcpt_op_a", "rcpt_op_b"],
        etags=["etag_op_a", "etag_op_b"],
    )
    if build_v:
        return False, "build_hermetic_smoke_evidence returned violations"
    result = write_smoke_evidence_artifact(doc)
    if not result.ok or result.path is None:
        return False, "hermetic write failed"
    try:
        flip_path, flip = write_audit_flip_candidate_file(
            result.document or doc,
            artifact_exists=True,
        )
        if flip.get("audit_flip_status") != "refused":
            return False, "hermetic flip must refuse without founder live predicates"
        if flip_path.is_file():
            flip_path.unlink()
    finally:
        if result.path.is_file():
            result.path.unlink()
    return True, "hermetic roundtrip ok"


def evaluate_live_smoke_operator(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
    *,
    run_fixtures: bool = True,
) -> SmokeOperatorResult:
    import os

    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved_mode = mode if mode is not None else detect_matrix_mode(env)
    violations: list[SmokeOperatorViolation] = []

    smoke_layer = hermetic_live_smoke_evidence_operator_check(env)
    smoke_ok = smoke_layer.ok
    if not smoke_ok:
        violations.append(
            SmokeOperatorViolation(
                code="smoke_evidence_layer_failed",
                message="PR #152 live-smoke-evidence layer must pass first",
            )
        )

    verify_path = REPO_ROOT / _VERIFY_SCRIPT_REL
    if not verify_path.is_file():
        violations.append(
            SmokeOperatorViolation(
                code="verify_script_missing",
                message=f"missing {_VERIFY_SCRIPT_REL}",
            )
        )
    cli_path = REPO_ROOT / OPERATOR_CLI_REL
    if not cli_path.is_file():
        violations.append(
            SmokeOperatorViolation(code="cli_missing", message=f"missing {OPERATOR_CLI_REL}")
        )

    pos = neg = 0
    fixture_errors: list[str] = []
    if run_fixtures:
        pos, neg, fixture_errors = run_operator_fixture_suite()
        for err in fixture_errors:
            violations.append(SmokeOperatorViolation(code="operator_fixture_failed", message=err))

    roundtrip_ok, roundtrip_detail = _hermetic_roundtrip_write()
    if not roundtrip_ok:
        violations.append(
            SmokeOperatorViolation(code="hermetic_roundtrip_failed", message=roundtrip_detail)
        )

    evidence = SmokeOperatorEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        smoke_evidence_layer_ok=smoke_ok,
        fixture_pass_count=pos,
        fixture_negative_reject_count=neg,
        hermetic_write_ok=roundtrip_ok,
        live_api_called=False,
        evidence_label="inferred",
    )

    ok = smoke_ok and not fixture_errors and roundtrip_ok and len(violations) == 0
    return SmokeOperatorResult(
        mode=resolved_mode,
        ok=ok,
        smoke_evidence_layer_ok=smoke_ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_live_smoke_operator_check(
    environ: Mapping[str, str] | None = None,
) -> SmokeOperatorResult:
    import os

    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_live_smoke_operator(detect_matrix_mode(env), env, run_fixtures=True)


def live_smoke_operator_gate_closed() -> bool:
    env = minimal_live_smoke_operator_environ()
    op = hermetic_live_smoke_operator_check(env)
    unit = evaluate_live_smoke_operator(EnvMatrixMode.HERMETIC_UNIT, env, run_fixtures=True)
    return op.ok and unit.ok


def redact_operator_summary(text: str) -> str:
    from thinkbox.kilo_live_smoke_evidence import redact_smoke_evidence_summary

    return redact_smoke_evidence_summary(text)


def live_smoke_operator_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    import os

    env: Mapping[str, str] = environ if environ is not None else os.environ
    mode = detect_matrix_mode(env)
    operator = hermetic_live_smoke_operator_check(env)
    redacted_box = redact_box_url(env.get(BOX_URL_ENV) or "") if BOX_URL_ENV in env else None
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr153_gate_id": GATE_ID,
        "pr152_layer_gate_id": SMOKE_EVIDENCE_GATE_ID,
        "detected_mode": mode.value,
        "smoke_evidence_layer": True,
        "hermetic_operator_ok": operator.ok,
        "smoke_evidence_layer_ok": operator.smoke_evidence_layer_ok,
        "fixture_paths": [p.name for p in list_fixture_paths()],
        "founder_ack_env": FOUNDER_ACK_ENV,
        "box_url_env": BOX_URL_ENV,
        "live_exec_env_ready": live_exec_env_ready(env),
        "redacted_box_url_sample": redacted_box,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "gate_closed_default": live_smoke_operator_gate_closed(),
        "verify_script": str(_VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / _VERIFY_SCRIPT_REL).is_file(),
        "operator_cli": str(OPERATOR_CLI_REL),
        "operator_cli_present": (REPO_ROOT / OPERATOR_CLI_REL).is_file(),
        "evidence_artifact_glob": str(ARTIFACT_DIR_REL / EVIDENCE_ARTIFACT_GLOB),
        "default_audit_prior": str(DEFAULT_AUDIT_PRIOR_REL),
        "audit_candidate_suffix": AUDIT_CANDIDATE_NAME_SUFFIX,
        "operator_prep_deepen_label": "live-proof-operator-prep-deepen",
        "operator_prep_deepen_gate_id": "live-proof-operator-prep-deepen",
        "hermetic_violation_codes": sorted({v.code for v in operator.violations}),
    }


def minimal_live_smoke_operator_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_live_smoke_evidence_environ())
    if extra:
        base.update(extra)
    return dict(base)
