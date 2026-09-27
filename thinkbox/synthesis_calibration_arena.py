"""
Synthesis Calibration Arena — pre-registered research experiment (PR #264).

QUESTION: When multiple specialized agents disagree, does the confidence-weighted
consensus synthesis shipped in thinkbox.multi_box_orchestration.SynthesisEngine
produce better-calibrated and/or more accurate answers than naive unweighted
majority voting, at IDENTICAL total agent-call budget?

This follows the same falsifiable, budget-matched, honestly-reported methodology
as the existing "Arena v2" experiments (see
data/thinkboxmd/artifacts/arena2_proof_20260917.json): a hypothesis and an
improvement threshold are fixed BEFORE any run, and results are classified
honestly even when they show no improvement or a regression.

RELATED WORK (cite properly before any publication or grant submission — this
module does not claim novelty over these, it tests a specific implementation
against their established baselines):
  - Du et al. 2023, "Improving Factuality and Reasoning in Language Models
    through Multiagent Debate"
  - Wang et al. 2022, "Self-Consistency Improves Chain of Thought Reasoning
    in Language Models" (naive majority voting baseline)
  - Guo et al. 2017, "On Calibration of Modern Neural Networks" (Brier score /
    calibration as the metric, not just accuracy)
  - Condorcet Jury Theorem (classical social choice theory; motivates why
    majority voting can beat individuals, and its known failure conditions)

PRE-REGISTERED HYPOTHESIS (fixed before any run in this module; do not edit
after seeing results):
  H1: Confidence-weighted synthesis achieves a lower Brier score (better
      calibration) than naive majority voting, on the same underlying agent
      responses (paired design), at matched total agent-call budget.

PRE-REGISTERED IMPROVEMENT THRESHOLD (fixed before any run):
  Brier score reduction > 0.05 AND the paired bootstrap 95% CI of the
  difference excludes zero. Anything else is classified
  NO_MEASURABLE_IMPROVEMENT. A positive Brier delta beyond -0.05 (i.e.
  synthesis calibrates worse) with a CI excluding zero is classified WORSE.

NULL HYPOTHESIS:
  No measurable difference in calibration or accuracy between naive majority
  voting and confidence-weighted synthesis.

EVIDENCE LEVEL: Every result this module produces is SIMULATED. Agent
responses come from a seeded synthetic response generator, not real model
calls (see SeededAgentSimulator). This module answers "does the AGGREGATION
METHOD in SynthesisEngine behave as intended," not "how good are real LLMs."
A LIVE variant (real model calls) is a separate, explicitly gated future step
— see run_live() below, which refuses to fabricate results.
"""

import hashlib
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from thinkbox.multi_box_orchestration import KnowledgeFabric, SynthesisEngine


# ============================================================================
# PRE-REGISTERED CONSTANTS — fixed before any run; changing these after
# seeing results would invalidate the experiment.
# ============================================================================

PRE_REGISTERED_HYPOTHESIS = (
    "Confidence-weighted synthesis achieves a lower Brier score (better "
    "calibration) than naive majority voting, on the same underlying agent "
    "responses, at matched total agent-call budget."
)

# Brier score reduction required to call it IMPROVED, plus non-overlapping CI.
IMPROVEMENT_THRESHOLD_BRIER_DELTA = 0.05

NO_CLAIMS = [
    "no claim about real model intelligence or capability",
    "no live model calls in the hermetic run",
    "no claim of novelty over cited prior work",
    "no claim this generalizes beyond the synthetic task families below",
]


class TaskFamily(Enum):
    COMPUTE = "compute"
    DISTRACTOR = "distractor"
    MULTIFIELD = "multifield"


@dataclass(frozen=True)
class SimulatedAgentProfile:
    """
    Fixed, documented assumptions about simulated agent behavior per task
    family. These are NOT measured from real models — they are arbitrary,
    reasonable values chosen to give the experiment room to show an effect
    in either direction (agents are imperfectly calibrated, not perfectly
    accurate, not random noise).
    """
    accuracy: float          # true P(correct) for one simulated agent call
    confidence_noise: float  # stddev of noise added to stated confidence


