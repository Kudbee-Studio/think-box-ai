"""KUDBEE Control Fabric — Live substrate binding.

Binds Think Boxes and the control fabric to the actual running substrate
instead of a hardcoded string. Detects the Upstash Box (the Firecracker-
class microVM we run inside), probes available isolation tools, and
persists Think Box snapshots to the Upstash Vector memory layer so work
survives box restarts — the system of record above the model session.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from thinkbox.workspace import ThinkBox

logger = logging.getLogger(__name__)


def detect_substrate() -> str:
    """Return the live substrate from the environment we actually run in."""
    box_url = os.environ.get("UPSTASH_PUBLIC_BOX_URL", "")
    if box_url:
        try:
            from urllib.parse import urlparse

            host = urlparse(box_url).hostname or "upstash-box"
            return host
        except Exception:
            return "upstash-box"
    if os.environ.get("THINKBOX_UPCLOUD_API_TOKEN"):
        return "upcloud-gpu"
    if os.environ.get("CI"):
        return "ci"
    return "local"


@dataclass
class IsolationProbe:
    tool: str
    available: bool
    path: str = ""


@dataclass
class SubstrateReport:
    substrate: str
    isolation_tools: list[IsolationProbe] = field(default_factory=list)
    vector_sync: bool = False
    box_url: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "substrate": self.substrate,
            "isolation_tools": {p.tool: p.available for p in self.isolation_tools},
            "vector_sync": self.vector_sync,
            "box_url": self.box_url,
            "timestamp": self.timestamp,
        }


class SubstrateProbe:
    """Detects the running substrate and its isolation capabilities."""

    TOOLS = ("unshare", "bwrap", "docker", "podman", "firecracker-jailer", "cloudflared")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reports: list[SubstrateReport] = []

    def probe(self) -> SubstrateReport:
        box_url = os.environ.get("UPSTASH_PUBLIC_BOX_URL", "")
        vector = bool(os.environ.get("UPSTASH_VECTOR_REST_URL") and os.environ.get("UPSTASH_VECTOR_REST_TOKEN"))
        tools = [IsolationProbe(tool=t, available=bool(shutil.which(t)), path=shutil.which(t) or "") for t in self.TOOLS]
        report = SubstrateReport(
            substrate=detect_substrate(),
            isolation_tools=tools,
            vector_sync=vector,
            box_url=box_url,
        )
        with self._lock:
            self._reports.append(report)
        return report

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            if limit <= 0:
                return []
            return [r.to_dict() for r in self._reports[-limit:]]


class ThinkBoxVectorSync:
    """Persists Think Box snapshots to the Upstash Vector memory layer.

    Uses a deterministic 1536-dim vector derived from the snapshot id so a
    box can be recovered by its box_id after a substrate restart. Matches
    the proven REST shape: /upsert (POST), /fetch (POST), /delete (POST).
    """

    DIMENSIONS = 1536

    def __init__(self) -> None:
        self._url = os.environ.get("UPSTASH_VECTOR_REST_URL", "").rstrip("/")
        self._token = os.environ.get("UPSTASH_VECTOR_REST_TOKEN", "")
        self._enabled = bool(self._url and self._token)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @staticmethod
    def _vector_for(snapshot_id: str) -> list[float]:
        digest = hashlib.sha256(snapshot_id.encode()).digest()
        # Expand 32 bytes into a deterministic 1536-dim vector in [0,1).
        out: list[float] = []
        while len(out) < ThinkBoxVectorSync.DIMENSIONS:
            out.extend(v / 255.0 for v in digest)
            digest = hashlib.sha256(digest).digest()
        return out[: ThinkBoxVectorSync.DIMENSIONS]

    def snapshot(self, box: ThinkBox) -> bool:
        if not self._enabled:
            return False
        payload = [{
            "id": f"thinkbox:{box.box_id}",
            "vector": self._vector_for(box.box_id),
            "metadata": box.snapshot(),
        }]
        return self._request("/upsert", payload)

    def fetch(self, box_id: str) -> dict[str, Any] | None:
        if not self._enabled:
            return None
        body = self._request_raw("/fetch", {"ids": [f"thinkbox:{box_id}"], "includeMetadata": True})
        if not body:
            return None
        try:
            results = body.get("result", [])
            return results[0].get("metadata") if results else None
        except (AttributeError, KeyError):
            return None

    def delete(self, box_id: str) -> bool:
        if not self._enabled:
            return False
        return self._request("/delete", {"ids": [f"thinkbox:{box_id}"]})

    def _request(self, path: str, payload: Any) -> bool:
        return self._request_raw(path, payload) is not None

    def _request_raw(self, path: str, payload: Any) -> dict[str, Any] | None:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            self._url + path,
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except (urllib.error.HTTPError, OSError):
            return None


def bind_think_box(box: ThinkBox, sync: ThinkBoxVectorSync | None = None) -> dict[str, Any]:
    """Bind a Think Box to the live substrate and memory layer."""
    sync = sync or ThinkBoxVectorSync()
    substrate = detect_substrate()
    box.substrate = substrate
    persisted = sync.snapshot(box)
    return {
        "box_id": box.box_id,
        "substrate": substrate,
        "persisted": persisted,
    }


# Box Pool Management — Enable 100x scale verification


class BoxHealthStatus(Enum):
    """Health status of a Box endpoint."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class BoxPoolError(RuntimeError):
    """Box pool error — all boxes failed or no boxes available."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_type = "box_pool_error"


@dataclass
class BoxEndpoint:
    """Represents a Box endpoint in the pool."""
    url: str
    name: str = ""
    status: BoxHealthStatus = BoxHealthStatus.HEALTHY
    consecutive_failures: int = 0
    last_check: str = ""
    total_requests: int = 0
    successful_requests: int = 0

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self._extract_hostname()

    def _extract_hostname(self) -> str:
        """Extract hostname from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.url)
            return parsed.hostname or self.url
        except Exception:
            return self.url

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "name": self.name,
            "status": self.status.value,
            "consecutive_failures": self.consecutive_failures,
            "last_check": self.last_check,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "success_rate": self.successful_requests / self.total_requests if self.total_requests > 0 else 0.0,
        }


