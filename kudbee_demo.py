"""KUDBEE Vertical-Slice Demo: Agent → Plan → Execute → Evaluate → Result"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from think_box_ai.token import ThinkToken, SYMBOL


# ═══════════════════════════════════════════════════════════════════════════
# EVIDENCE - Immutable record of agent actions
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Evidence:
    """Immutable record of an agent action and its outcome."""
    evidence_id: str
    agent_id: str
    action: str
    input_data: dict
    output_data: dict
    success: bool
    confidence: float  # 0.0 to 1.0
    timestamp: str
    proof_hash: str = ""

    def __post_init__(self) -> None:
        if not self.proof_hash:
            import hashlib
            content = f"{self.evidence_id}:{self.agent_id}:{self.action}:{self.timestamp}"
            self.proof_hash = hashlib.sha256(content.encode()).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════════
# JURY - Evaluates evidence and produces scores
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class JuryVerdict:
    """Verdict from the jury after evaluating evidence."""
    verdict_id: str
    task_id: str
    score: float  # 0.0 to 100.0
    confidence: float  # 0.0 to 1.0
    criteria: dict[str, float]
    reasoning: str
    timestamp: str


class Jury:
    """Evaluates agent work and produces measurable results."""

    CRITERIA_WEIGHTS = {
        "correctness": 0.35,
        "completeness": 0.25,
        "efficiency": 0.20,
        "safety": 0.20,
    }

    def evaluate(self, task_id: str, evidence_list: list[Evidence]) -> JuryVerdict:
        if not evidence_list:
            return JuryVerdict(
                verdict_id=str(uuid.uuid4())[:8],
                task_id=task_id,
                score=0.0,
                confidence=0.0,
                criteria={},
                reasoning="No evidence provided.",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Calculate criteria scores
        success_rate = sum(1 for e in evidence_list if e.success) / len(evidence_list)
        avg_confidence = sum(e.confidence for e in evidence_list) / len(evidence_list)

        criteria = {
            "correctness": success_rate * 100,
            "completeness": min(100.0, len(evidence_list) * 25.0),
            "efficiency": max(0, 100 - len(evidence_list) * 10),
            "safety": 100.0 if all(e.success for e in evidence_list) else 50.0,
        }

        # Weighted score
        score = sum(
            criteria[k] * self.CRITERIA_WEIGHTS[k]
            for k in self.CRITERIA_WEIGHTS
        )

        # Confidence based on evidence quality
        confidence = avg_confidence * (0.5 + 0.5 * success_rate)

        reasoning = (
            f"Evaluated {len(evidence_list)} evidence items. "
            f"Success rate: {success_rate:.0%}. "
            f"Average confidence: {avg_confidence:.2f}. "
            f"Final score: {score:.1f}/100."
        )

        return JuryVerdict(
            verdict_id=str(uuid.uuid4())[:8],
            task_id=task_id,
            score=round(score, 1),
            confidence=round(confidence, 2),
            criteria=criteria,
            reasoning=reasoning,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


# ═══════════════════════════════════════════════════════════════════════════
# CHALLENGE - Defines the task to be solved
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Challenge:
    """A challenge that an agent must solve."""
    challenge_id: str
    title: str
    description: str
    success_criteria: list[str]
    reward_tokens: int
    difficulty: str  # easy, medium, hard
    timestamp: str


# ═══════════════════════════════════════════════════════════════════════════
# AGENT - The KUDBEE agent that plans, executes, and produces evidence
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Step:
    """A single step in an agent's plan."""
    step_id: str
    action: str
    parameters: dict[str, Any]
    expected_output: str
    evidence: Evidence | None = None


@dataclass
class Plan:
    """A plan consisting of ordered steps."""
    plan_id: str
    goal: str
    steps: list[Step] = field(default_factory=list)