# Fixed before any run. Do not tune after seeing results.
AGENT_PROFILES: Dict[TaskFamily, SimulatedAgentProfile] = {
    TaskFamily.COMPUTE: SimulatedAgentProfile(accuracy=0.72, confidence_noise=0.12),
    TaskFamily.DISTRACTOR: SimulatedAgentProfile(accuracy=0.55, confidence_noise=0.18),
    TaskFamily.MULTIFIELD: SimulatedAgentProfile(accuracy=0.64, confidence_noise=0.15),
}


# ============================================================================
# 1. TASK GENERATION (deterministic given a seed)
# ============================================================================

@dataclass
class SyntheticTask:
    task_id: str
    family: TaskFamily
    ground_truth: int


def generate_task_set(n_tasks: int, seed: int) -> List[SyntheticTask]:
    """Deterministic task set: same seed always produces the same tasks."""
    rng = random.Random(seed)
    families = list(TaskFamily)
    tasks = []
    for i in range(n_tasks):
        family = families[i % len(families)]
        ground_truth = rng.randint(1, 999)
        tasks.append(SyntheticTask(task_id=f"task_{i:04d}", family=family, ground_truth=ground_truth))
    return tasks


# ============================================================================
# 2. SEEDED AGENT SIMULATOR (stand-in for real model calls — SIMULATED only)
# ============================================================================

@dataclass
class AgentResponse:
    task_id: str
    answer: int
    confidence: float  # agent's stated confidence, 0.0-1.0
    correct: bool


class SeededAgentSimulator:
    """
    Deterministic stand-in for a real model call. Given the same
    (task, response_index, seed), always returns the same response.

    This is the hermetic substitute for calling Mercury-2 or any other
    provider. It exists so the experiment harness itself (task generation,
    aggregation logic, statistics) can be CODE_COMPLETE and TEST_VERIFIED
    without spending API budget. Swapping this for a real provider call is
    the entire scope of a future LIVE run — see run_live().
    """

    def __init__(self, seed: int):
        self.seed = seed

    def _rng_for(self, task_id: str, response_index: int) -> random.Random:
        key = f"{self.seed}:{task_id}:{response_index}"
        digest = hashlib.sha256(key.encode()).hexdigest()
        return random.Random(int(digest[:16], 16))

    def respond(self, task: SyntheticTask, response_index: int) -> AgentResponse:
        rng = self._rng_for(task.task_id, response_index)
        profile = AGENT_PROFILES[task.family]

        is_correct = rng.random() < profile.accuracy
        if is_correct:
            answer = task.ground_truth
        else:
            # Wrong answer: deviates from ground truth in either direction
            # with a randomized sign. A one-sided offset (always +N) would
            # make the correct answer identifiable as "the minimum value"
            # whenever exactly one response is correct, which would silently
            # advantage any aggregation rule that tie-breaks on lowest value
            # — an experimental confound, not a real synthesis-engine effect.
            offset = rng.randint(1, 50)
            sign = rng.choice([-1, 1])
            answer = task.ground_truth + sign * offset
            if answer == task.ground_truth:
                answer += 1  # guard against sign*offset landing on 0

        noise = rng.gauss(0, profile.confidence_noise)
        stated_confidence = profile.accuracy + noise
        stated_confidence = max(0.05, min(0.99, stated_confidence))

        return AgentResponse(
            task_id=task.task_id,
            answer=answer,
            confidence=round(stated_confidence, 4),
            correct=is_correct,
        )


# ============================================================================
# 3. AGGREGATION CONDITIONS
# ============================================================================

class Condition(Enum):
    SINGLE_AGENT = "single_agent"
    NAIVE_MAJORITY_VOTE = "naive_majority_vote"
    CONFIDENCE_WEIGHTED_SYNTHESIS = "confidence_weighted_synthesis"


