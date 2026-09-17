"""Controlled 300-instance Experiment Arena — deterministic core.

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
from dataclasses import dataclass, field
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
