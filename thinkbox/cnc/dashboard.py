"""ROI dashboard for CNC manufacturing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ROIStats:
    programming_hours_avoided: float = 0.0
    quote_turnaround_days: float = 0.0
    cycle_time_change_pct: float = 0.0
    scrap_rework_avoided: float = 0.0
    successful_reuse_count: int = 0
    validation_failures_caught: int = 0
    jobs_completed: int = 0
    knowledge_retained_count: int = 0
    total_savings_avoided: float = 0.0

    def model_dump(self) -> dict[str, Any]:
        return {"programming_hours_avoided": self.programming_hours_avoided, "quote_turnaround_days": self.quote_turnaround_days, "cycle_time_change_pct": self.cycle_time_change_pct, "scrap_rework_avoided": self.scrap_rework_avoided, "successful_reuse_count": self.successful_reuse_count, "validation_failures_caught": self.validation_failures_caught, "jobs_completed": self.jobs_completed, "knowledge_retained_count": self.knowledge_retained_count, "total_savings_avoided": self.total_savings_avoided}


class ROIDashboard:
    def __init__(self):
        self._stats = ROIStats()

    def compute_stats(self) -> ROIStats:
        return self._stats

    def generate_report(self) -> str:
        stats = self._stats
        return f"""CNC ROI Report
{'=' * 50}
Programming Hours Avoided: {stats.programming_hours_avoided}
Quote Turnaround: {stats.quote_turnaround_days}d
Cycle Time Change: {stats.cycle_time_change_pct:+.1f}%
Scrap/Rework Avoided: ${stats.scrap_rework_avoided:,.0f}
Successful Reuse: {stats.successful_reuse_count}
Validation Failures Caught: {stats.validation_failures_caught}
Jobs Completed: {stats.jobs_completed}
Knowledge Retained: {stats.knowledge_retained_count}
Total Savings: ${stats.total_savings_avoided:,.0f}/year
"""

    def to_dict(self) -> dict[str, Any]:
        return self._stats.model_dump()