@dataclass
class ConditionResult:
    task_id: str
    predicted_answer: int
    predicted_confidence: float
    correct: bool


def evaluate_single_agent(responses: List[AgentResponse], task: SyntheticTask) -> ConditionResult:
    """Baseline: use only the first of the N responses. No aggregation."""
    r = responses[0]
    return ConditionResult(
        task_id=task.task_id,
        predicted_answer=r.answer,
        predicted_confidence=r.confidence,
        correct=r.answer == task.ground_truth,
    )


def evaluate_naive_majority_vote(responses: List[AgentResponse], task: SyntheticTask) -> ConditionResult:
    """Unweighted majority vote; confidence = fraction of agents agreeing."""
    counts: Dict[int, int] = {}
    for r in responses:
        counts[r.answer] = counts.get(r.answer, 0) + 1

    best_answer = max(counts.items(), key=lambda kv: (kv[1], -kv[0]))[0]
    vote_share = counts[best_answer] / len(responses)

    return ConditionResult(
        task_id=task.task_id,
        predicted_answer=best_answer,
        predicted_confidence=vote_share,
        correct=best_answer == task.ground_truth,
    )


def evaluate_confidence_weighted_synthesis(
    responses: List[AgentResponse], task: SyntheticTask
) -> ConditionResult:
    """
    Runs the ACTUAL shipped SynthesisEngine (PR #263) against the same
    underlying responses used by the other two conditions. This tests the
    real production aggregation code, not a reimplementation of it.
    """
    fabric = KnowledgeFabric()
    box_ids = []
    for i, r in enumerate(responses):
        box_id = f"{task.task_id}_agent_{i}"
        box_ids.append(box_id)
        fabric.add_knowledge(
            content={"answer": r.answer, "topic": task.task_id},
            source_boxes=[box_id],
            evidence_level="SIMULATED",
            confidence=r.confidence,
        )

    synthesis = SynthesisEngine(fabric)
    result = synthesis.synthesize_findings(box_ids, task.task_id)

    if result["consensus_findings"]:
        best = max(result["consensus_findings"], key=lambda f: f["agreements"])
        predicted_answer = best["content"]["answer"]
        predicted_confidence = best["average_confidence"]
    elif result["conflicting_findings"]:
        # Documented tie-break: no consensus reached, fall back to the
        # single highest-confidence finding among the conflicting ones.
        best = max(result["conflicting_findings"], key=lambda f: f["confidence"])
        predicted_answer = best["content"]["answer"]
        predicted_confidence = best["confidence"]
    else:
        # Should not happen given non-empty responses; fail loudly rather
        # than silently fabricating a result (AGENTS.md 4.4).
        raise RuntimeError(f"Synthesis produced no findings for {task.task_id}")

    return ConditionResult(
        task_id=task.task_id,
        predicted_answer=predicted_answer,
        predicted_confidence=predicted_confidence,
        correct=predicted_answer == task.ground_truth,
    )


CONDITION_EVALUATORS: Dict[Condition, Callable] = {
    Condition.SINGLE_AGENT: evaluate_single_agent,
    Condition.NAIVE_MAJORITY_VOTE: evaluate_naive_majority_vote,
    Condition.CONFIDENCE_WEIGHTED_SYNTHESIS: evaluate_confidence_weighted_synthesis,
}


# ============================================================================
# 4. STATISTICS (stdlib only — no numpy/scipy, per AGENTS.md dependency rule)
# ============================================================================

