"""Multi-agent lease/heartbeat with stale agent eviction and no double-leaders."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class Lease:
    agent_id: str
    task_id: str
    acquired_at: float = field(default_factory=time.time)
    ttl_seconds: int = 300
    leader: bool = False


class LeaseManager:
    """Manages leases across agents; evicts stale leases; prevents double-leaders."""

    def __init__(self, default_ttl_seconds: int = 300):
        self._leases: Dict[str, Lease] = {}  # task_id → Lease
        self._agent_leases: Dict[str, Set[str]] = {}  # agent_id → set(task_ids)
        self._leaders: Set[str] = set()  # agent_ids that are leaders
        self._default_ttl = default_ttl_seconds

    def acquire(self, agent_id: str, task_id: str, leader: bool = False) -> bool:
        """Acquire lease for task. Prevents double-leader."""
        if leader and self._leaders:
            logger.warning(f"Leader already exists; deny {agent_id}")
            return False
        if task_id in self._leases:
            lease = self._leases[task_id]
            if time.time() - lease.acquired_at < lease.ttl_seconds:
                return False  # active lease exists
        lease = Lease(agent_id=agent_id, task_id=task_id, leader=leader)
        self._leases[task_id] = lease
        self._agent_leases.setdefault(agent_id, set()).add(task_id)
        if leader:
            self._leaders.add(agent_id)
        return True

    def release(self, task_id: str) -> bool:
        """Release lease by task_id."""
        if task_id not in self._leases:
            return False
        lease = self._leases.pop(task_id)
        agent_tasks = self._agent_leases.get(lease.agent_id, set())
        agent_tasks.discard(task_id)
        if not agent_tasks:
            self._agent_leases.pop(lease.agent_id, None)
        if lease.leader and lease.agent_id in self._leaders:
            self._leaders.discard(lease.agent_id)
        return True

    def evict_stale(self) -> List[str]:
        """Evict all stale leases. Returns evicted task_ids."""
        now = time.time()
        stale = [
            tid for tid, lease in self._leases.items()
            if now - lease.acquired_at > lease.ttl_seconds
        ]
        for tid in stale:
            self.release(tid)
        return stale

    def is_leader(self, agent_id: str) -> bool:
        return agent_id in self._leaders

    def get_agent_tasks(self, agent_id: str) -> Set[str]:
        return set(self._agent_leases.get(agent_id, set()))

    def get_lease(self, task_id: str) -> Optional[Lease]:
        return self._leases.get(task_id)

    @property
    def active_leases(self) -> Dict[str, Lease]:
        return dict(self._leases)
