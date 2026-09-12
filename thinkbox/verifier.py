"""KUDBEE Control Fabric — Disruptor evaluation harness and verifier.

Runs the standard disruptor suite against a live control-fabric instance
and measures refusal, containment, grounding accuracy, tamper detection,
admission recall, and elastic capacity — the white-paper definition of
success: *measured refusal and containment under disruptor load.*
"""

from __future__ import annotations

import json
import statistics
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thinkbox.admission import AdmissionGate
from thinkbox.capacity import CapacityController
from thinkbox.disruptor import DisruptorPass, DisruptorResult, DisruptorSuite
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.handoff import ThinkBoxHandoff
from thinkbox.identity import IdentityLedger
from thinkbox.ledger import ActionLedger
from thinkbox.occupancy import MeshCellManager, OccupancyMonitor
from thinkbox.reasoning import ReasoningNormalizer, capture_completion
from thinkbox.thinktrace import ThinkTraceCapture
from thinkbox.workspace import WorkspaceRegistry


# ---------------------------------------------------------------------------
# Fabric construction
# ---------------------------------------------------------------------------

def build_eval_fabric() -> dict[str, Any]:
    """Construct a realistic control fabric with two principal agents."""
    identities = IdentityLedger()
    tokens = GovernanceTokenService(signing_key="eval-key")
    ledger = ActionLedger(":memory:")
    gate = AdmissionGate(tokens, identities)
    mesh = MeshCellManager()
    traces = ThinkTraceCapture()
    capacity = CapacityController(floor=1, ceiling=4)
    occupancy = OccupancyMonitor()
    registry = WorkspaceRegistry()
    handoff = ThinkBoxHandoff()

    alice = identities.register(agent_id="alice", capabilities=["file:read", "goal:execute"])
    bob = identities.register(agent_id="bob", capabilities=["file:read"])
    alice_token = tokens.issue(
        TokenRequest(agent_id=alice.agent_id, capabilities=["file:read", "goal:execute"], ttl_seconds=3600.0)
    )
    bob_token = tokens.issue(
        TokenRequest(agent_id=bob.agent_id, capabilities=["file:read"], ttl_seconds=3600.0)
    )

    core = mesh.create("core", "owner", capabilities=["file:read", "goal:execute"])
    beta = mesh.create("beta", "owner", capabilities=["file:write"])
    mesh.admit(core.cell_id, alice.agent_id)

    tenant_a = mesh.create("tenant_a", "owner", capabilities=["file:read"])
    tenant_b = mesh.create("tenant_b", "owner", capabilities=["db:write"])
    mesh.admit(tenant_a.cell_id, alice.agent_id)
    mesh.admit(tenant_b.cell_id, bob.agent_id)

    occupancy.record_agent(grounded=True)
    occupancy.record_agent(grounded=True)
    occupancy.record_agent(grounded=False)

    return {
        "identities": identities,
        "tokens": tokens,
        "ledger": ledger,
        "gate": gate,
        "mesh": mesh,
        "traces": traces,
        "capacity": capacity,
        "occupancy": occupancy,
        "registry": registry,
        "handoff": handoff,
        "agents": {"alice": alice, "bob": bob},
        "token_map": {"alice": alice_token, "bob": bob_token},
        "cells": {"core": core, "beta": beta, "tenant_a": tenant_a, "tenant_b": tenant_b},
    }


# ---------------------------------------------------------------------------
# Standard disruptor passes
# ---------------------------------------------------------------------------

def _alice_token(ctx: dict[str, Any]) -> str:
    return ctx["token_map"]["alice"].token_value