def wilson_confidence_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion. Same method used by
    the existing Arena v2 experiments (see arena2_proof_20260917.json)."""
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    adj = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    lo = (centre - adj) / denom
    hi = (centre + adj) / denom
    return (max(0.0, lo), min(1.0, hi))


def brier_score(results: List[ConditionResult]) -> float:
    """Mean squared error between stated confidence and binary outcome.
    Lower is better calibrated (0.0 = perfect, 0.25 = uninformative)."""
    if not results:
        return 0.0
    total = 0.0
    for r in results:
        outcome = 1.0 if r.correct else 0.0
        total += (r.predicted_confidence - outcome) ** 2
    return total / len(results)


def bootstrap_paired_difference(
    pairs: List[Tuple[ConditionResult, ConditionResult]],
    statistic_fn: Callable[[List[ConditionResult]], float],
    n_resamples: int = 2000,
    seed: int = 0,
) -> Tuple[float, float, float]:
    """
    Paired bootstrap for the difference in a statistic (e.g. Brier score)
    between condition B and condition A, computed on the SAME underlying
    task pairs (paired design controls for task-sampling variance).

    Returns (observed_difference, ci_lo, ci_hi) where difference = B - A.
    """
    a_results = [p[0] for p in pairs]
    b_results = [p[1] for p in pairs]
    observed = statistic_fn(b_results) - statistic_fn(a_results)

    rng = random.Random(seed)
    n = len(pairs)
    diffs = []
    for _ in range(n_resamples):
        idx = [rng.randrange(n) for _ in range(n)]
        resample_a = [a_results[i] for i in idx]
        resample_b = [b_results[i] for i in idx]
        diffs.append(statistic_fn(resample_b) - statistic_fn(resample_a))

    diffs.sort()
    lo_idx = int(0.025 * n_resamples)
    hi_idx = int(0.975 * n_resamples) - 1
    ci_lo = diffs[max(0, lo_idx)]
    ci_hi = diffs[min(n_resamples - 1, hi_idx)]
    return (observed, ci_lo, ci_hi)


# ============================================================================
# 5. THE ARENA
# ============================================================================

@dataclass
class ArenaProof:
    arena: str
    timestamp: str
    hypothesis: str
    improvement_threshold: str
    n_tasks: int
    total_agent_calls: int
    accuracy: Dict[str, Dict[str, Any]]
    brier: Dict[str, Dict[str, Any]]
    brier_delta_synthesis_vs_majority: Dict[str, float]
    classification: str
    classification_reason: str
    no_claims: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "arena": self.arena,
            "timestamp": self.timestamp,
            "hypothesis": self.hypothesis,
            "improvement_threshold": self.improvement_threshold,
            "n_tasks": self.n_tasks,
            "total_agent_calls": self.total_agent_calls,
            "accuracy": self.accuracy,
            "brier": self.brier,
            "brier_delta_synthesis_vs_majority": self.brier_delta_synthesis_vs_majority,
            "classification": self.classification,
            "classification_reason": self.classification_reason,
            "no_claims": self.no_claims,
            "proof_hash": self._compute_proof_hash(),
        }

    def _compute_proof_hash(self) -> str:
        import json
        payload = json.dumps(
            {
                "arena": self.arena,
                "n_tasks": self.n_tasks,
                "accuracy": self.accuracy,
                "brier": self.brier,
                "classification": self.classification,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


class SynthesisCalibrationArena:
    """
    Runs the pre-registered experiment. Every task gets exactly N_RESPONSES
    simulated agent responses, generated ONCE and reused across all three
    conditions (paired design — isolates the aggregation method as the only
    variable, removing task-sampling noise from the comparison).
    """

    N_RESPONSES_PER_TASK = 3

    def __init__(self, n_tasks: int, seed: int = 20260926):
        self.n_tasks = n_tasks
        self.seed = seed
        self.tasks = generate_task_set(n_tasks, seed)
        self.simulator = SeededAgentSimulator(seed)

    def run_hermetic(self) -> ArenaProof:
        """
        Runs the full experiment against SIMULATED (seeded, deterministic)
        agent responses. This is the CODE_COMPLETE / TEST_VERIFIED path —
        safe to run in CI, costs nothing, fully reproducible.
        """
        results: Dict[Condition, List[ConditionResult]] = {c: [] for c in Condition}

        for task in self.tasks:
            responses = [
                self.simulator.respond(task, i) for i in range(self.N_RESPONSES_PER_TASK)
            ]
            for condition, evaluator in CONDITION_EVALUATORS.items():
                results[condition].append(evaluator(responses, task))

        total_agent_calls = self.n_tasks * self.N_RESPONSES_PER_TASK

        accuracy_stats = {}
        for condition in Condition:
            correct = sum(1 for r in results[condition] if r.correct)
            total = len(results[condition])
            lo, hi = wilson_confidence_interval(correct, total)
            accuracy_stats[condition.value] = {
                "correct": correct,
                "total": total,
                "rate": round(correct / total, 4) if total else 0.0,
                "ci95": [round(lo, 4), round(hi, 4)],
            }

        brier_stats = {}
        for condition in Condition:
            brier_stats[condition.value] = round(brier_score(results[condition]), 4)

        pairs = list(zip(results[Condition.NAIVE_MAJORITY_VOTE], results[Condition.CONFIDENCE_WEIGHTED_SYNTHESIS]))
        observed_delta, ci_lo, ci_hi = bootstrap_paired_difference(
            pairs, brier_score, n_resamples=2000, seed=self.seed
        )

        # Pre-registered classification logic — fixed before any run.
        ci_excludes_zero = (ci_lo > 0) or (ci_hi < 0)
        if observed_delta <= -IMPROVEMENT_THRESHOLD_BRIER_DELTA and ci_excludes_zero:
            classification = "IMPROVED"
            reason = (
                f"synthesis Brier score {abs(observed_delta):.4f} lower than naive majority "
                f"vote, exceeding pre-registered threshold {IMPROVEMENT_THRESHOLD_BRIER_DELTA}, "
                f"95% CI [{ci_lo:.4f}, {ci_hi:.4f}] excludes zero"
            )
        elif observed_delta >= IMPROVEMENT_THRESHOLD_BRIER_DELTA and ci_excludes_zero:
            classification = "WORSE"
            reason = (
                f"synthesis Brier score {observed_delta:.4f} higher (worse) than naive "
                f"majority vote, 95% CI [{ci_lo:.4f}, {ci_hi:.4f}] excludes zero"
            )
        else:
            classification = "NO_MEASURABLE_IMPROVEMENT"
            reason = (
                f"Brier delta {observed_delta:.4f} does not clear pre-registered threshold "
                f"{IMPROVEMENT_THRESHOLD_BRIER_DELTA}, or 95% CI [{ci_lo:.4f}, {ci_hi:.4f}] "
                f"includes zero"
            )

        return ArenaProof(
            arena="synthesis-calibration-v1",
            timestamp=datetime.utcnow().isoformat(),
            hypothesis=PRE_REGISTERED_HYPOTHESIS,
            improvement_threshold=(
                f"Brier reduction > {IMPROVEMENT_THRESHOLD_BRIER_DELTA} AND paired bootstrap "
                f"95% CI excludes zero (pre-registered)"
            ),
            n_tasks=self.n_tasks,
            total_agent_calls=total_agent_calls,
            accuracy=accuracy_stats,
            brier=brier_stats,
            brier_delta_synthesis_vs_majority={
                "observed": round(observed_delta, 4),
                "ci95_lo": round(ci_lo, 4),
                "ci95_hi": round(ci_hi, 4),
            },
            classification=classification,
            classification_reason=reason,
            no_claims=NO_CLAIMS,
        )

    def run_live(self, provider: Optional[Any] = None):
        """
        LIVE variant: would replace SeededAgentSimulator.respond() with real
        provider calls (e.g. Mercury-2 via the existing ModelProvider
        protocol) and re-run the identical aggregation/statistics logic
        above unchanged.

        NOT IMPLEMENTED. Per AGENTS.md 4.4 ("No Fake Success"), this refuses
        to run rather than silently falling back to simulated data under a
        LIVE label. Wiring a real provider in is the entire scope of a
        future, explicitly budgeted PR.
        """
        raise NotImplementedError(
            "run_live() requires a real ModelProvider and an explicit compute "
            "budget decision. Refusing to fabricate a live result — see "
            "AGENTS.md 4.4 (No Fake Success)."
        )
