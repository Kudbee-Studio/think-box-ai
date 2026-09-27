"""Task decomposition engine for ThinkBox AI.

Parses incoming root workspace goals into a Directed Acyclic Graph (DAG)
of micro-tasks with context limits and dependency metadata.
Integrates with the Token Whip Protocol for dynamic token management.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from thinkbox.whip import TokenWhipProtocol, estimate_tokens, STANDARD_TOKEN_ALLOWANCE


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
    def __init__(self, max_tokens: int = STANDARD_TOKEN_ALLOWANCE, whip_protocol: TokenWhipProtocol | None = None):
        self.max_tokens = max_tokens
        self.whip = whip_protocol or TokenWhipProtocol()

    def estimate_tokens(self, text: str) -> int:
        return estimate_tokens(text)

    def decompose(self, goal: str, prior_recommendation: dict[str, Any] | None = None) -> TaskGraph:
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        root = TaskNode(
            id=task_id,
            description=goal[:self.max_tokens * TOKEN_CHAR_RATIO],
            token_count=self.estimate_tokens(goal),
        )
        tasks = {task_id: root}

        if prior_recommendation is not None:
            rec_type = prior_recommendation.get("type", "")
            adjustments = prior_recommendation.get("adjustments", [])
            if rec_type == "regression_followup":
                for adj in adjustments:
                    metric = adj.get("metric", "unknown")
                    action = adj.get("action", "investigate")
                    sub_id = f"task_{uuid.uuid4().hex[:8]}"
                    node = TaskNode(
                        id=sub_id,
                        description=f"Investigate root cause for {metric}: {action}",
                        dependencies=[task_id],
                        token_count=self.estimate_tokens(f"Investigate {metric}"),
                        metadata={
                            "generated_from": "prior_recommendation",
                            "recommendation_type": rec_type,
                            "target_metric": metric,
                            "recommended_action": action,
                        },
                    )
                    tasks[sub_id] = node
            elif rec_type == "anomaly_followup":
                for adj in adjustments:
                    anomaly = adj.get("type", "unknown")
                    action = adj.get("action", "investigate")
                    sub_id = f"task_{uuid.uuid4().hex[:8]}"
                    node = TaskNode(
                        id=sub_id,
                        description=f"Investigate anomaly: {anomaly} ({action})",
                        dependencies=[task_id],
                        token_count=self.estimate_tokens(f"Investigate {anomaly}"),
                        metadata={
                            "generated_from": "prior_recommendation",
                            "recommendation_type": rec_type,
                            "anomaly_type": anomaly,
                            "recommended_action": action,
                        },
                    )
                    tasks[sub_id] = node

        return TaskGraph(root_id=task_id, tasks=tasks)

    def decompose_with_subtasks(self, goal: str, subtasks: list[str]) -> TaskGraph:
        root_id = f"task_{uuid.uuid4().hex[:8]}"
        root = TaskNode(id=root_id, description=goal[:100], dependencies=[])
        tasks = {root_id: root}

        for i, desc in enumerate(subtasks):
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            node = TaskNode(
                id=task_id,
                description=desc[:self.max_tokens * TOKEN_CHAR_RATIO],
                dependencies=[root_id],
                token_count=self.estimate_tokens(desc),
            )
            tasks[task_id] = node

        return TaskGraph(root_id=root_id, tasks=tasks)
