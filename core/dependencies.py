#!/usr/bin/env python3
"""Job dependencies for Think Box AI.

Define dependencies between jobs so they execute in correct order.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEPS_PATH = Path("data/job_dependencies.jsonl")


class JobDependency:
    """A dependency relationship between two jobs."""

    def __init__(self, job_id: str, depends_on: str, dependency_type: str = "completion"):
        self.job_id = job_id
        self.depends_on = depends_on
        self.dependency_type = dependency_type  # completion, output, approval
        self.created_at = datetime.now(timezone.utc).isoformat()


class DependencyManager:
    """Manage job dependencies."""

    def __init__(self):
        self.dependencies: list[JobDependency] = []
        self._load()

    def _load(self):
        if DEPS_PATH.exists():
            with open(DEPS_PATH) as f:
                for line in f:
                    data = json.loads(line.strip())
                    dep = JobDependency(data["job_id"], data["depends_on"], data.get("dependency_type", "completion"))
                    self.dependencies.append(dep)

    def _save(self):
        DEPS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DEPS_PATH, "w") as f:
            for dep in self.dependencies:
                f.write(json.dumps({
                    "job_id": dep.job_id, "depends_on": dep.depends_on,
                    "dependency_type": dep.dependency_type, "created_at": dep.created_at,
                }) + "\n")

    def add(self, job_id: str, depends_on: str, dependency_type: str = "completion"):
        """Add a dependency."""
        dep = JobDependency(job_id, depends_on, dependency_type)
        self.dependencies.append(dep)
        self._save()
        return dep

    def get_dependencies(self, job_id: str) -> list[JobDependency]:
        """Get all dependencies for a job."""
        return [d for d in self.dependencies if d.job_id == job_id]

    def get_dependents(self, job_id: str) -> list[JobDependency]:
        """Get all jobs that depend on this job."""
        return [d for d in self.dependencies if d.depends_on == job_id]

    def is_ready(self, job_id: str) -> bool:
        """Check if a job is ready to run (all dependencies met)."""
        deps = self.get_dependencies(job_id)
        if not deps:
            return True

        for dep in deps:
            # Check if dependency is met
            done_file = Path("jobs") / "done" / f"{dep.depends_on}.json"
            if not done_file.exists():
                return False
        return True

    def get_execution_order(self, job_ids: list[str]) -> list[str]:
        """Topological sort of jobs based on dependencies."""
        visited = set()
        order = []

        def _visit(jid: str):
            if jid in visited:
                return
            visited.add(jid)
            for dep in self.get_dependencies(jid):
                _visit(dep.depends_on)
            order.append(jid)

        for jid in job_ids:
            _visit(jid)
        return order

    def list_all(self) -> list[dict]:
        return [{"job_id": d.job_id, "depends_on": d.depends_on, "type": d.dependency_type} for d in self.dependencies]


# Global manager
dependencies = DependencyManager()
