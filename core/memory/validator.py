"""Memory validation pipeline for THINK BOX AI.

This module implements the validation pipeline that verifies candidate memories
before promoting them to permanent storage. Validation sources include tests,
documentation, codebase evidence, user history, and repeated usage.

Per AGENTS.md §1.4: "Never store speculative claims in Organizational Memory."
"""

from __future__ import annotations

import json
from typing import Any

from core.foundation.logging import get_logger
from core.memory.candidate import (
    CandidateMemory,
    ValidationResult,
    ValidationSource,
    ValidationStatus,
)

logger = get_logger(__name__)


class MemoryValidator:
    """Validates candidate memories before promotion to permanent storage.

    The validator checks candidates against multiple sources:
    - Tests: Does the memory agree with passing tests?
    - Documentation: Does it match README, ADRs, code comments?
    - Codebase: Is the pattern actually present in the code?
    - User history: Has the user confirmed this before?
    - Repeated usage: Has this worked ≥ 3 times?

    Usage:
        validator = MemoryValidator(codebase_index, docs_index, test_results)
        result = await validator.validate(candidate)
        if result.status == ValidationStatus.APPROVED:
            store_verified_memory(candidate, result)
    """

    def __init__(
        self,
        codebase_index: Any | None = None,
        docs_index: Any | None = None,
        test_results: Any | None = None,
    ) -> None:
        """Initialize the Memory Validator.

        Args:
            codebase_index: Index of codebase for codebase validation
            docs_index: Index of documentation for doc validation
            test_results: Test results for test validation
        """
        self.codebase_index = codebase_index
        self.docs_index = docs_index
        self.test_results = test_results

    async def validate(self, candidate: CandidateMemory) -> ValidationResult:
        """Validate a candidate memory against all available sources.

        Args:
            candidate: Candidate memory to validate

        Returns:
            ValidationResult with status and score
        """
        sources_checked: list[ValidationSource] = []
        reasons: list[str] = []
        scores: list[float] = []

        # Check each validation source
        if self.test_results is not None:
            test_score = self.check_tests(candidate)
            sources_checked.append(ValidationSource.TESTS)
            scores.append(test_score)
            reasons.append(f"Tests: {test_score:.0%} match")

        if self.docs_index is not None:
            doc_score = self.check_documentation(candidate)
            sources_checked.append(ValidationSource.DOCUMENTATION)
            scores.append(doc_score)
            reasons.append(f"Documentation: {doc_score:.0%} match")

        if self.codebase_index is not None:
            code_score = self.check_codebase(candidate)
            sources_checked.append(ValidationSource.CODEBASE)
            scores.append(code_score)
            reasons.append(f"Codebase: {code_score:.0%} match")

        # Always check repeated usage
        usage_score = self.check_repeated_usage(candidate)
        sources_checked.append(ValidationSource.REPEATED_USAGE)
        scores.append(usage_score)
        reasons.append(f"Repeated usage: {usage_score:.0%}")

        # Calculate overall score
        overall_score = sum(scores) / len(scores) if scores else 0.0

        # Determine status
        if overall_score >= 0.8:
            status = ValidationStatus.APPROVED
        elif overall_score >= 0.5:
            status = ValidationStatus.NEEDS_REVIEW
        else:
            status = ValidationStatus.REJECTED

        result = ValidationResult(
            candidate_id=candidate.id,
            status=status,
            score=overall_score,
            sources_checked=sources_checked,
            reasons=reasons,
        )

        logger.info(
            "Validated candidate memory",
            extra={
                "candidate_id": candidate.id,
                "status": status.value,
                "score": overall_score,
                "sources": [s.value for s in sources_checked],
            },
        )
        return result

    def check_tests(self, candidate: CandidateMemory) -> float:
        """Check if candidate agrees with passing tests.

        In a real implementation, this would:
        1. Extract keywords from candidate content
        2. Search test results for matching assertions
        3. Return match score

        For now, returns a heuristic score based on candidate type.
        """
        if candidate.candidate_type == CandidateType.FACT:
            return 0.7  # Facts should be testable
        elif candidate.candidate_type == CandidateType.PATTERN:
            return 0.6  # Patterns should have test coverage
        return 0.5

    def check_documentation(self, candidate: CandidateMemory) -> float:
        """Check if candidate matches documentation.

        In a real implementation, this would:
        1. Search README, ADRs, code comments
        2. Check for agreement/disagreement
        3. Return match score

        For now, returns a heuristic score.
        """
        content_lower = candidate.content.lower()
        # Check for documentation keywords
        doc_keywords = ["readme", "docs", "documentation", "guide", "adr"]
        matches = sum(1 for kw in doc_keywords if kw in content_lower)
        return min(0.3 + matches * 0.1, 0.9)

    def check_codebase(self, candidate: CandidateMemory) -> float:
        """Check if candidate is supported by codebase evidence.

        In a real implementation, this would:
        1. Use codebase_index to search for relevant code
        2. Check if the pattern/fact exists in code
        3. Return match score

        For now, returns a heuristic score.
        """
        if candidate.candidate_type == CandidateType.PATTERN:
            return 0.7  # Patterns should exist in code
        elif candidate.candidate_type == CandidateType.FACT:
            return 0.6
        return 0.4

    def check_repeated_usage(self, candidate: CandidateMemory) -> float:
        """Check if candidate has been successfully used multiple times.

        Repeated successful usage increases confidence.
        """
        usage_count = candidate.metadata.get("usage_count", 0)
        if usage_count >= 5:
            return 0.9
        elif usage_count >= 3:
            return 0.7
        elif usage_count >= 1:
            return 0.5
        return 0.3

    async def batch_validate(
        self, candidates: list[CandidateMemory]
    ) -> list[ValidationResult]:
        """Validate a batch of candidates.

        Args:
            candidates: List of candidate memories to validate

        Returns:
            List of validation results
        """
        results = []
        for candidate in candidates:
            result = await self.validate(candidate)
            results.append(result)
        return results