class BoxHealthChecker:
    """Periodic health checker for Box endpoints."""

    FAILURE_THRESHOLD = 3
    CHECK_TIMEOUT = 5

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._endpoints: dict[str, BoxEndpoint] = {}

    def register(self, url: str, name: str = "") -> None:
        """Register a Box endpoint for monitoring."""
        with self._lock:
            if url not in self._endpoints:
                self._endpoints[url] = BoxEndpoint(url=url, name=name)
                logger.info(f"Registered box endpoint: {name or url}")

    def check_health(self, url: str) -> BoxHealthStatus:
        """Check health of a single Box endpoint."""
        if url not in self._endpoints:
            return BoxHealthStatus.UNHEALTHY

        endpoint = self._endpoints[url]

        try:
            req = urllib.request.Request(
                url.rstrip("/") + "/health",
                method="GET",
                headers={"Connection": "close"},
            )
            with urllib.request.urlopen(req, timeout=self.CHECK_TIMEOUT) as resp:
                if resp.status == 200:
                    endpoint.status = BoxHealthStatus.HEALTHY
                    endpoint.consecutive_failures = 0
                    endpoint.last_check = datetime.now(timezone.utc).isoformat()
                    logger.debug(f"Health check PASSED for {endpoint.name}: {url}")
                    return BoxHealthStatus.HEALTHY
                else:
                    endpoint.status = BoxHealthStatus.DEGRADED
                    endpoint.consecutive_failures += 1
                    endpoint.last_check = datetime.now(timezone.utc).isoformat()
                    logger.warning(f"Health check DEGRADED for {endpoint.name}: HTTP {resp.status}")
                    return BoxHealthStatus.DEGRADED
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, Exception) as e:
            endpoint.consecutive_failures += 1
            endpoint.last_check = datetime.now(timezone.utc).isoformat()

            if endpoint.consecutive_failures >= self.FAILURE_THRESHOLD:
                endpoint.status = BoxHealthStatus.UNHEALTHY
                logger.error(f"Health check FAILED for {endpoint.name}: marked UNHEALTHY after {endpoint.consecutive_failures} failures")
            else:
                logger.warning(f"Health check attempt {endpoint.consecutive_failures}/{self.FAILURE_THRESHOLD} failed for {endpoint.name}: {e}")

            return endpoint.status

    def check_all(self) -> dict[str, BoxHealthStatus]:
        """Check all registered endpoints."""
        results = {}
        for url in list(self._endpoints.keys()):
            results[url] = self.check_health(url)
        return results

    def get_endpoint(self, url: str) -> BoxEndpoint | None:
        """Get endpoint metadata."""
        with self._lock:
            return self._endpoints.get(url)

    def record_success(self, url: str) -> None:
        """Record a successful request."""
        with self._lock:
            if url in self._endpoints:
                endpoint = self._endpoints[url]
                endpoint.total_requests += 1
                endpoint.successful_requests += 1
                endpoint.consecutive_failures = 0
                if endpoint.status == BoxHealthStatus.UNHEALTHY:
                    endpoint.status = BoxHealthStatus.DEGRADED

    def record_failure(self, url: str) -> None:
        """Record a failed request."""
        with self._lock:
            if url in self._endpoints:
                endpoint = self._endpoints[url]
                endpoint.total_requests += 1
                endpoint.consecutive_failures += 1
                if endpoint.consecutive_failures >= self.FAILURE_THRESHOLD:
                    endpoint.status = BoxHealthStatus.UNHEALTHY
                    logger.error(f"Circuit breaker OPEN for {endpoint.name}: {endpoint.consecutive_failures} consecutive failures")

    def all_endpoints(self) -> list[BoxEndpoint]:
        """Get all registered endpoints."""
        with self._lock:
            return list(self._endpoints.values())

    def healthy_endpoints(self) -> list[BoxEndpoint]:
        """Get all healthy endpoints."""
        with self._lock:
            return [e for e in self._endpoints.values() if e.status == BoxHealthStatus.HEALTHY]

    def available_endpoints(self) -> list[BoxEndpoint]:
        """Get all available endpoints (healthy or degraded)."""
        with self._lock:
            return [e for e in self._endpoints.values() if e.status != BoxHealthStatus.UNHEALTHY]


