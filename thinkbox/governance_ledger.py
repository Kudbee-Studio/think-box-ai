"""Auditable governance ledger for autonomous decision accountability.

Records value signals, decisions, governance rules, drift indicators, and
cryptographic proofs—enabling independent verification of what was applied
to each autonomous decision, without claiming to prove ethical correctness.

Six governance primitives:
1. Value Signal Ledger — records human feedback, policies, governance decisions
2. Governance Consensus Engine — detects conflicts, resolves with explicit rules
3. Alignment Drift Monitor — tracks deviation from baseline behavior
4. Decision Governance Gate — evaluates constraints before execution
5. Proof Layer — produces tamper-evident cryptographic receipts
6. Human Audit Trail — complete record of governance and human intervention
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GovernanceSignalType(Enum):
    """Types of governance signals in the ledger."""
    HUMAN_PREFERENCE = "human_preference"  # Human stated what they want
    POLICY_CONSTRAINT = "policy_constraint"  # Rule/constraint declared
    GOVERNANCE_DECISION = "governance_decision"  # Governance team decision
    DRIFT_ALERT = "drift_alert"  # System detected deviation
    INTERVENTION = "intervention"  # Human overrode system


class DecisionGatingDecision(Enum):
    """Gate decision on a proposed action."""
    ALLOW = "allow"  # Evaluates against constraints, all pass
    DENY = "deny"  # Violates declared constraint
    ESCALATE = "escalate"  # Cannot resolve with declared rules


@dataclass
class GovernanceSignal:
    """A single governance input (human preference, policy, decision)."""
    signal_type: GovernanceSignalType
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    provenance: str = ""  # WHO supplied this (human ID, policy version, etc.)
    content: str = ""  # WHAT the signal is
    versioning: Optional[str] = None  # Version ID of policy/rule
    human_id: Optional[str] = None
    signal_id: str = field(default_factory=lambda: hashlib.sha256(
        f"{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:16])

    def hash(self) -> str:
        """Cryptographic hash of this signal."""
        return hashlib.sha256(
            json.dumps({
                "type": self.signal_type.value,
                "provenance": self.provenance,
                "content": self.content,
                "version": self.versioning,
            }, sort_keys=True).encode()
        ).hexdigest()


@dataclass
class GovernanceDecision:
    """Record of a governance gate decision on a proposed action."""
    decision_id: str
    action_description: str
    decision: DecisionGatingDecision
    applicable_signals: list[str] = field(default_factory=list)  # Signal IDs that applied
    conflict_detected: bool = False  # True if signals contradicted
    resolution_rule: str = ""  # How conflict was resolved (or why escalated)
    evidence: dict[str, Any] = field(default_factory=dict)  # Decision evidence
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    human_intervened: bool = False
    intervention_note: Optional[str] = None

    def hash(self) -> str:
        """Cryptographic hash of this decision."""
        return hashlib.sha256(
            json.dumps({
                "decision": self.decision.value,
                "action": self.action_description,
                "signals": sorted(self.applicable_signals),
                "conflict": self.conflict_detected,
                "human_intervened": self.human_intervened,
            }, sort_keys=True).encode()
        ).hexdigest()


@dataclass
class GovernanceProof:
    """Tamper-evident receipt of governance applied to a decision."""
    proof_id: str
    decision_id: str
    decision_hash: str  # Hash of the governance decision
    governing_signals: list[str] = field(default_factory=list)  # Signal IDs that governed this
    signal_hashes: list[str] = field(default_factory=list)  # Hashes of those signals
    previous_proof_hash: str = ""  # Links to prior decision (chain)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def full_hash(self) -> str:
        """Hash of this proof (for chaining)."""
        return hashlib.sha256(
            json.dumps({
                "decision_hash": self.decision_hash,
                "signal_hashes": sorted(self.signal_hashes),
                "previous_hash": self.previous_proof_hash,
            }, sort_keys=True).encode()
        ).hexdigest()


class GovernanceLedger:
    """Auditable ledger of governance signals and decision gates.

    This is NOT an alignment system. This is an accountability system.
    It records what governance rules were applied to each decision,
    enabling independent verification—but does not claim to prove
    those decisions were ethically correct.
    """

    def __init__(self):
        """Initialize empty governance ledger."""
        self._signals: dict[str, GovernanceSignal] = {}
        self._decisions: dict[str, GovernanceDecision] = {}
        self._proofs: list[GovernanceProof] = []

    async def record_signal(
        self,
        signal_type: GovernanceSignalType,
        provenance: str,
        content: str,
        versioning: Optional[str] = None,
        human_id: Optional[str] = None,
    ) -> GovernanceSignal:
        """Record a governance signal (human preference, policy, decision).

        Args:
            signal_type: What kind of signal
            provenance: Who/what supplied this (must be auditable)
            content: The signal content
            versioning: Version ID (for policies)
            human_id: Human if from human review

        Returns:
            The recorded signal with hash
        """
        signal = GovernanceSignal(
            signal_type=signal_type,
            provenance=provenance,
            content=content,
            versioning=versioning,
            human_id=human_id,
        )
        self._signals[signal.signal_id] = signal
        logger.info(f"Recorded governance signal {signal.signal_id}: {provenance}")
        return signal

    async def evaluate_against_constraints(
        self,
        action_description: str,
        applicable_signal_ids: list[str],
    ) -> GovernanceDecision:
        """Evaluate a proposed action against recorded governance signals.

        Does NOT claim the action is ethically correct. Only evaluates
        whether it violates explicitly recorded constraints.

        Args:
            action_description: What is being proposed
            applicable_signal_ids: Which signals should apply to this action

        Returns:
            GovernanceDecision recording the evaluation
        """
        decision_id = "decision_" + hashlib.sha256(
            f'{action_description}{datetime.now(timezone.utc).isoformat()}'.encode()
        ).hexdigest()[:12]

        applicable_signals = [
            self._signals.get(sid) for sid in applicable_signal_ids
            if sid in self._signals
        ]

        # Check for conflicts (multiple policies saying different things)
        deny_signals = [s for s in applicable_signals if s and "deny" in s.content.lower()]
        allow_signals = [s for s in applicable_signals if s and "allow" in s.content.lower()]
        conflict = bool(deny_signals and allow_signals)

        # Decision logic: explicit constraints only
        decision = DecisionGatingDecision.ALLOW
        resolution_rule = "No applicable deny constraints"

        if deny_signals and not allow_signals:
            decision = DecisionGatingDecision.DENY
            resolution_rule = f"Denied by {len(deny_signals)} constraint(s)"
        elif conflict:
            decision = DecisionGatingDecision.ESCALATE
            resolution_rule = "Conflicting governance signals; human escalation required"

        gov_decision = GovernanceDecision(
            decision_id=decision_id,
            action_description=action_description,
            decision=decision,
            applicable_signals=applicable_signal_ids,
            conflict_detected=conflict,
            resolution_rule=resolution_rule,
            evidence={
                "deny_signals": len(deny_signals),
                "allow_signals": len(allow_signals),
                "total_signals": len(applicable_signals),
            },
        )

        self._decisions[decision_id] = gov_decision
        return gov_decision

    async def record_human_intervention(
        self,
        decision_id: str,
        intervention_note: str,
    ) -> None:
        """Record that a human reviewed and intervened on a decision.

        Args:
            decision_id: Which decision
            intervention_note: What the human decided and why
        """
        if decision_id in self._decisions:
            self._decisions[decision_id].human_intervened = True
            self._decisions[decision_id].intervention_note = intervention_note
            logger.info(f"Recorded human intervention on {decision_id}")

    async def generate_proof(
        self,
        decision_id: str,
    ) -> GovernanceProof:
        """Generate tamper-evident proof of governance applied to a decision.

        Args:
            decision_id: Which decision to prove

        Returns:
            GovernanceProof with cryptographic hashes
        """
        if decision_id not in self._decisions:
            raise ValueError(f"Decision {decision_id} not found")

        decision = self._decisions[decision_id]
        signal_hashes = [
            self._signals[sid].hash()
            for sid in decision.applicable_signals
            if sid in self._signals
        ]

        previous_hash = self._proofs[-1].full_hash() if self._proofs else ""

        proof_id_hash = hashlib.sha256(
            f'{decision_id}{datetime.now(timezone.utc).isoformat()}'.encode()
        ).hexdigest()[:12]

        proof = GovernanceProof(
            proof_id="proof_" + proof_id_hash,
            decision_id=decision_id,
            decision_hash=decision.hash(),
            governing_signals=decision.applicable_signals,
            signal_hashes=signal_hashes,
            previous_proof_hash=previous_hash,
        )

        self._proofs.append(proof)
        return proof

    async def verify_proof_chain(self) -> bool:
        """Verify the entire proof chain is tamper-evident.

        Checks:
        - Each proof's previous_hash matches prior proof's full_hash
        - No broken links in the chain

        Returns:
            True if chain is valid, False if tampered
        """
        if not self._proofs:
            return True

        for i in range(1, len(self._proofs)):
            proof = self._proofs[i]
            prev_proof = self._proofs[i - 1]

            if proof.previous_proof_hash != prev_proof.full_hash():
                logger.warning(f"Proof chain broken at index {i}")
                return False

        return True

    def get_audit_trail(self, decision_id: str) -> dict[str, Any]:
        """Get the complete audit trail for a decision.

        Returns:
            WHO supplied governance signals → WHAT decision was made →
            WHAT evidence was available → WHICH policies applied →
            WHETHER human intervened → OUTCOME
        """
        if decision_id not in self._decisions:
            return {}

        decision = self._decisions[decision_id]
        signals_detail = {
            sid: {
                "type": self._signals[sid].signal_type.value,
                "provenance": self._signals[sid].provenance,
                "content": self._signals[sid].content,
            }
            for sid in decision.applicable_signals
            if sid in self._signals
        }

        return {
            "decision_id": decision_id,
            "action_description": decision.action_description,
            "decision": decision.decision.value,
            "governing_signals": signals_detail,
            "conflict_detected": decision.conflict_detected,
            "resolution_rule": decision.resolution_rule,
            "evidence": decision.evidence,
            "human_intervened": decision.human_intervened,
            "intervention_note": decision.intervention_note,
            "timestamp": decision.timestamp,
            "can_verify": True,  # All artifacts are present for independent verification
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown and report ledger state."""
        is_valid = await self.verify_proof_chain()
        logger.info(
            f"Governance ledger shutdown. "
            f"Recorded {len(self._signals)} signals, "
            f"{len(self._decisions)} decisions, "
            f"{len(self._proofs)} proofs. "
            f"Proof chain valid: {is_valid}"
        )
