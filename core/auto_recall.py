#!/usr/bin/env python3
"""Auto-recall system for Think Box AI.

Automatically injects relevant memories into CLI context based on current task.
"""

from __future__ import annotations

import re
from typing import Any

from core.cli_memory import memory
from core.memory_graph import memory_graph


class AutoRecall:
    """Intelligently recall relevant memories."""

    def __init__(self):
        self.context_window: list[str] = []

    def analyze_intent(self, user_input: str) -> list[str]:
        """Extract keywords and intent from user input."""
        # Simple keyword extraction
        words = re.findall(r'\b\w+\b', user_input.lower())
        # Filter common words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "shall", "to", "of", "in", "for", "on", "with", "at", "by", "from", "as", "into", "through", "during", "before", "after", "above", "below", "between", "out", "off", "over", "under", "again", "further", "then", "once", "and", "but", "or", "nor", "not", "so", "than", "too", "very", "just", "about", "this", "that", "these", "those", "it", "its", "i", "me", "my", "we", "our", "you", "your", "he", "him", "his", "she", "her", "they", "them", "their", "what", "which", "who", "whom", "when", "where", "why", "how"}
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords

    def recall_for(self, user_input: str, limit: int = 10) -> list[dict]:
        """Find relevant memories for a given input."""
        keywords = self.analyze_intent(user_input)
        results = []

        for keyword in keywords:
            matches = memory.search(keyword, limit=3)
            results.extend(matches)

        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            if r["key"] not in seen:
                seen.add(r["key"])
                unique.append(r)

        return unique[:limit]

    def inject_context(self, user_input: str) -> str:
        """Generate context injection for CLI."""
        memories = self.recall_for(user_input)
        if not memories:
            return ""

        context_lines = ["[Relevant memories]"]
        for m in memories:
            context_lines.append(f"  - {m['key']}: {m['value'][:100]}")
        return "\n".join(context_lines)

    def update_context_window(self, command: str, result: str):
        """Track recent commands for context."""
        self.context_window.append(f"{command}: {result[:200]}")
        if len(self.context_window) > 20:
            self.context_window.pop(0)

    def get_context_window(self) -> str:
        """Get recent context."""
        return "\n".join(self.context_window[-5:])


# Global auto-recall
auto_recall = AutoRecall()
