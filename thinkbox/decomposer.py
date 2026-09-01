"""Task decomposition engine for ThinkBox AI.

Parses incoming root workspace goals into a Directed Acyclic Graph (DAG)
of micro-tasks with context limits and dependency metadata.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


MAX_TASK_TOKENS = 500
TOKEN_CHAR_RATIO = 4


@dataclass
class TaskNode:
    id: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    state: str = "pending"
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskGraph:
    root_id: str
    tasks: dict[str, TaskNode] = field(default_factory=dict)

    def get_ready_tasks(self) -> list[TaskNode]:
        ready = []
        for task in self.tasks.values():
            if task.state != "pending":
                continue
            if all(self.tasks[dep].state == "completed" for dep in task.dependencies):
                ready.append(task)
        return ready

    def get_execution_order(self) -> list[list[str]]:
        layers: list[list[str]] = []
        completed = set()
        remaining = set(self.tasks.keys())

        while remaining:
            layer = []
            for task_id in remaining:
                task = self.tasks[task_id]
                if all(dep in completed for dep in task.dependencies):
                    layer.append(task_id)
            if not layer:
                break
            layers.append(layer)
            completed.update(layer)
            remaining.difference_update(layer)

        return layers


class TaskDecomposer:
    def __init__(self, max_tokens: int = MAX_TASK_TOKENS):
        self.max_tokens = max_tokens

    def estimate_tokens(self, text: str) -> int:
        return len(text) // TOKEN_CHAR_RATIO + 1

    def decompose(self, goal: str) -> TaskGraph:
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        root = TaskNode(
            id=task_id,
            description=goal[:self.max_tokens * TOKEN_CHAR_RATIO],
            token_count=self.estimate_tokens(goal),
        )
        return TaskGraph(root_id=task_id, tasks={task_id: root})

    def decompose_with_subtasks(self, goal: str, subtasks: list[str]) -> TaskGraph:
        root_id = f"task_{uuid.uuid4().hex()[8:]}"
        root = TaskNode(id=root_id, description=goal[:100], dependencies=[])
        tasks = {root_id: root}

        for i, desc in enumerate(subtasks):
            task_id = f"task_{uuid.uuid4().hex()[8:]}"
            node = TaskNode(
                id=task_id,
                description=desc[:self.max_tokens * TOKEN_CHAR_RATIO],
                dependencies=[root_id],
                token_count=self.estimate_tokens(desc),
            )
            tasks[task_id] = node

        return TaskGraph(root_id=root_id, tasks=tasks)
