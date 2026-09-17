"""Controlled 300-instance Experiment Arena — deterministic core + persistent control surface.

DECISION (2026-09-17): pop_arena.py IS the canonical population-arena
implementation. Rationale: existing ExperimentManager owns single-job
persistence (experiments/outcomes/lessons/artifacts/proofs/events/params)
and ChallengeArena owns adversarial probes — neither owns a 300-instance
population with live-budget separation, per-instance origin tracking, and
transfer classification. pop_arena owns ONLY that missing layer and
delegates every persisted write to ExperimentManager / MemoryStore /
ActionLedger. No duplication: pure helpers (task ids, prompts, verifier,
classifier, hashes) plus the ArenaRun control surface below.

Population: 300 logical agent/task instances across 6 task variants of the
proven exact-JSON emission family (property: parsed.answer == expected).

  Variants (50 instances each, stable task_ids arena_t{variant}_{i:03d}):
    v0 direct      — system prompt demands exactly {"answer": N}
    v1 fenced      — same demand inside one sentence of prose
    v2 prefixed    — model-style prefix "Here is the result:" then object
    v3 spaced      — extra whitespace / newlines inside the object
    v4 stringnum   — number rendered as string "N" (must still parse to N)
    v5 negative    — negative integer N (sign handling)

Separation (explicit, never mixed):
  A. POPULATION SIZE  = 300 (all persisted as experiment records)
  B. LIVE MODEL CALLS = bounded budget (default 12: 6 baseline + 6 learned)
  C. REPLAY SIZE      = 300 - live_calls (deterministic local emission)
  D. VERIFICATION     = identical property check for live and replay

Live vs replay is recorded per-instance in ``origin`` ("live" or "replay").
Replay is deterministic local emission — never represented as model execution.

Learning reuse (existing systems only):
  Phase A baseline live jobs (no lesson) -> Phase B lesson persisted via
  ExperimentManager.record_lesson + MemoryStore (provenance task_id) ->
  Phase C learned live jobs retrieve the lesson first (lesson_retrieval
  event + lesson_source parameter + ledger metadata).

Classification vocabulary (plain labels; no OutcomeClassifier class exists):
  IMPROVED / NO_MEASURABLE_IMPROVEMENT / REGRESSION / INCONCLUSIVE / FAILED

Metrics are recorded individually per instance; the Arena aggregates counts
and distributions but never invents a single "AI score".
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POPULATION_SIZE = 300
LIVE_BUDGET_DEFAULT = 12
VARIANTS_PER_FAMILY = 50

VARIANT_NAMES = ("direct", "fenced", "prefixed", "spaced", "stringnum", "negative")

EXPECTED_VALUES = {
    "direct": 7,
    "fenced": 11,
    "prefixed": 13,
    "spaced": 17,
    "stringnum": 19,
    "negative": -23,
}


def task_id_for(variant: str, index: int) -> str:
    """Stable task id: arena_t{variant}_{index:03d} (variant = 0..5)."""
    v = VARIANT_NAMES.index(variant) if variant in VARIANT_NAMES else 0
    return f"arena_t{v}_{index:03d}"


def system_prompt_for(variant: str, expected: int) -> str:
    """Deterministic task specification per variant (no answers leaked beyond the demand)."""
    obj = f'{{"answer": {expected}}}'
    if variant == "direct":
        return f"Reply with ONLY this exact JSON object and nothing else: {obj}"
    if variant == "fenced":
        return (
            "You are a precise responder. In one short sentence state you will comply, "
            f"then emit ONLY this exact JSON object and nothing else: {obj}"
        )
    if variant == "prefixed":
        return (
            f"Emit the line 'Here is the result:' followed by ONLY this exact JSON object: {obj}"
        )
    if variant == "spaced":
        return (
            "Reply with ONLY this exact JSON object (whitespace and newlines allowed) "
            f"and nothing else: {obj}"
        )
    if variant == "stringnum":
        return (
            "Reply with ONLY this exact JSON object and nothing else, "
            f'with the number as a string: {{"answer": "{expected}"}}'
        )
    if variant == "negative":
        return f"Reply with ONLY this exact JSON object and nothing else: {obj}"
    raise ValueError(f"unknown variant: {variant}")


def normalize_answer(parsed: Any) -> int | None:
    """Coerce parsed['answer'] to int when unambiguous (handles stringnum)."""
    if not isinstance(parsed, dict):
        return None
    val = parsed.get("answer")
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        try:
            return int(val.strip())
        except ValueError:
            return None
    return None


def verify_property(parsed: Any, expected: int) -> bool:
    """Objective verifier: normalized answer equals expected."""
    return normalize_answer(parsed) == expected


def extract_json(text: str) -> dict[str, Any]:
    """Local balanced-brace JSON extraction (same contract as research helper)."""
    if not text:
        return {}
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cleaned[start : i + 1])
                    except json.JSONDecodeError:
                        break
        start = cleaned.find("{", start + 1)
    return {}


def deterministic_emission(variant: str, expected: int) -> str:
    """Deterministic local emission for REPLAY instances (never a model call)."""
    if variant == "fenced":
        return f"I will comply. {{\"answer\": {expected}}}"
    if variant == "prefixed":
        return f"Here is the result: {{\"answer\": {expected}}}"
    if variant == "spaced":
        return f'{{\n  "answer" :  {expected}\n}}'
    if variant == "stringnum":
        return f'{{\"answer\": "{expected}"}}'
    return f'{{"answer": {expected}}}'


@dataclass
class ArenaTask:
    task_id: str
    variant: str
    index: int
    expected: int
    strategy: str = "baseline"
    origin: str = "replay"
    system_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "variant": self.variant,
            "index": self.index,
            "expected": self.expected,
            "strategy": self.strategy,
            "origin": self.origin,
            "system_prompt": self.system_prompt,
        }


def build_population(
    size: int = POPULATION_SIZE,
    per_variant: int = VARIANTS_PER_FAMILY,
    live_budget: int = LIVE_BUDGET_DEFAULT,
) -> list[ArenaTask]:
    """Build the full logical population with stable ids and explicit origins.

    First ``live_budget`` tasks (round-robin across variants, baseline half
    then learned half) are marked origin="live"; the rest are origin="replay".
    Strategies: first half of live = baseline, second half = learned; replay
    mirrors the same split so baseline/learned separation holds at 150/150.
    """
    if size != len(VARIANT_NAMES) * per_variant:
        raise ValueError("size must equal len(VARIANT_NAMES) * per_variant")
    if live_budget % 2:
        raise ValueError("live_budget must be even (baseline/learned split)")
    if live_budget > size:
        raise ValueError("live_budget exceeds population")
    tasks: list[ArenaTask] = []
    for vi, variant in enumerate(VARIANT_NAMES):
        for i in range(per_variant):
            tasks.append(
                ArenaTask(
                    task_id=task_id_for(variant, i),
                    variant=variant,
                    index=i,
                    expected=EXPECTED_VALUES[variant],
                    system_prompt=system_prompt_for(variant, EXPECTED_VALUES[variant]),
                )
            )
    tasks.sort(key=lambda t: t.task_id)
    by_variant: dict[str, list[ArenaTask]] = {}
    for task in tasks:
        by_variant.setdefault(task.variant, []).append(task)
    for variant_tasks in by_variant.values():
        variant_tasks.sort(key=lambda t: t.index)
    live_baseline = live_budget // 2
    live_learned = live_budget // 2
    per_variant_live_each = live_baseline // len(VARIANT_NAMES)
    if live_baseline % len(VARIANT_NAMES) or live_learned % len(VARIANT_NAMES):
        raise ValueError("live_budget must split evenly across variants")
    for variant_tasks in by_variant.values():
        for task in variant_tasks[:per_variant_live_each]:
            task.origin = "live"
            task.strategy = "baseline"
        for task in variant_tasks[per_variant_live_each : 2 * per_variant_live_each]:
            task.origin = "live"
            task.strategy = "learned"
        rest = variant_tasks[2 * per_variant_live_each :]
        half = len(rest) // 2
        for task in rest[:half]:
            task.origin = "replay"
            task.strategy = "baseline"
        for task in rest[half:]:
            task.origin = "replay"
            task.strategy = "learned"
    return tasks


@dataclass
class ArenaAggregate:
    total: int = 0
    live: int = 0
    replay: int = 0
    baseline: int = 0
    learned: int = 0
    verified: int = 0
    failed: int = 0
    errors: int = 0
    retries: int = 0
    retrieval_count: int = 0
    provenance_complete: int = 0
    artifacts_valid: int = 0
    proofs_complete: int = 0
    replay_reproducible: int = 0
    latencies: list[float] = field(default_factory=list)
    tokens: list[int] = field(default_factory=list)
    classification: str = "INCONCLUSIVE"
    classification_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "live": self.live,
            "replay": self.replay,
            "baseline": self.baseline,
            "learned": self.learned,
            "verified": self.verified,
            "failed": self.failed,
            "errors": self.errors,
            "retries": self.retries,
            "retrieval_count": self.retrieval_count,
            "provenance_complete": self.provenance_complete,
            "artifacts_valid": self.artifacts_valid,
            "proofs_complete": self.proofs_complete,
            "replay_reproducible": self.replay_reproducible,
            "latency_min": min(self.latencies) if self.latencies else None,
            "latency_max": max(self.latencies) if self.latencies else None,
            "tokens_min": min(self.tokens) if self.tokens else None,
            "tokens_max": max(self.tokens) if self.tokens else None,
            "classification": self.classification,
            "classification_reason": self.classification_reason,
        }


def classify_arena(
    baseline_success: int,
    baseline_total: int,
    learned_success: int,
    learned_total: int,
    learned_live_success: int | None = None,
    learned_live_total: int | None = None,
) -> tuple[str, str]:
    """Classify transfer with explicit ceiling-effect handling.

    Live-only evidence decides improvement (replay cannot prove transfer).
    """
    if baseline_total == 0 or learned_total == 0:
        return "INCONCLUSIVE", "empty arm"
    if learned_live_total == 0 or learned_live_total is None:
        return "INCONCLUSIVE", "no live learned evidence"
    base_rate = baseline_success / baseline_total
    learn_live_rate = learned_live_success / learned_live_total
    if base_rate >= 1.0 and learn_live_rate >= 1.0:
        return (
            "NO_MEASURABLE_IMPROVEMENT",
            "ceiling effect: baseline already 1.0 and live learned 1.0; "
            "reuse may be proven but success cannot improve",
        )
    if learn_live_rate > base_rate:
        return (
            "IMPROVED",
            f"live learned rate {learn_live_rate:.3f} exceeds baseline {base_rate:.3f}",
        )
    if learn_live_rate < base_rate:
        return (
            "REGRESSION",
            f"live learned rate {learn_live_rate:.3f} below baseline {base_rate:.3f}",
        )
    return (
        "NO_MEASURABLE_IMPROVEMENT",
        f"equal rates ({learn_live_rate:.3f}); no measured transfer",
    )


def artifact_hash(payload: dict[str, Any]) -> str:
    """Canonical SHA256 over sorted-JSON payload (no secrets ever included)."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def secrets_clean(obj: dict[str, Any]) -> bool:
    """Confirm no credential material in a persisted payload."""
    raw = json.dumps(obj)
    hits = re.findall(r"(?i)(api[_-]?key|bearer|authorization)", raw)
    if hits:
        return False
    hits = re.findall(r"(?i)(api[_-]?key|token|secret)[\"\s:]+[A-Za-z0-9_\-]{20,}", raw)
    return len(hits) == 0


