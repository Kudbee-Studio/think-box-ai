#!/usr/bin/env python3
"""GPU job queue for Think Box AI.

Pre-built jobs ready for execution when GPU is available.
Queue persists to disk, drains in priority order.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

QUEUE_PATH = Path("data/gpu_queue.jsonl")


class GPUQueue:
    """Priority queue for GPU jobs."""

    def __init__(self):
        QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.jobs: list[dict] = []
        self._load()

    def _load(self):
        if QUEUE_PATH.exists():
            with open(QUEUE_PATH) as f:
                self.jobs = [json.loads(l) for l in f if l.strip()]

    def _save(self):
        with open(QUEUE_PATH, "w") as f:
            for job in self.jobs:
                f.write(json.dumps(job) + "\n")

    def add(self, intent: str, hat: str = "researcher", priority: str = "normal", inputs: dict | None = None) -> str:
        """Add a job to the queue."""
        job_id = f"gpu_{uuid.uuid4().hex[:8]}"
        priority_val = {"urgent": 0, "normal": 1, "low": 2}.get(priority, 1)
        job = {
            "id": job_id,
            "intent": intent,
            "hat": hat,
            "priority": priority,
            "priority_val": priority_val,
            "inputs": inputs or {},
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "gpu_time_estimate": self._estimate_time(intent),
            "cost_estimate": self._estimate_cost(intent),
        }
        self.jobs.append(job)
        self.jobs.sort(key=lambda j: j["priority_val"])
        self._save()
        return job_id

    def batch_add(self, jobs: list[dict]) -> list[str]:
        """Add multiple jobs at once."""
        ids = []
        for job_data in jobs:
            job_id = self.add(
                intent job_data.get("intent", ""),
                hat=job_data.get("hat", "researcher"),
                priority=job_data.get("priority", "normal"),
                inputs=job_data.get("inputs"),
            )
            ids.append(job_id)
        return ids

    def next(self) -> dict | None:
        """Get the next job to execute."""
        for job in self.jobs:
            if job["status"] == "queued":
                return job
        return None

    def complete(self, job_id: str, result: dict):
        """Mark a job as completed."""
        for job in self.jobs:
            if job["id"] == job_id:
                job["status"] = "completed"
                job["result"] = result
                job["completed_at"] = datetime.now(timezone.utc).isoformat()
                break
        self._save()

    def drain(self) -> list[dict]:
        """Get all queued jobs (for GPU execution)."""
        return [j for j in self.jobs if j["status"] == "queued"]

    def status(self) -> dict:
        """Get queue status."""
        queued = len([j for j in self.jobs if j["status"] == "queued"])
        completed = len([j for j in self.jobs if j["status"] == "completed"])
        total_cost = sum(j.get("cost_estimate", 0) for j in self.jobs if j["status"] == "queued")
        total_time = sum(j.get("gpu_time_estimate", 0) for j in self.jobs if j["status"] == "queued"])
        return {
            "queued": queued,
            "completed": completed,
            "total": len(self.jobs),
            "estimated_cost": round(total_cost, 2),
            "estimated_gpu_minutes": round(total_time, 1),
        }

    def _estimate_time(self, intent: str) -> float:
        """Estimate GPU time in minutes based on intent complexity."""
        # Simple heuristic based on word count and complexity
        words = len(intent.split())
        if "research" in intent.lower() or "analyze" in intent.lower():
            return max(5.0, words * 0.5)
        elif "generate" in intent.lower() or "create" in intent.lower():
            return max(10.0, words * 1.0)
        return max(3.0, words * 0.3)

    def _estimate_cost(self, intent: str) -> float:
        """Estimate cost in USD based on GPU time."""
        gpu_time = self._estimate_time(intent)
        # Assume $0.02 per minute for spot GPU
        return round(gpu_time * 0.02, 4)

    def clear_completed(self):
        """Remove completed jobs from queue."""
        self.jobs = [j for j in self.jobs if j["status"] != "completed"]
        self._save()


# Pre-built job templates
JOB_TEMPLATES = {
    "research_token": {
        "intent": "Research {token} token deployment and supply across indexers",
        "hat": "researcher",
        "priority": "normal",
    },
    "compare_indexers": {
        "intent": "Compare {inscription_id} across all available Doginals indexers",
        "hat": "researcher",
        "priority": "normal",
    },
    "wallet_scan": {
        "intent": "Scan wallet {address} for Doginals holdings and provenance",
        "hat": "researcher",
        "priority": "low",
    },
    "generate_art": {
        "intent": "Generate {description} as a Doginal inscription",
        "hat": "camera",
        "priority": "normal",
    },
    "security_audit": {
        "intent": "Audit smart contract {address} for vulnerabilities",
        "hat": "researcher",
        "priority": "urgent",
    },
}


# Global queue
gpu_queue = GPUQueue()