class BoxPool:
    """Round-robin Box endpoint pool with circuit-breaker failover."""

    def __init__(self, box_urls: list[str] | None = None) -> None:
        """Initialize Box pool.

        Args:
            box_urls: List of Box endpoint URLs. If None, parsed from environment.
        """
        self._lock = threading.Lock()
        self._current_index = 0
        self._health_checker = BoxHealthChecker()
        self._assignment_store: dict[str, str] = {}  # agent_id -> box_url

        # Parse box URLs from environment or use provided list
        if box_urls is None:
            box_urls = self._parse_box_urls_from_env()

        if not box_urls:
            logger.warning("No Box endpoints configured; falling back to single default")
            box_urls = [os.environ.get("UPSTASH_PUBLIC_BOX_URL", "http://localhost:8000")]

        for url in box_urls:
            self._health_checker.register(url)
            logger.info(f"Added box endpoint to pool: {url}")

    @staticmethod
    def _parse_box_urls_from_env() -> list[str]:
        """Parse Box URLs from environment variables.

        Looks for:
        - UPSTASH_PUBLIC_BOX_URL (single URL)
        - THINKBOX_BOX_POOL_URLS (comma-separated URLs)
        """
        urls = []

        # Try comma-separated list first
        pool_urls = os.environ.get("THINKBOX_BOX_POOL_URLS", "").strip()
        if pool_urls:
            urls = [u.strip() for u in pool_urls.split(",") if u.strip()]
            logger.debug(f"Parsed {len(urls)} box URLs from THINKBOX_BOX_POOL_URLS")

        # Fall back to single URL
        if not urls:
            single_url = os.environ.get("UPSTASH_PUBLIC_BOX_URL", "").strip()
            if single_url:
                urls = [single_url]
                logger.debug(f"Parsed 1 box URL from UPSTASH_PUBLIC_BOX_URL")

        return urls

    def allocate(self, agent_id: str) -> str:
        """Allocate an agent to a Box endpoint using round-robin."""
        with self._lock:
            available = self._health_checker.available_endpoints()

            if not available:
                # All boxes unhealthy; try to use any endpoint
                all_endpoints = self._health_checker.all_endpoints()
                if not all_endpoints:
                    raise BoxPoolError("No Box endpoints available in pool")
                available = all_endpoints

            # Round-robin allocation
            self._current_index = self._current_index % len(available)
            selected = available[self._current_index]
            self._current_index += 1

            self._assignment_store[agent_id] = selected.url
            logger.debug(f"Allocated agent {agent_id} to {selected.name}")
            return selected.url

    def get_assignment(self, agent_id: str) -> str | None:
        """Get the assigned Box endpoint for an agent."""
        with self._lock:
            return self._assignment_store.get(agent_id)

    def release(self, agent_id: str) -> None:
        """Release an agent's assignment."""
        with self._lock:
            if agent_id in self._assignment_store:
                del self._assignment_store[agent_id]
                logger.debug(f"Released agent {agent_id}")

    def record_success(self, agent_id: str) -> None:
        """Record successful request for an agent."""
        box_url = self.get_assignment(agent_id)
        if box_url:
            self._health_checker.record_success(box_url)

    def record_failure(self, agent_id: str) -> None:
        """Record failed request for an agent."""
        box_url = self.get_assignment(agent_id)
        if box_url:
            self._health_checker.record_failure(box_url)

    def check_health(self) -> dict[str, Any]:
        """Check health of all Box endpoints."""
        results = self._health_checker.check_all()
        return {
            url: self._health_checker.get_endpoint(url).to_dict()
            for url in results.keys()
        }

    def get_status(self) -> dict[str, Any]:
        """Get current pool status."""
        with self._lock:
            endpoints = self._health_checker.all_endpoints()
            healthy = self._health_checker.healthy_endpoints()
            available = self._health_checker.available_endpoints()

            return {
                "total_endpoints": len(endpoints),
                "healthy_endpoints": len(healthy),
                "available_endpoints": len(available),
                "active_allocations": len(self._assignment_store),
                "endpoints": [e.to_dict() for e in endpoints],
            }

    def enumerate_boxes(self) -> list[dict[str, Any]]:
        """Enumerate all available Box endpoints."""
        endpoints = self._health_checker.all_endpoints()
        return [e.to_dict() for e in endpoints]