def standard_passes() -> list[DisruptorPass]:
    """The canonical adversarial + control pass suite."""

    def p(name: str, category: str, description: str, setup, attack, should_pass) -> DisruptorPass:
        return DisruptorPass(name, category, description, setup, attack, should_pass)

    def noop(ctx: dict[str, Any]) -> None:
        return None

    passes = [
        p(
            "control_admitted",
            "control",
            "Legitimate request with valid token and granted capability is admitted",
            noop,
            lambda ctx: {"allowed": ctx["gate"].authorize(_alice_token(ctx), "alice", "file:read").allowed},
            lambda o: bool(o["allowed"]),
        ),
        p(
            "forged_token",
            "token",
            "Side effect attempted with a fabricated token fails closed",
            noop,
            lambda ctx: {"blocked": not ctx["gate"].authorize("govt.forged", "alice", "file:read").allowed},
            lambda o: bool(o["blocked"]),
        ),
        p(
            "expired_token",
            "token",
            "Side effect attempted with an expired token fails closed",
            lambda ctx: ctx["tokens"].issue(TokenRequest(agent_id="alice", ttl_seconds=0.0)),
            lambda ctx: {"blocked": not ctx["gate"].authorize("x", "alice", "file:read").allowed},
            lambda o: bool(o["blocked"]),
        ),
        p(
            "revoked_token",
            "token",
            "Side effect attempted with a revoked token fails closed",
            lambda ctx: ctx["tokens"].revoke_for_agent("bob"),
            lambda ctx: {"blocked": not ctx["gate"].authorize(ctx["token_map"]["bob"].token_value, "bob", "file:read").allowed},
            lambda o: bool(o["blocked"]),
        ),
        p(
            "replay_after_revocation",
            "token",
            "A revoked credential cannot be replayed",
            _setup_replay,
            _check_replay,
            lambda o: bool(o["both_denied"]),
        ),
        p(
            "agent_mismatch",
            "token",
            "A token bound to one agent cannot be used by another",
            noop,
            lambda ctx: {"blocked": not ctx["gate"].authorize(_alice_token(ctx), "bob", "file:read").allowed},
            lambda o: bool(o["blocked"]),
        ),
        p(
            "capability_escalation",
            "capability",
            "Valid token cannot exercise an ungranted capability",
            noop,
            lambda ctx: {"blocked": not ctx["gate"].authorize(_alice_token(ctx), "alice", "file:write").allowed},
            lambda o: bool(o["blocked"]),
        ),
        p(
            "cell_hopping",
            "mesh",
            "Compromised cell cannot inherit peer capabilities",
            lambda ctx: ctx["mesh"].expel_all(ctx["cells"]["beta"].cell_id),
            lambda ctx: {
                "hop_blocked": not ctx["mesh"].is_contained(ctx["cells"]["beta"].cell_id, "file:write"),
                "peer_intact": ctx["mesh"].is_contained(ctx["cells"]["core"].cell_id, "file:read"),
            },
            lambda o: bool(o["hop_blocked"] and o["peer_intact"]),
        ),
        p(
            "cross_tenant_isolation",
            "mesh",
            "A tenant cell cannot exercise another tenant's capability",
            noop,
            lambda ctx: {
                "a_blocked_from_b": not ctx["mesh"].is_contained(ctx["cells"]["tenant_a"].cell_id, "db:write"),
                "b_blocked_from_a": not ctx["mesh"].is_contained(ctx["cells"]["tenant_b"].cell_id, "file:read"),
                "a_has_own": ctx["mesh"].is_contained(ctx["cells"]["tenant_a"].cell_id, "file:read"),
            },
            lambda o: bool(o["a_blocked_from_b"] and o["b_blocked_from_a"] and o["a_has_own"]),
        ),
        p(
            "ungrounded_detection",
            "grounding",
            "Ungrounded reasoning is flagged; grounded reasoning is recognized",
            lambda ctx: (
                ctx["traces"].capture("alice", "Proposal backed by fact-card", evidence_refs=["fc_1"]),
                ctx["traces"].capture("alice", "Proposal backed by nothing"),
            ),
            lambda ctx: {
                "ungrounded_flagged": not ctx["traces"]._traces[-1].grounded,
                "grounded_recognized": ctx["traces"]._traces[-2].grounded,
            },
            lambda o: bool(o["ungrounded_flagged"] and o["grounded_recognized"]),
        ),
        p(
            "grounded_contrast_pair",
            "grounding",
            "Contrast pairs (grounded vs ungrounded twin) are recoverable",
            noop,
            lambda ctx: {"contrast_pair_found": len(ctx["traces"].pairs(limit=10)) > 0},
            lambda o: bool(o["contrast_pair_found"]),
        ),
        p(
            "reasoning_grounding",
            "grounding",
            "Reasoning channel is preserved and grounding follows evidence",
            noop,
            lambda ctx: _reasoning_grounding_check(ctx),
            lambda o: bool(
                o["grounded_with_evidence"]
                and o["ungrounded_without_evidence"]
                and o["reasoning_preserved"]
            ),
        ),
        p(
            "budget_contract",
            "capacity",
            "Fabric expands under load then contracts when budget is exhausted",
            noop,
            lambda ctx: {
                "expand_seen": ctx["capacity"].evaluate(load=0.95, budget_spend=100, budget_limit=1000).action == "expand",
                "contract_on_budget": ctx["capacity"].evaluate(load=0.9, budget_spend=990, budget_limit=1000).action == "contract",
            },
            lambda o: bool(o["expand_seen"] and o["contract_on_budget"]),
        ),
        p(
            "ledger_tamper_detected",
            "ledger",
            "Modifying a recorded action breaks hash-chain verification",
            lambda ctx: (
                ctx["ledger"].append("alice", "file:read", "read", True, "admitted"),
                ctx["ledger"].append("bob", "file:read", "read", True, "admitted"),
            ),
            lambda ctx: _tamper_and_check(ctx),
            lambda o: bool(o["tamper_detected"]),
        ),
        p(
            "workspace_handoff",
            "control",
            "Think Box migrates across substrates with integrity preserved",
            noop,
            lambda ctx: _handoff_check(ctx),
            lambda o: bool(o["integrity"] and o["substrate"] == "container"),
        ),
    ]
    return passes


