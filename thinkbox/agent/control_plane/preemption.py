"""Priority lane preemption — critical work preempts best-effort; audited."""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class Priority(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    BEST_EFFORT = "BEST_EFFORT"

_PRIORITY_RANK = {
    Priority.CRITICAL: 4,
    Priority.HIGH: 3,
    Priority.NORMAL: 2,
    Priority.BEST_EFFORT: 1,
}


@dataclass
class PreemptionRecord:
    preemptor_task: str
    preempted_task: str
    reason: str
    timestamp: float = 0.0


@dataclass
class WorkItem:
    task_id: str
    priority: Priority = Priority.NORMAL
    payload: Dict = field(default_factory=dict)


class PriorityPreemptor:
    """Priority lane preemption — critical work preempts best-effort; all audited."""

    def __init__(self):
        self._queue: List[WorkItem] = []
        self._preemption_log: List[PreemptionRecord] = []
        self._active: Optional[str] = None  # current task_id

    def submit(self, item: WorkItem) -> bool:
        """Submit work item. Returns True if admitted."""
        self._queue.append(item)
        self._queue.sort(key=lambda w: _PRIORITY_RANK.get(w.priority, 0), reverse=True)
        return True

    def dispatch(self) -> Optional[WorkItem]:
        """Dispatch highest priority item."""
        if not self._queue:
            return None
        item = self._queue.pop(0)
        self._active = item
        return item

    def preempt(self, critical_task_id: str, reason: str = "") -> Optional[str]:
        """Preempt current best-effort task for critical work. Returns preempted task_id or None."""
        if self._active is None:
            return None
        active_item = self._active if isinstance(self._active, WorkItem) else None
        if active_item is None:
            return None
        if active_item.priority in (Priority.CRITICAL, Priority.HIGH):
            return None  # don't preempt critical/high
        record = PreemptionRecord(
            preemptor_task=critical_task_id,
            preempted_task=active_item.task_id,
            reason=reason or f"preempted by {critical_task_id}",
        )
        import time
        record.timestamp = time.time()
        self._preemption_log.append(record)
        preempted_id = active_item.task_id
        self._queue = [i for i in self._queue if i.task_id != preempted_id]
        self._active = None
        self.submit(WorkItem(task_id=preempted_id, priority=Priority.BEST_EFFORT))
        self.submit(WorkItem(task_id=critical_task_id, priority=Priority.CRITICAL))
        return preempted_id

    @property
    def preemption_log(self) -> List[PreemptionRecord]:
        return list(self._preemption_log)

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    def get_queue(self) -> List[WorkItem]:
        return list(self._queue)
