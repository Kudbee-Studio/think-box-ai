"""Box assignment persistence store.

Persists Box pool allocations to `.thinkbox/box_assignments.json` so
assignments survive process restarts.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BoxAssignmentRecord:
    """Record of a box assignment."""
    agent_id: str
    box_url: str
    assigned_at: str
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "box_url": self.box_url,
            "assigned_at": self.assigned_at,
        }


class BoxAssignmentStore:
    """Persistent Box assignment store."""
    
    def __init__(self, store_path: str | None = None) -> None:
        """Initialize assignment store.
        
        Args:
            store_path: Path to store file. Defaults to .thinkbox/box_assignments.json
        """
        if store_path is None:
            store_path = os.path.expanduser("~/.thinkbox/box_assignments.json")
        
        self._path = Path(store_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._assignments: dict[str, str] = {}  # agent_id -> box_url
        self._assignment_times: dict[str, str] = {}  # agent_id -> timestamp
        self._load()
    
    def _load(self) -> None:
        """Load assignments from disk."""
        with self._lock:
            if self._path.exists():
                try:
                    data = json.loads(self._path.read_text())
                    for record in data.get("assignments", []):
                        agent_id = record.get("agent_id")
                        box_url = record.get("box_url")
                        assigned_at = record.get("assigned_at")
                        if agent_id and box_url:
                            self._assignments[agent_id] = box_url
                            if assigned_at:
                                self._assignment_times[agent_id] = assigned_at
                    logger.info(f"Loaded {len(self._assignments)} box assignments from {self._path}")
                except Exception as e:
                    logger.error(f"Failed to load box assignments: {e}")
    
    def _save(self) -> None:
        """Save assignments to disk."""
        try:
            records = []
            for agent_id, box_url in self._assignments.items():
                assigned_at = self._assignment_times.get(agent_id, datetime.now(timezone.utc).isoformat())
                records.append({
                    "agent_id": agent_id,
                    "box_url": box_url,
                    "assigned_at": assigned_at,
                })
            
            data = {
                "assignments": records,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
            self._path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save box assignments: {e}")
    
    def set_assignment(self, agent_id: str, box_url: str) -> None:
        """Set an agent's box assignment."""
        with self._lock:
            self._assignments[agent_id] = box_url
            self._assignment_times[agent_id] = datetime.now(timezone.utc).isoformat()
            self._save()
    
    def get_assignment(self, agent_id: str) -> str | None:
        """Get an agent's box assignment."""
        with self._lock:
            return self._assignments.get(agent_id)
    
    def remove_assignment(self, agent_id: str) -> None:
        """Remove an agent's assignment."""
        with self._lock:
            self._assignments.pop(agent_id, None)
            self._assignment_times.pop(agent_id, None)
            self._save()
    
    def get_all_assignments(self) -> dict[str, str]:
        """Get all assignments."""
        with self._lock:
            return dict(self._assignments)
    
    def clear_all(self) -> None:
        """Clear all assignments."""
        with self._lock:
            self._assignments.clear()
            self._assignment_times.clear()
            self._save()
    
    def get_status(self) -> dict[str, Any]:
        """Get store status."""
        with self._lock:
            return {
                "store_path": str(self._path),
                "assignment_count": len(self._assignments),
                "assignments": {
                    agent_id: {
                        "box_url": box_url,
                        "assigned_at": self._assignment_times.get(agent_id, ""),
                    }
                    for agent_id, box_url in self._assignments.items()
                },
            }
