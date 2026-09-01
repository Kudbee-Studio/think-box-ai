#!/usr/bin/env python3
"""Webhook triggers and scheduled jobs for Think Box AI.

Cron-like scheduling + webhook-triggered job execution.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEDULE_PATH = Path("data/schedule.jsonl")


class ScheduledJob:
    """A job that runs on a schedule."""

    def __init__(self, name: str, schedule: str, intent: str, hat: str = "researcher"):
        self.id = f"sched_{name}"
        self.name = name
        self.schedule = schedule  # cron-like: "*/5 * * * *" (every 5 min)
        self.intent = intent
        self.hat = hat
        self.enabled = True
        self.last_run: str | None = None
        self.last_status: str | None = None
        self.created_at = datetime.now(timezone.utc).isoformat()


class ScheduleManager:
    """Manage scheduled jobs."""

    def __init__(self):
        self.jobs: dict[str, ScheduledJob] = {}
        self._load()

    def _load(self):
        if SCHEDULE_PATH.exists():
            with open(SCHEDULE_PATH) as f:
                for line in f:
                    data = json.loads(line.strip())
                    job = ScheduledJob(data["name"], data["schedule"], data["intent"], data.get("hat", "researcher"))
                    job.id = data["id"]
                    job.enabled = data.get("enabled", True)
                    job.last_run = data.get("last_run")
                    job.last_status = data.get("last_status")
                    self.jobs[job.id] = job

    def _save(self):
        SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SCHEDULE_PATH, "w") as f:
            for job in self.jobs.values():
                f.write(json.dumps({
                    "id": job.id, "name": job.name, "schedule": job.schedule,
                    "intent": job.intent, "hat": job.hat, "enabled": job.enabled,
                    "last_run": job.last_run, "last_status": job.last_status,
                }) + "\n")

    def add(self, name: str, schedule: str, intent: str, hat: str = "researcher"):
        """Add a scheduled job."""
        job = ScheduledJob(name, schedule, intent, hat)
        self.jobs[job.id] = job
        self._save()
        return job

    def remove(self, name: str):
        job_id = f"sched_{name}"
        if job_id in self.jobs:
            del self.jobs[job_id]
            self._save()

    def list(self) -> list[dict]:
        return [{"id": j.id, "name": j.name, "schedule": j.schedule, "intent": j.intent, "enabled": j.enabled, "last_run": j.last_run} for j in self.jobs.values()]

    def check_due(self) -> list[ScheduledJob]:
        """Check which jobs are due to run."""
        due = []
        now = datetime.now(timezone.utc)
        for job in self.jobs.values():
            if not job.enabled:
                continue
            if self._is_due(job.schedule, now, job.last_run):
                due.append(job)
        return due

    def _is_due(self, schedule: str, now: datetime, last_run: str | None) -> bool:
        """Simple cron matching."""
        parts = schedule.split()
        if len(parts) != 5:
            return False
        minute, hour, day, month, weekday = parts

        if minute != "*" and int(minute) != now.minute:
            return False
        if hour != "*" and int(hour) != now.hour:
            return False
        if day != "*" and int(day) != now.day:
            return False
        if month != "*" and int(month) != now.month:
            return False
        if weekday != "*" and int(weekday) != now.weekday():
            return False

        # Don't run more than once per minute
        if last_run:
            last = datetime.fromisoformat(last_run)
            if (now - last).total_seconds() < 60:
                return False

        return True


# Global scheduler
scheduler = ScheduleManager()