ARENA_STATES = ("NOT_RUN", "CONFIGURED", "RUNNING", "COMPLETE", "BLOCKED", "FAILED")

ARENA_DB_DEFAULT = "data/thinkboxmd/db/experiments.db"
ARENA_ARTIFACTS_DEFAULT = "data/thinkboxmd/artifacts"


@dataclass
class ArenaConfig:
    population: int = POPULATION_SIZE
    per_variant: int = VARIANTS_PER_FAMILY
    live_budget: int = LIVE_BUDGET_DEFAULT
    provider: str = "openai_compat"
    model: str = "mercury-2"
    max_tokens: int = 3500
    temperature: float = 0.2
    timeout_s: int = 60

    def to_dict(self) -> dict[str, Any]:
        return {
            "population": self.population,
            "per_variant": self.per_variant,
            "live_budget": self.live_budget,
            "provider": self.provider,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout_s": self.timeout_s,
        }


class ArenaRun:
    """Persistent Arena control surface over existing ExperimentManager storage.

    State machine: NOT_RUN -> CONFIGURED -> RUNNING -> COMPLETE / BLOCKED / FAILED.
    Every transition is a persisted ``arena_event`` row in experiment_events
    (keyed to the arena control experiment) AND a lesson row carrying the
    Chronicle payload, so CONTINUITY/STATUS/AGENTS updates are mechanical.
    All 300 instances persist as experiment rows with arena_* parameters;
    the instances table below is the query index, not a second store.
    """

    CONTROL_INTENT = "arena-control-300-population"

    def __init__(
        self,
        config: ArenaConfig | None = None,
        db_path: str = ARENA_DB_DEFAULT,
        artifacts_dir: str = ARENA_ARTIFACTS_DEFAULT,
    ) -> None:
        self.config = config or ArenaConfig()
        self.db_path = db_path
        self.artifacts_dir = Path(artifacts_dir)
        self._lock = threading.Lock()

    # -- storage helpers (same SQLite file as ExperimentManager) -------------

    def _connect(self) -> sqlite3.Connection:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _utc(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # -- lifecycle -----------------------------------------------------------

    def state(self) -> dict[str, Any]:
        """Current Arena state rebuilt from storage (no memory)."""
        from thinkbox.experiment import ExperimentManager

        ExperimentManager(db_path=self.db_path, artifacts_dir=str(self.artifacts_dir))
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT experiment_id FROM experiments WHERE intent = ? ORDER BY timestamp DESC LIMIT 1",
                (self.CONTROL_INTENT,),
            ).fetchone()
            if not row:
                return {"state": "NOT_RUN", "control_experiment_id": "", "transitions": []}
            eid = row["experiment_id"]
            events = [
                dict(r)
                for r in conn.execute(
                    "SELECT event_type, data, timestamp FROM experiment_events "
                    "WHERE experiment_id = ? AND event_type LIKE 'arena_%' ORDER BY id",
                    (eid,),
                ).fetchall()
            ]
            current = "CONFIGURED"
            for ev in events:
                if ev["event_type"] == "arena_started":
                    current = "RUNNING"
                elif ev["event_type"] == "arena_completed":
                    current = "COMPLETE"
                elif ev["event_type"] == "arena_blocked":
                    current = "BLOCKED"
                elif ev["event_type"] == "arena_failed":
                    current = "FAILED"
            params = {
                r["name"]: r["value"]
                for r in conn.execute(
                    "SELECT name, value FROM experiment_parameters WHERE experiment_id = ?",
                    (eid,),
                ).fetchall()
            }
            count = conn.execute(
                "SELECT COUNT(*) c FROM experiment_parameters WHERE name = 'arena_task_id'"
            ).fetchone()["c"]
            return {
                "state": current,
                "control_experiment_id": eid,
                "config": json.loads(params.get("arena_config", "{}") or "{}"),
                "transitions": [
                    {"event": e["event_type"], "timestamp": e["timestamp"]} for e in events
                ],
                "instance_count": count,
            }
        finally:
            conn.close()

    def configure(self, agent_id: str = "kilo-arena") -> str:
        """Persist population plan as the control experiment (NOT_RUN -> CONFIGURED)."""
        from thinkbox.experiment import ExperimentManager

        mgr = ExperimentManager(db_path=self.db_path, artifacts_dir=str(self.artifacts_dir))
        tasks = build_population(
            size=self.config.population,
            per_variant=self.config.per_variant,
            live_budget=self.config.live_budget,
        )
        mgr.create_session(agent_id=agent_id, metadata={"role": "arena-control"})
        exp = mgr.create_experiment(
            intent=self.CONTROL_INTENT,
            hypothesis="persistent knowledge transfers across task variants",
            parameters={"population": self.config.population, "live_budget": self.config.live_budget},
            agent_id=agent_id,
            execution_mode="upstash-box",
        )
        mgr.add_parameter(exp.experiment_id, "arena_config", json.dumps(self.config.to_dict()), confidence=1.0)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO experiment_events (experiment_id, event_type, data, timestamp) VALUES (?, ?, ?, ?)",
                    (exp.experiment_id, "arena_configured", json.dumps(self.config.to_dict()), self._utc()),
                )
                conn.commit()
            finally:
                conn.close()
        return exp.experiment_id

    def record_instance(
        self,
        task: ArenaTask,
        experiment_id: str,
        valid: bool,
        latency_s: float | None = None,
        tokens: int | None = None,
        lesson_source: str = "",
        retrieval_proven: bool = False,
        errors: int = 0,
        retries: int = 0,
        artifact_sha256: str = "",
    ) -> None:
        """Persist one logical instance: experiment row params + outcome + events."""
        from thinkbox.experiment import ExperimentManager

        mgr = ExperimentManager(db_path=self.db_path, artifacts_dir=str(self.artifacts_dir))
        mgr.add_parameter(experiment_id, "arena_task_id", task.task_id, confidence=1.0)
        mgr.add_parameter(experiment_id, "arena_variant", task.variant, confidence=1.0)
        mgr.add_parameter(experiment_id, "arena_strategy", task.strategy, confidence=1.0)
        mgr.add_parameter(experiment_id, "arena_origin", task.origin, confidence=1.0)
        if lesson_source:
            mgr.add_parameter(experiment_id, "lesson_source", lesson_source, confidence=0.9)
        outcome = {
            "property_valid": valid,
            "origin": task.origin,
            "strategy": task.strategy,
            "variant": task.variant,
            "artifact_sha256": artifact_sha256,
            "latency_s": latency_s,
            "tokens": tokens,
            "errors": errors,
            "retries": retries,
            "retrieval_proven": retrieval_proven,
        }
        assert secrets_clean({"outcome": {k: v for k, v in outcome.items() if k != "artifact_sha256"}} | {"sha": artifact_sha256[:12]})
        mgr.record_outcome(experiment_id, outcome, 1.0 if valid else 0.4, "TEST_VERIFIED" if valid else "FAILED")

    def transition(self, control_experiment_id: str, event: str, data: dict[str, Any]) -> None:
        """Persist a lifecycle transition + Chronicle lesson row."""
        if event not in ("arena_started", "arena_completed", "arena_blocked", "arena_failed"):
            raise ValueError(f"unknown arena event: {event}")
        from thinkbox.experiment import ExperimentManager

        mgr = ExperimentManager(db_path=self.db_path, artifacts_dir=str(self.artifacts_dir))
        mgr.db.save_event(control_experiment_id, event, data)
        mgr.record_lesson(
            control_experiment_id,
            f"Arena {event}: {json.dumps(data, sort_keys=True)[:300]}",
            [],
            "",
        )

    def aggregate(self) -> ArenaAggregate:
        """Rebuild population metrics from storage (no memory).

        Deduplicates defensively: at most one outcome row per experiment
        (latest id wins) so JOIN fanout can never inflate counts.
        """
        conn = self._connect()
        try:
            rows = [
                dict(r)
                for r in conn.execute(
                    "SELECT e.experiment_id, "
                    "(SELECT o.outcome_data FROM outcomes o WHERE o.experiment_id = e.experiment_id "
                    "ORDER BY o.id DESC LIMIT 1) AS outcome_data FROM experiments e "
                    "WHERE EXISTS (SELECT 1 FROM experiment_parameters p WHERE p.experiment_id = e.experiment_id "
                    "AND p.name = 'arena_task_id')"
                ).fetchall()
            ]
            agg = ArenaAggregate(total=len(rows))
            for r in rows:
                try:
                    out = json.loads(r["outcome_data"] or "{}")
                except Exception:
                    out = {}
                if out.get("origin") == "live":
                    agg.live += 1
                else:
                    agg.replay += 1
                if out.get("strategy") == "learned":
                    agg.learned += 1
                else:
                    agg.baseline += 1
                if out.get("property_valid") is True:
                    agg.verified += 1
                else:
                    agg.failed += 1
                agg.errors += int(out.get("errors", 0) or 0)
                agg.retries += int(out.get("retries", 0) or 0)
                if out.get("retrieval_proven"):
                    agg.retrieval_count += 1
                    agg.provenance_complete += 1
                if out.get("artifact_sha256"):
                    agg.artifacts_valid += 1
                    agg.proofs_complete += 1
                    agg.replay_reproducible += 1
                if out.get("latency_s") is not None:
                    agg.latencies.append(float(out["latency_s"]))
                if out.get("tokens") is not None:
                    agg.tokens.append(int(out["tokens"]))
            base_ok = sum(
                1
                for r in rows
                if (json.loads(r["outcome_data"] or "{}") or {}).get("strategy") != "learned"
                and (json.loads(r["outcome_data"] or "{}") or {}).get("property_valid") is True
            )
            base_n = sum(
                1
                for r in rows
                if (json.loads(r["outcome_data"] or "{}") or {}).get("strategy") != "learned"
            )
            learn_live_ok = sum(
                1
                for r in rows
                if (json.loads(r["outcome_data"] or "{}") or {}).get("strategy") == "learned"
                and (json.loads(r["outcome_data"] or "{}") or {}).get("origin") == "live"
                and (json.loads(r["outcome_data"] or "{}") or {}).get("property_valid") is True
            )
            learn_live_n = sum(
                1
                for r in rows
                if (json.loads(r["outcome_data"] or "{}") or {}).get("strategy") == "learned"
                and (json.loads(r["outcome_data"] or "{}") or {}).get("origin") == "live"
            )
            learn_ok = sum(
                1
                for r in rows
                if (json.loads(r["outcome_data"] or "{}") or {}).get("strategy") == "learned"
                and (json.loads(r["outcome_data"] or "{}") or {}).get("property_valid") is True
            )
            learn_n = agg.learned
            cls, reason = classify_arena(base_ok, base_n, learn_ok, learn_n, learn_live_ok, learn_live_n)
            agg.classification, agg.classification_reason = cls, reason
            return agg
        finally:
            conn.close()
