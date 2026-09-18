from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class WorkerHeartbeat:
    """Feature 3 (PR82): Worker heartbeats with dead-letter queue.

    Tracks worker liveness via heartbeat timestamps. Stale workers are
    evicted and their in-flight jobs are moved to a dead-letter queue
    with a reason string for later recovery or reassignment.
    """

    def __init__(self, heartbeat_timeout_s: float = 30.0) -> None:
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self._workers: dict[str, dict[str, Any]] = {}
        self._dlq: list[dict[str, Any]] = []

    def register_worker(self, worker_id: str, capabilities: list[str] = []) -> None:
        self._workers[worker_id] = {
            "capabilities": list(capabilities),
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }

    def heartbeat(self, worker_id: str) -> bool:
        if worker_id not in self._workers:
            return False
        self._workers[worker_id]["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        return True

    def evict_stale(self) -> list[str]:
        now = datetime.now(timezone.utc)
        evicted: list[str] = []
        for worker_id in list(self._workers.keys()):
            worker = self._workers[worker_id]
            last_hb = datetime.fromisoformat(worker["last_heartbeat"])
            if (now - last_hb).total_seconds() > self.heartbeat_timeout_s:
                evicted.append(worker_id)
                for job_id in worker.get("assigned_jobs", []):
                    self.move_to_dlq(
                        job_id,
                        reason=f"worker {worker_id} evicted: heartbeat stale",
                    )
                del self._workers[worker_id]
        return evicted

    def move_to_dlq(self, job_id: str, reason: str) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "job_id": job_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._dlq.append(entry)
        return entry

    def get_dlq(self) -> list[dict[str, Any]]:
        return list(self._dlq)

    def get_active_workers(self) -> list[str]:
        return list(self._workers.keys())

    def get_stats(self) -> dict[str, Any]:
        return {
            "active_workers": len(self._workers),
            "dlq_size": len(self._dlq),
            "heartbeat_timeout_s": self.heartbeat_timeout_s,
        }


class TokenBucketRateLimit:
    """Feature 4 (PR82): Per-tenant token-bucket rate limits.

    Each tenant has an independent token bucket. Tokens refill at a
    configured rate per second up to the bucket capacity. Consumes
    return a structured tuple: (allowed, reason, event).
    """

    def __init__(self, capacity: int = 10, refill_rate: float = 1.0) -> None:
        self._default_capacity = capacity
        self._default_refill_rate = refill_rate
        self._tenants: dict[str, dict[str, Any]] = {}
        self._last_refill: dict[str, float] = {}

    def set_tenant(
        self,
        tenant_id: str,
        capacity: int | None = None,
        refill_rate: float | None = None,
    ) -> None:
        self._tenants[tenant_id] = {
            "capacity": capacity if capacity is not None else self._default_capacity,
            "refill_rate": refill_rate if refill_rate is not None else self._default_refill_rate,
            "tokens": float(capacity) if capacity is not None else float(self._default_capacity),
        }
        self._last_refill[tenant_id] = datetime.now(timezone.utc).timestamp()

    def refill(self) -> None:
        now = datetime.now(timezone.utc).timestamp()
        for tenant_id in list(self._tenants.keys()):
            if tenant_id not in self._last_refill:
                self._last_refill[tenant_id] = now
                continue
            elapsed = now - self._last_refill[tenant_id]
            if elapsed <= 0:
                continue
            tenant = self._tenants[tenant_id]
            added = elapsed * tenant["refill_rate"]
            tenant["tokens"] = min(tenant["tokens"] + added, float(tenant["capacity"]))
            self._last_refill[tenant_id] = now

    def consume(self, tenant_id: str, tokens: int = 1) -> tuple[bool, str, dict[str, Any]]:
        if tenant_id not in self._tenants:
            return (
                False,
                "tenant not registered",
                {
                    "tenant_id": tenant_id,
                    "tokens_requested": tokens,
                    "allowed": False,
                    "reason": "tenant not registered",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        if tokens <= 0:
            return (
                False,
                "invalid token count",
                {
                    "tenant_id": tenant_id,
                    "tokens_requested": tokens,
                    "allowed": False,
                    "reason": "invalid token count",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        self.refill()
        tenant = self._tenants[tenant_id]
        if tenant["tokens"] >= tokens:
            tenant["tokens"] -= tokens
            now = datetime.now(timezone.utc)
            event: dict[str, Any] = {
                "tenant_id": tenant_id,
                "tokens_requested": tokens,
                "tokens_deducted": tokens,
                "remaining_balance": tenant["tokens"],
                "allowed": True,
                "reason": "ok",
                "timestamp": now.isoformat(),
            }
            return (True, "ok", event)
        now = datetime.now(timezone.utc)
        event = {
            "tenant_id": tenant_id,
            "tokens_requested": tokens,
            "tokens_deducted": 0,
            "remaining_balance": tenant["tokens"],
            "allowed": False,
            "reason": "insufficient tokens",
            "timestamp": now.isoformat(),
        }
        return (False, "insufficient tokens", event)

    def get_balance(self, tenant_id: str) -> float:
        if tenant_id not in self._tenants:
            return 0.0
        self.refill()
        return self._tenants[tenant_id]["tokens"]

    def get_stats(self) -> dict[str, Any]:
        self.refill()
        total_capacity = sum(t["capacity"] for t in self._tenants.values())
        total_balance = sum(t["tokens"] for t in self._tenants.values())
        return {
            "tenant_count": len(self._tenants),
            "default_capacity": self._default_capacity,
            "default_refill_rate": self._default_refill_rate,
            "total_capacity": total_capacity,
            "total_balance": total_balance,
        }
