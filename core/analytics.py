"""Analytics module for Think Box AI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("data/analytics.db")


class Analytics:
    def __init__(self):
        self.events: list[dict] = []
        self._load()

    def _load(self):
        f = Path("data/analytics_events.jsonl")
        if f.exists():
            with open(f) as fh:
                self.events = [json.loads(l) for l in fh if l.strip()]

    def track(self, event: str, properties: dict | None = None):
        entry = {
            "event": event,
            "properties": properties or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.events.append(entry)
        with open("data/analytics_events.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_stats(self) -> dict:
        stats = {
            "total_events": len(self.events),
            "events_by_type": {},
            "jobs_created": 0,
            "jobs_completed": 0,
            "api_calls": 0,
            "errors": 0,
        }
        for e in self.events:
            event_type = e["event"]
            stats["events_by_type"][event_type] = stats["events_by_type"].get(event_type, 0) + 1
            if event_type == "job_created":
                stats["jobs_created"] += 1
            elif event_type == "job_completed":
                stats["jobs_completed"] += 1
            elif event_type == "api_call":
                stats["api_calls"] += 1
            elif event_type == "error":
                stats["errors"] += 1
        return stats

    def get_daily_stats(self, days: int = 7) -> list[dict]:
        from collections import defaultdict
        daily = defaultdict(lambda: {"events": 0, "jobs": 0, "errors": 0})
        for e in self.events:
            day = e["timestamp"][:10]
            daily[day]["events"] += 1
            if e["event"] == "job_completed":
                daily[day]["jobs"] += 1
            elif e["event"] == "error":
                daily[day]["errors"] += 1
        return [{"date": d, **s} for d, s in sorted(daily.items())][-days:]
