"""Governance integration for autonomous task execution.

Wires the six governance primitives into the Think Box autonomous execution
lifecycle. Every task execution passes through governance gates and produces
cryptographic proofs of what rules were applied.

Integration points:
1. Before task execution: evaluate against governance signals
2. Gate decision: ALLOW / DENY / ESCALATE
3. On execution: record task completion + governance decision
4. After execution: generate and persist cryptographic proof
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from thinkbox.governance_ledger import (
    GovernanceLedger,
    GovernanceSignalType,
    DecisionGatingDecision,
)

logger = logging.getLogger(__name__)


class GovernedExecutionPhase(Enum):
    """Phases of governed task execution."""
    PRE_GATE = "pre_gate"  # Before governance evaluation
    GATED = "gated"  # After governance decision
    EXECUTED = "executed"  # After task execution
    PROVED = "proved"  # After proof generation


@dataclass
class GovernedTaskExecution:
    """Record of a governed task execution."""
    task_id: str
    task_description: str
    phase: GovernedExecutionPhase
    governance_signals: list[str] = None  # Signal IDs that governed this
    gate_decision: Optional[DecisionGatingDecision] = None
    execution_allowed: bool = False
    execution_result: Optional[dict[str, Any]] = None
    proof_id: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self) -> None:
        """Set defaults."""
        if self.governance_signals is None:
            self.governance_signals = []


class GovernedExecutionEngine:
    """Wraps autonomous task execution with governance enforcement."""

    def __init__(
        self,
        ledger: GovernanceLedger,
        get_applicable_signals: Callable,
    ):
        """Initialize governed execution engine.

        Args:
            ledger: GovernanceLedger for recording governance artifacts
            get_applicable_signals: Async function to get applicable signal IDs for a task
        """
        self.ledger = ledger
        self.get_applicable_signals = get_applicable_signals
        self._execution_records: list[GovernedTaskExecution] = []

    async def governed_execute_task(
        self,
        task_id: str,
        task_description: str,
        actual_execute: Callable[[], Any],
    ) -> GovernedTaskExecution:
        """Execute a task under governance gates.

        Args:
            task_id: Unique task identifier
            task_description: Human-readable description
            actual_execute: Async function that executes the task

        Returns:
            GovernedTaskExecution record with complete governance trail
        """
        execution_record = GovernedTaskExecution(
            task_id=task_id,
            task_description=task_description,
            phase=GovernedExecutionPhase.PRE_GATE,
        )

        try:
            # 1. Get applicable governance signals
            signal_ids = await self.get_applicable_signals(task_description)
            execution_record.governance_signals = signal_ids

            logger.info(f"Task {task_id}: {len(signal_ids)} governance signal(s) apply")

            # 2. Evaluate against constraints
            gov_decision = await self.ledger.evaluate_against_constraints(
                action_description=task_description,
                applicable_signal_ids=signal_ids,
            )
            execution_record.gate_decision = gov_decision.decision
            execution_record.phase = GovernedExecutionPhase.GATED

            logger.info(f"Task {task_id}: Gate decision = {gov_decision.decision.value}")

            # 3. Decide whether to execute
            if gov_decision.decision == DecisionGatingDecision.DENY:
                logger.warning(f"Task {task_id}: DENIED by governance")
                execution_record.error = f"Denied: {gov_decision.resolution_rule}"
                execution_record.execution_allowed = False
                self._execution_records.append(execution_record)
                return execution_record

            if gov_decision.decision == DecisionGatingDecision.ESCALATE:
                logger.warning(f"Task {task_id}: ESCALATE - requires human review")
                execution_record.error = f"Escalated: {gov_decision.resolution_rule}"
                execution_record.execution_allowed = False
                self._execution_records.append(execution_record)
                return execution_record

            # 4. Execute task (ALLOW)
            logger.info(f"Task {task_id}: ALLOWED - executing")
            execution_record.execution_allowed = True
            result = await actual_execute()
            execution_record.execution_result = result
            execution_record.phase = GovernedExecutionPhase.EXECUTED

            logger.info(f"Task {task_id}: Executed successfully")

            # 5. Generate cryptographic proof
            proof = await self.ledger.generate_proof(gov_decision.decision_id)
            execution_record.proof_id = proof.proof_id
            execution_record.phase = GovernedExecutionPhase.PROVED

            logger.info(f"Task {task_id}: Proof generated: {proof.proof_id}")

            self._execution_records.append(execution_record)
            return execution_record

        except Exception as e:
            logger.error(f"Task {task_id}: Execution error: {str(e)}")
            execution_record.error = str(e)
            self._execution_records.append(execution_record)
            raise

    async def verify_execution_chain(self) -> bool:
        """Verify the entire governance chain is tamper-evident.

        Returns:
            True if all proofs are valid and chain is intact
        """
        return await self.ledger.verify_proof_chain()

    def get_execution_audit_trail(self, task_id: str) -> dict[str, Any]:
        """Get complete audit trail for a task execution.

        Args:
            task_id: Which task

        Returns:
            Complete record of governance and execution
        """
        record = next(
            (r for r in self._execution_records if r.task_id == task_id),
            None,
        )

        if not record:
            return {}

        # Find the corresponding governance decision
        gov_decision_id = None
        for r in self._execution_records:
            if r.proof_id and r.task_id == task_id:
                # We have the proof, but need the decision ID from the ledger
                # For now, return what we have
                break

        return {
            "task_id": task_id,
            "task_description": record.task_description,
            "phase": record.phase.value,
            "governance_signals": record.governance_signals,
            "gate_decision": record.gate_decision.value if record.gate_decision else None,
            "execution_allowed": record.execution_allowed,
            "execution_result_type": type(record.execution_result).__name__ if record.execution_result else None,
            "proof_id": record.proof_id,
            "error": record.error,
            "can_verify": True,
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown and report governance state."""
        is_valid = await self.verify_execution_chain()
        logger.info(
            f"Governed execution engine shutdown. "
            f"Executed {len(self._execution_records)} tasks. "
            f"Proof chain valid: {is_valid}"
        )
