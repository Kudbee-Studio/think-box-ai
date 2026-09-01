#!/usr/bin/env python3
"""Memory graph for Think Box AI.

Tracks relationships between memories for better recall and context.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GRAPH_PATH = Path("data/memory_graph.jsonl")


class MemoryNode:
    """A node in the memory graph."""

    def __init__(self, key: str, category: str, value: Any):
        self.key = key
        self.category = category
        self.value = value
        self.links: list[str] = []  # Keys of related memories
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.access_count = 0


class MemoryGraph:
    """Graph-based memory with relationships."""

    def __init__(self):
        self.nodes: dict[str, MemoryNode] = {}
        self._load()

    def _load(self):
        if GRAPH_PATH.exists():
            with open(GRAPH_PATH) as f:
                for line in f:
                    data = json.loads(line.strip())
                    node = MemoryNode(data["key"], data["category"], data["value"])
                    node.links = data.get("links", [])
                    node.created_at = data["created_at"]
                    node.access_count = data.get("access_count", 0)
                    self.nodes[node.key] = node

    def _save(self):
        GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(GRAPH_PATH, "w") as f:
            for node in self.nodes.values():
                f.write(json.dumps({
                    "key": node.key, "category": node.category, "value": node.value,
                    "links": node.links, "created_at": node.created_at, "access_count": node.access_count,
                }) + "\n")

    def add(self, key: str, category: str, value: Any, links: list[str] | None = None):
        """Add a memory node."""
        node = MemoryNode(key, category, value)
        node.links = links or []
        self.nodes[key] = node
        self._save()
        return node

    def link(self, key1: str, key2: str):
        """Create a bidirectional link between two memories."""
        if key1 in self.nodes and key2 in self.nodes:
            if key2 not in self.nodes[key1].links:
                self.nodes[key1].links.append(key2)
            if key1 not in self.nodes[key2].links:
                self.nodes[key2].links.append(key1)
            self._save()

    def get_related(self, key: str, depth: int = 1) -> list[MemoryNode]:
        """Get related memories up to N degrees of separation."""
        visited = set()
        related = []

        def _explore(k: str, d: int):
            if d <= 0 or k in visited:
                return
            visited.add(k)
            node = self.nodes.get(k)
            if node and k != key:
                related.append(node)
            if node:
                for link in node.links:
                    _explore(link, d - 1)

        _explore(key, depth)
        return related

    def get_cluster(self, category: str) -> list[MemoryNode]:
        """Get all memories in a category cluster."""
        return [n for n in self.nodes.values() if n.category == category]

    def get_stats(self) -> dict:
        """Get graph statistics."""
        return {
            "total_nodes": len(self.nodes),
            "total_links": sum(len(n.links) for n in self.nodes.values()),
            "categories": {cat: len(self.get_cluster(cat)) for cat in set(n.category for n in self.nodes.values())},
        }


# Global graph
memory_graph = MemoryGraph()
