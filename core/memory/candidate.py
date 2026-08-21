"""Memory candidate schema for THINK BOX AI.

This module defines the schemas for candidate memories (pre-validation)
and validation results. Candidates are extracted from raw events by the
Memory Curator and promoted to permanent memory after validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class CandidateType(str, Enum):
    """Types of candidate memories."""

    FACT = "fact"
    DECISION = "decision"
    PREFERENCE = "preference"
    LESSON = "lesson"
    QUESTION = "question"
    PATTERN = "pattern"


class ValidationStatus(str, Enum):
    """Status of a candidate memory in the validation pipeline."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class ValidationSource(str, Enum):
    """Sources used for validation."""

    TESTS = "tests"
    DOCUMENTATION = "documentation"
    CODEBASE = "codebase"
    USER_HISTORY = "user_history"
    REPEATED_USAGE = "repeated_usage"


@dataclass
class CandidateMemory:
    """A candidate memory extracted from raw events.

    Candidates are created by the Memory Curator from raw memory events.
    They must pass validation before being promoted to permanent memory.

    Attributes:
        id: Unique candidate identifier
        session_id: Session where this candidate was extracted
        agent_id: Agent that extracted this candidate
        content: The memory content (e.g., "PostgreSQL preferred over Redis")
        candidate_type: Type of memory (fact, decision, preference, etc.)
        confidence: Initial confidence score (0.0-1.0)
        status: Current validation status
        source_events: IDs of raw events this candidate was extracted from
        created_at: When this candidate was created
        metadata: Additional structured data
    """

    id: str
    session_id: str
    agent_id: str
    content: str
    candidate_type: CandidateType
    confidence: float = 0.0
    status: ValidationStatus = ValidationStatus.PENDING
    source_events: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of validating a candidate memory.

    Attributes:
        candidate_id: ID of the validated candidate
        status: Final validation status
        score: Validation score (0.0-1.0)
        sources_checked: Which validation sources were checked
        reasons: List of reasons for the decision
        validated_at: When validation was performed
    """

    candidate_id: str
    status: ValidationStatus
    score: float = 0.0
    sources_checked: list[ValidationSource] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    validated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class VerifiedMemory:
    """A memory that has passed validation.

    Verified memories are stored in the Verified Knowledge layer
    and can safely influence agent decisions.

    Attributes:
        id: Unique verified memory identifier
        content: The verified memory content
        memory_type: Type of memory
        confidence: Final confidence score
        verification_sources: Sources that verified this memory
        verified_at: When this memory was verified
        metadata: Additional structured data
    """

    id: str
    content: str
    memory_type: CandidateType
    confidence: float
    verification_sources: list[ValidationSource]
    verified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
