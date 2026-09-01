"""Background workers for Think Box AI.

Celery-style task queue using asyncio.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from core.foundation.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Task:
    id: str
    name: str
    func: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    completed_at: str | None = None


class WorkerPool:
    def __init__(self, num_workers: int = 4):
        self.num_workers = num_workers
        self.queue: asyncio.Queue = asyncio.Queue()
        self.tasks: dict[str, Task] = {}
        self._workers: list[asyncio.Task] = []

    async def start(self):
        """Start worker pool."""
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(self.num_workers)]
        logger.info(f"Worker pool started: {self.num_workers} workers")

    async def stop(self):
        """Stop all workers."""
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)

    async def submit(self, name: str, func: Callable, *args, **kwargs) -> str:
        """Submit a task to the queue."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = Task(id=task_id, name=name, func=func, args=args, kwargs=kwargs)
        self.tasks[task_id] = task
        await self.queue.put(task_id)
        return task_id

    async def _worker(self, worker_id: int):
        """Worker loop."""
        while True:
            try:
                task_id = await self.queue.get()
                task = self.tasks[task_id]
                task.status = "running"
                task.started_at = datetime.now(timezone.utc).isoformat()
                try:
                    if asyncio.iscoroutinefunction(task.func):
                        task.result = await task.func(*task.args, **task.kwargs)
                    else:
                        task.result = task.func(*task.args, **task.kwargs)
                    task.status = "completed"
                except Exception as e:
                    task.status = "failed"
                    task.error = str(e)
                    logger.error(f"Task {task_id} failed: {e}")
                task.completed_at = datetime.now(timezone.utc).isoformat()
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")

    def get_task(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    def list_tasks(self, status: str | None = None) -> list[Task]:
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks


# Global pool
pool = WorkerPool()


async def setup_periodic_tasks():
    """Schedule recurring tasks."""
    await pool.start()
    # Add periodic tasks here
    # await pool.submit("health_check", check_health)
