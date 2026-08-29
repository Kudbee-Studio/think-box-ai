"""Deterministic verification guardrail for zero-hallucination outputs.

Implements the 'Psychiatrist/Specialist' verification loop:
1. Primary model generates draft
2. Guardrail verifies claims against context
3. Reject or flag unsupported claims
4. Retry with corrective context if needed
"""

from __future__ import annotations
import re
import logging
from typing import Any

from core.foundation.error_codes import ErrorCode, format_error_response

logger = logging.getLogger(__name__)


class VerificationResult:
    """Result of guardrail verification."""

    def __init__(self, approved: bool, issues: list[str], confidence: float) -> None:
        self.approved = approved
        self.issues = issues
        self.confidence = confidence  # 0.0 - 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "issues": self.issues,
            "confidence": round(self.confidence, 4),
        }


class SpecialistGuardrail:
    """Validates model outputs for factual accuracy and context adherence."""

    def __init__(self, require_citations: bool = True, max_claim_length: int = 500) -> None:
        self._require_citations = require_citations
        self._max_claim_length = max_claim_length

    def verify(self, response: str, context: str, claims: list[str] | None = None) -> VerificationResult:
        """Verify response against provided context."""
        issues: list[str] = []
        confidence = 1.0

        # Check 1: Response length sanity
        if len(response) > self._max_claim_length * 10:
            issues.append("Response exceeds reasonable length")
            confidence -= 0.2

        # Check 2: Direct claim verification against context
        if claims:
            for claim in claims:
                if not self._verify_claim(claim, context):
                    issues.append(f"Unverified claim: {claim[:100]}")
                    confidence -= 0.3

        # Check 3: Detect common hallucination patterns
        if self._detect_hallucination_markers(response):
            issues.append("Potential hallucination markers detected")
            confidence -= 0.4

        # Check 4: Citation requirement
        if self._require_citations and not self._has_citations(response, context):
            issues.append("Missing source citations")
            confidence -= 0.1

        approved = len(issues) == 0 and confidence >= 0.6
        return VerificationResult(approved, issues, max(0.0, confidence))

    def _verify_claim(self, claim: str, context: str) -> bool:
        """Check if claim is supported by context."""
        # Simple substring check - production would use semantic similarity
        claim_lower = claim.lower().strip()
        context_lower = context.lower()

        # Direct substring match
        if claim_lower in context_lower:
            return True

        # Key term overlap (at least 50% of significant terms present)
        claim_terms = set(re.findall(r'\b\w{4,}\b', claim_lower))
        if not claim_terms:
            return True  # Skip very short claims

        matching_terms = sum(1 for term in claim_terms if term in context_lower)
        return (matching_terms / len(claim_terms)) >= 0.5

    def _detect_hallucination_markers(self, text: str) -> bool:
        """Detect common patterns associated with hallucinated content."""
        markers = [
            r"i (think|believe|feel) that",
            r"it'?s? (likely|probable|possible) that",
            r"(studies|research) (shows?|suggests?|indicates?)",
            r"(?:according to|as reported by).*?(?:unverified|unknown)",
        ]
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in markers)

    def _has_citations(self, response: str, context: str) -> bool:
        """Check if response references context content."""
        # Simple check: does response share significant terms with context?
        response_terms = set(re.findall(r'\b\w{5,}\b', response.lower()))
        context_terms = set(re.findall(r'\b\w{5,}\b', context.lower()))

        if not response_terms:
            return True

        overlap = len(response_terms & context_terms) / len(response_terms)
        return overlap >= 0.3  # At least 30% term overlap

    def generate_feedback(self, result: VerificationResult) -> str:
        """Generate corrective feedback for rejected responses."""
        if result.approved:
            return ""

        feedback_parts = ["The response requires revision:"]
        for i, issue in enumerate(result.issues, 1):
            feedback_parts.append(f"  {i}. {issue}")

        feedback_parts.append("\nPlease revise with strict adherence to the provided context.")
        return "\n".join(feedback_parts)