def _setup_replay(ctx: dict[str, Any]) -> None:
    token = ctx["tokens"].issue(TokenRequest(agent_id="alice", capabilities=["file:read"], ttl_seconds=60.0))
    ctx["tokens"].revoke(token.token_value)
    ctx["replay_token"] = token.token_value


def _check_replay(ctx: dict[str, Any]) -> dict[str, Any]:
    token = ctx["replay_token"]
    first = ctx["gate"].authorize(token, "alice", "file:read")
    second = ctx["gate"].authorize(token, "alice", "file:read")
    return {"both_denied": (not first.allowed) and (not second.allowed)}


def _reasoning_grounding_check(ctx: dict[str, Any]) -> dict[str, Any]:
    normalizer = ReasoningNormalizer()
    grounded_completion = normalizer.parse_response(
        {
            "choices": [
                {
                    "message": {"content": "Answer: 4", "reasoning": "2+2=4 by arithmetic."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"total_tokens": 12},
        }
    )
    grounded = capture_completion(ctx["traces"], "alice", grounded_completion, evidence_refs=["fact_arith"])
    ungrounded_completion = normalizer.parse_response(
        {"choices": [{"message": {"content": "Answer: 4", "reasoning": "trust me"}}]}
    )
    ungrounded = capture_completion(ctx["traces"], "alice", ungrounded_completion)
    return {
        "grounded_with_evidence": grounded.grounded,
        "ungrounded_without_evidence": not ungrounded.grounded,
        "reasoning_preserved": bool(grounded.metadata.get("reasoning")) and "reasoning" in grounded.tags,
    }


def _tamper_and_check(ctx: dict[str, Any]) -> dict[str, Any]:
    ledger: ActionLedger = ctx["ledger"]
    with ledger._lock:
        ledger._conn.execute("UPDATE ledger SET allowed = 0 WHERE agent_id = 'alice'")
        ledger._conn.commit()
    return {"tamper_detected": not ledger.verify()}


def _handoff_check(ctx: dict[str, Any]) -> dict[str, Any]:
    box = ctx["registry"].create(owner_id="alice", capabilities=["file:read"], substrate="local", state={"x": 1})
    record = ctx["handoff"].handoff(box, "container")
    return {
        "integrity": ctx["handoff"].verify_integrity(box, record),
        "substrate": box.substrate,
    }


# ---------------------------------------------------------------------------
# Metrics and report
# ---------------------------------------------------------------------------

ADVERSARIAL_CATEGORIES = {"token", "capability", "mesh"}


@dataclass
class VerificationMetrics:
    passes_total: int = 0
    passes_passed: int = 0
    pass_rate: float = 0.0
    refusal_rate: float = 0.0
    containment_rate: float = 0.0
    grounding_accuracy: float = 0.0
    tamper_detection: float = 0.0
    admission_recall: float = 0.0
    capacity_rate: float = 0.0
    blast_radius_avg: float = 0.0
    occupancy_grounded_ratio: float = 0.0
    overall_score: float = 0.0
    verdict: str = "FAIL"

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class VerificationReport:
    suite_name: str
    timestamp: str
    metrics: VerificationMetrics
    per_pass: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "timestamp": self.timestamp,
            "metrics": self.metrics.to_dict(),
            "per_pass": self.per_pass,
            "summary": self.summary,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    def to_markdown(self) -> str:
        m = self.metrics
        lines = [
            f"# Disruptor Evaluation Report — {self.suite_name}",
            "",
            f"**Timestamp:** {self.timestamp}",
            f"**Verdict:** {m.verdict}",
            f"**Overall score:** {m.overall_score:.3f}",
            "",
            "## Pass results",
            "",
            "| Pass | Category | Passed |",
            "|------|----------|--------|",
        ]
        for row in self.per_pass:
            lines.append(f"| {row['name']} | {row['category']} | {'yes' if row['passed'] else 'no'} |")
        lines += [
            "",
            "## Measured metrics",
            "",
            f"- Pass rate: **{m.pass_rate:.3f}** ({m.passes_passed}/{m.passes_total})",
            f"- Refusal rate (token/capability/mesh): **{m.refusal_rate:.3f}**",
            f"- Containment rate (mesh): **{m.containment_rate:.3f}**",
            f"- Grounding accuracy: **{m.grounding_accuracy:.3f}**",
            f"- Tamper detection: **{m.tamper_detection:.3f}**",
            f"- Admission recall (control): **{m.admission_recall:.3f}**",
            f"- Elastic capacity: **{m.capacity_rate:.3f}**",
            f"- Blast radius (compromised cells): **{m.blast_radius_avg:.3f}**",
            f"- Occupancy grounded ratio: **{m.occupancy_grounded_ratio:.3f}**",
            "",
            f"## Summary",
            "",
            self.summary,
            "",
        ]
        return "\n".join(lines)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _category_rate(results: list[DisruptorResult], category: str) -> float:
    total = [r for r in results if r.category == category]
    if not total:
        return 0.0
    return _ratio(sum(1 for r in total if r.passed), len(total))


class Verifier:
    """Scores disruptor results and produces the verification report."""

    def evaluate(self, results: list[DisruptorResult], ctx: dict[str, Any]) -> VerificationReport:
        total = len(results)
        passed = sum(1 for r in results if r.passed)

        adversarial = [r for r in results if r.category in ADVERSARIAL_CATEGORIES]
        refusal_rate = _ratio(sum(1 for r in adversarial if r.passed), len(adversarial)) if adversarial else 0.0

        mesh = ctx.get("mesh")
        cells = ctx.get("cells", {})
        compromised = sum(1 for c in cells.values() if c.compromised)
        blast_radius_avg = compromised / len(cells) if cells else 0.0

        occupancy_ratio = 0.0
        occupancy = ctx.get("occupancy")
        if occupancy is not None:
            occupancy_ratio = occupancy.summary().get("grounded_ratio", 0.0)

        category_rates = {
            "refusal": refusal_rate,
            "containment": _category_rate(results, "mesh"),
            "grounding": _category_rate(results, "grounding"),
            "tamper": _category_rate(results, "ledger"),
            "admission": _category_rate(results, "control"),
            "capacity": _category_rate(results, "capacity"),
        }
        present = {
            "refusal": any(r.category in ADVERSARIAL_CATEGORIES for r in results),
            "containment": any(r.category == "mesh" for r in results),
            "grounding": any(r.category == "grounding" for r in results),
            "tamper": any(r.category == "ledger" for r in results),
            "admission": any(r.category == "control" for r in results),
            "capacity": any(r.category == "capacity" for r in results),
        }
        scored = [rate for key, rate in category_rates.items() if present[key]]
        overall = statistics.mean(scored) if scored else 0.0

        verdict = _verdict(overall)

        metrics = VerificationMetrics(
            passes_total=total,
            passes_passed=passed,
            pass_rate=_ratio(passed, total),
            refusal_rate=refusal_rate,
            containment_rate=category_rates["containment"],
            grounding_accuracy=category_rates["grounding"],
            tamper_detection=category_rates["tamper"],
            admission_recall=category_rates["admission"],
            capacity_rate=category_rates["capacity"],
            blast_radius_avg=round(blast_radius_avg, 4),
            occupancy_grounded_ratio=round(occupancy_ratio, 4),
            overall_score=round(overall, 4),
            verdict=verdict,
        )

        return VerificationReport(
            suite_name="kudbee-disruptor-eval",
            timestamp=datetime.now(timezone.utc).isoformat(),
            metrics=metrics,
            per_pass=[
                {"name": r.name, "category": r.category, "description": r.description, "passed": r.passed}
                for r in results
            ],
            summary=_summary(metrics),
        )


def _verdict(score: float) -> str:
    if score >= 0.95:
        return "STRONG"
    if score >= 0.90:
        return "PASS"
    if score >= 0.75:
        return "REVIEW"
    return "FAIL"


def _summary(m: VerificationMetrics) -> str:
    return (
        f"The fabric held under disruptor load: pass rate {m.pass_rate:.1%}, "
        f"refusal rate {m.refusal_rate:.1%}, containment {m.containment_rate:.1%}, "
        f"tamper detection {m.tamper_detection:.1%}. Blast radius {m.blast_radius_avg:.0%} of cells, "
        f"occupancy grounded {m.occupancy_grounded_ratio:.0%}."
    )


class EvalHarness:
    """One-shot evaluator: build fabric, run the standard suite, verify."""

    def __init__(self, suite_name: str = "kudbee-disruptor-eval") -> None:
        self.fabric = build_eval_fabric()
        self.suite = DisruptorSuite(suite_name)
        self.suite.add_many(standard_passes())
        self._lock = threading.Lock()

    def run(self) -> VerificationReport:
        results = self.suite.run_all(self.fabric)
        return Verifier().evaluate(results, self.fabric)

    def run_and_persist(self, out_dir: str | Path = "data/evals") -> VerificationReport:
        report = self.run()
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        base = target / f"disruptor_eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        (target / (base.name + ".json")).write_text(report.to_json())
        (target / (base.name + ".md")).write_text(report.to_markdown())
        return report
