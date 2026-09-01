#!/usr/bin/env python3
"""Remote monitoring for Think Box AI.

Watch GPU jobs from CLI, monitor agent status, view logs.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.cli_memory import memory
from core.foundation.logging import get_logger

logger = get_logger("monitor")


class RemoteMonitor:
    """Monitor remote agents and GPU jobs."""

    def __init__(self):
        self.status_file = Path("data/monitor_status.json")
        self.log_file = Path("data/monitor_log.jsonl")

    def update_status(self, component: str, status: dict):
        """Update component status."""
        all_status = {}
        if self.status_file.exists():
            all_status = json.loads(self.status_file.read_text())
        all_status[component] = {**status, "updated_at": datetime.now(timezone.utc).isoformat()}
        self.status_file.write_text(json.dumps(all_status, indent=2))

    def get_status(self, component: str | None = None) -> dict:
        """Get status of one or all components."""
        if not self.status_file.exists():
            return {}
        all_status = json.loads(self.status_file.read_text())
        if component:
            return all_status.get(component, {})
        return all_status

    def log_event(self, event: str, details: dict | None = None):
        """Log a monitoring event."""
        entry = {
            "event": event,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_logs(self, event_type: str | None = None, limit: int = 50) -> list[dict]:
        """Get monitoring logs."""
        if not self.log_file.exists():
            return []
        logs = []
        with open(self.log_file) as f:
            for line in f:
                entry = json.loads(line.strip())
                if event_type and entry["event"] != event_type:
                    continue
                logs.append(entry)
        return logs[-limit:]

    def watch_job(self, job_id: str, interval: int = 5):
        """Watch a job's progress in real-time."""
        print(f"Watching job: {job_id} (Ctrl+C to stop)")
        try:
            while True:
                # Check job status
                for state_dir in ["queue", "active", "done", "blocked"]:
                    jf = Path("jobs") / state_dir / f"{job_id}.json"
                    if jf.exists():
                        job = json.loads(jf.read_text())
                        status = job.get("evaluation", {}).get("verdict", state_dir)
                        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Status: {status}", end="")
                        if state_dir in ("done", "blocked"):
                            print(f"\nJob finished: {status}")
                            return
                        break
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped watching.")

    def watch_queue(self, interval: int = 5):
        """Watch the job queue in real-time."""
        print(f"Watching queue (Ctrl+C to stop)")
        try:
            while True:
                counts = {"queue": 0, "active": 0, "done": 0, "blocked": 0}
                for state in counts:
                    d = Path("jobs") / state
                    if d.exists():
                        counts[state] = len(list(d.glob("job_*.json")))
                total = sum(counts.values())
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] Queue: {counts['queue']} | Active: {counts['active']} | Done: {counts['done']} | Blocked: {counts['blocked']} | Total: {total}", end="")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped watching.")

    def get_agent_status(self, agent_id: str) -> dict:
        """Get status of a sub-agent."""
        from core.spawner import spawner
        agent = spawner.get(agent_id)
        if agent:
            return agent.to_dict()
        return {"error": "Agent not found"}

    def list_active_agents(self) -> list[dict]:
        """List all active agents."""
        from core.spawner import spawner
        return [a.to_dict() for a in spawner.list_active()]


# Global monitor
monitor = RemoteMonitor()