class KudbeeAgent:
    """KUDBEE Agent: Plans, executes work, and produces evidence."""

    def __init__(self, agent_id: str, name: str) -> None:
        self.agent_id = agent_id
        self.name = name
        self.token_balance: int = 1000
        self.evidence_log: list[Evidence] = []

    def plan(self, challenge: Challenge) -> Plan:
        """Create a plan to solve the challenge."""
        plan = Plan(plan_id=str(uuid.uuid4())[:8], goal=challenge.title)

        # Generate steps based on challenge difficulty
        num_steps = {"easy": 2, "medium": 3, "hard": 4}.get(challenge.difficulty, 2)

        for i in range(num_steps):
            step = Step(
                step_id=f"step-{i+1}",
                action=f"execute_{challenge.success_criteria[i % len(challenge.success_criteria)].replace(' ', '_')}",
                parameters={
                    "challenge_id": challenge.challenge_id,
                    "step_index": i + 1,
                    "difficulty": challenge.difficulty,
                },
                expected_output=f"Complete: {challenge.success_criteria[i % len(challenge.success_criteria)]}",
            )
            plan.steps.append(step)

        return plan

    async def execute_plan(self, plan: Plan) -> list[Evidence]:
        """Execute a plan and produce evidence for each step."""
        evidence_list: list[Evidence] = []

        for step in plan.steps:
            # Simulate execution
            await asyncio.sleep(0.1)

            # Determine success based on action
            success = True
            confidence = 0.85 + (0.1 if "validate" in step.action else 0.05)

            evidence = Evidence(
                evidence_id=str(uuid.uuid4())[:8],
                agent_id=self.agent_id,
                action=step.action,
                input_data=step.parameters,
                output_data={
                    "status": "completed",
                    "result": step.expected_output,
                    "step_id": step.step_id,
                },
                success=success,
                confidence=min(1.0, confidence),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            step.evidence = evidence
            evidence_list.append(evidence)
            self.evidence_log.append(evidence)

        return evidence_list


# ═══════════════════════════════════════════════════════════════════════════
# KUDBEE DEMO - Full vertical slice
# ═══════════════════════════════════════════════════════════════════════════

async def run_kudbee_demo() -> dict[str, Any]:
    """Run the complete KUDBEE vertical-slice demo."""

    print("=" * 70)
    print("  KUDBEE — Think Box AI — Vertical Slice Demo")
    print("=" * 70)

    # ── 1. CHALLENGE ──────────────────────────────────────────────────
    print("\n📋 CHALLENGE")
    challenge = Challenge(
        challenge_id=str(uuid.uuid4())[:8],
        title="Build a Python function that calculates factorial",
        description="Create a recursive factorial function with input validation and tests.",
        success_criteria=[
            "Function computes correct factorial values",
            "Input validation handles negative numbers",
            "Edge cases (0, 1) handled correctly",
            "Code follows PEP 8 style",
        ],
        reward_tokens=50,
        difficulty="medium",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    print(f"  ID: {challenge.challenge_id}")
    print(f"  Title: {challenge.title}")
    print(f"  Difficulty: {challenge.difficulty}")
    print(f"  Reward: {challenge.reward_tokens} {SYMBOL}")

    # ── 2. AGENT ──────────────────────────────────────────────────────
    print("\n🤖 AGENT")
    agent = KudbeeAgent(
        agent_id=str(uuid.uuid4())[:8],
        name="kudbee-worker-1",
    )
    print(f"  ID: {agent.agent_id}")
    print(f"  Name: {agent.name}")
    print(f"  Starting balance: {agent.token_balance} {SYMBOL}")

    # ── 3. PLAN ───────────────────────────────────────────────────────
    print("\n📐 PLAN")
    plan = agent.plan(challenge)
    print(f"  Plan ID: {plan.plan_id}")
    print(f"  Goal: {plan.goal}")
    print(f"  Steps: {len(plan.steps)}")
    for step in plan.steps:
        print(f"    {step.step_id}: {step.action} → {step.expected_output}")

    # ── 4. EXECUTE ────────────────────────────────────────────────────
    print("\n⚡ EXECUTE")
    evidence_list = await agent.execute_plan(plan)
    for ev in evidence_list:
        status = "✅" if ev.success else "❌"
        print(f"  {status} {ev.evidence_id}: {ev.action} (confidence: {ev.confidence:.0%})")

    # ── 5. EVIDENCE ───────────────────────────────────────────────────
    print("\n📊 EVIDENCE")
    print(f"  Total evidence items: {len(evidence_list)}")
    print(f"  All successful: {all(e.success for e in evidence_list)}")
    print(f"  Average confidence: {sum(e.confidence for e in evidence_list) / len(evidence_list):.2f}")
    for ev in evidence_list:
        print(f"    [{ev.proof_hash}] {ev.action} → {ev.output_data['status']}")

    # ── 6. JURY ───────────────────────────────────────────────────────
    print("\n⚖️  JURY")
    jury = Jury()
    verdict = jury.evaluate(challenge.challenge_id, evidence_list)
    print(f"  Verdict ID: {verdict.verdict_id}")
    print(f"  Score: {verdict.score}/100")
    print(f"  Confidence: {verdict.confidence:.0%}")
    print(f"  Criteria:")
    for criterion, score in verdict.criteria.items():
        bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
        print(f"    {criterion:15s} {bar} {score:.1f}")
    print(f"  Reasoning: {verdict.reasoning}")

    # ── 7. RESULT ─────────────────────────────────────────────────────
    print("\n🏆 RESULT")
    passed = verdict.score >= 70.0
    result_status = "PASS ✅" if passed else "FAIL ❌"

    # Award tokens if passed
    if passed:
        reward = int(challenge.reward_tokens * (verdict.score / 100))
        agent.token_balance += reward
        print(f"  Status: {result_status}")
        print(f"  Tokens awarded: {reward} {SYMBOL}")
    else:
        print(f"  Status: {result_status}")
        print(f"  Tokens awarded: 0 {SYMBOL}")

    print(f"  Agent balance: {agent.token_balance} {SYMBOL}")
    print(f"  Final score: {verdict.score}/100")

    print("\n" + "=" * 70)
    print(f"  KUDBEE DEMO COMPLETE — Score: {verdict.score}/100 — {result_status}")
    print("=" * 70)

    return {
        "challenge": challenge,
        "agent": agent,
        "plan": plan,
        "evidence": evidence_list,
        "verdict": verdict,
        "passed": passed,
        "score": verdict.score,
    }


if __name__ == "__main__":
    result = asyncio.run(run_kudbee_demo())
