"""KUDBEE Control Fabric — Deterministic grounding scorer (v0).

Scores how well a claim binds to supporting evidence. Used by the harvest
replay to turn real traces into honest groundedness / bind-failure numbers
without needing a model or network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "to", "and", "or",
    "in", "on", "for", "with", "by", "as", "at", "be", "it", "this", "that",
    "answer", "grounded", "ungrounded", "using",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_NUMBER_RE = re.compile(r"\d+")


@dataclass
class GroundingScore:
    score: float
    coverage: float
    numeric_ratio: float
    reasoning_present: bool
    evidence_present: bool
    matched_terms: list[str] = field(default_factory=list)

    def is_grounded(self, threshold: float = 0.5) -> bool:
        return self.score >= threshold


def _tokenize(text: str) -> set[str]:
    return {
        t
        for t in _TOKEN_RE.findall(text.lower())
        if t not in _STOPWORDS and (len(t) > 1 or t.isdigit())
    }


class GroundingScorer:
    """Heuristic groundedness: evidence coverage + numeric anchors + reasoning."""

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def score(self, claim: str, evidence: str | None, reasoning: str = "") -> GroundingScore:
        claim_tokens = _tokenize(claim)
        evidence_text = evidence or ""
        evidence_tokens = _tokenize(evidence_text)
        evidence_present = bool(evidence_text.strip())

        if not claim_tokens or not evidence_tokens:
            coverage = 0.0
            matched: list[str] = []
        else:
            matched = sorted(claim_tokens & evidence_tokens)
            coverage = len(matched) / len(claim_tokens)

        claim_numbers = set(_NUMBER_RE.findall(claim))
        evidence_numbers = set(_NUMBER_RE.findall(evidence_text))
        if claim_numbers:
            numeric_ratio = len(claim_numbers & evidence_numbers) / len(claim_numbers)
        else:
            numeric_ratio = 0.0

        reasoning_present = bool(reasoning.strip())
        raw = 0.7 * coverage + 0.2 * numeric_ratio + (0.1 if reasoning_present else 0.0)
        if not evidence_present:
            raw = 0.0
        score = round(max(0.0, min(1.0, raw)), 4)

        return GroundingScore(
            score=score,
            coverage=round(coverage, 4),
            numeric_ratio=round(numeric_ratio, 4),
            reasoning_present=reasoning_present,
            evidence_present=evidence_present,
            matched_terms=matched,
        )

    def classify(self, claim: str, evidence: str | None, reasoning: str = "") -> bool:
        return self.score(claim, evidence, reasoning).is_grounded(self.threshold)