"""KUDBEE Control Fabric — Fact-card registry and coverage scheduler.

Targets under-covered concepts so each paid burst call adds signal instead
of repeating what the harness already has.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FactCard:
    card_id: str
    concept: str
    prompt: str
    text: str
    uses: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "concept": self.concept,
            "prompt": self.prompt,
            "text": self.text,
            "uses": self.uses,
        }


class FactCardRegistry:
    """Registry with least-used-first scheduling for burst planning."""

    def __init__(self) -> None:
        self._cards: dict[str, FactCard] = {}
        self._order: list[str] = []

    def add(self, card_id: str, concept: str, prompt: str, text: str) -> FactCard:
        card = FactCard(card_id=card_id, concept=concept, prompt=prompt, text=text)
        if card_id not in self._cards:
            self._order.append(card_id)
        self._cards[card_id] = card
        return card

    def get(self, card_id: str) -> FactCard | None:
        return self._cards.get(card_id)

    def all(self) -> list[FactCard]:
        return [self._cards[cid] for cid in self._order]

    def record_use(self, card_id: str, times: int = 1) -> bool:
        card = self._cards.get(card_id)
        if not card:
            return False
        card.uses += times
        return True

    def next_batch(self, size: int = 1) -> list[FactCard]:
        ranked = sorted(self._cards.values(), key=lambda c: (c.uses, self._order.index(c.card_id)))
        return ranked[: max(0, size)]

    def coverage(self) -> dict[str, int]:
        return {card.concept: card.uses for card in self.all()}

    def to_dict(self) -> list[dict[str, Any]]:
        return [card.to_dict() for card in self.all()]

    @classmethod
    def from_mapping(cls, mapping: dict[str, str]) -> "FactCardRegistry":
        """Build from ``{prompt: "concept: text"}`` (burst default shape)."""
        registry = cls()
        for index, (prompt, value) in enumerate(mapping.items()):
            concept, _, text = value.partition(":")
            registry.add(
                card_id=f"fc_{index:03d}",
                concept=concept.strip(),
                prompt=prompt,
                text=text.strip() or value,
            )
        return registry