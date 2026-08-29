"""UpCloud infrastructure management for Think Box AI.

Provides a clean API for managing UpCloud servers, storage, and monitoring.
All operations are fail-safe with proper error handling and logging.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from core.foundation.logging import get_logger

logger = get_logger(__name__)


def _error_result(message: str, **kwargs: Any) -> dict[str, Any]:
    """Create a standardized error result."""
    return {"error": message, "details": kwargs}


class ServerState(str, Enum):
    STARTED = "started"
    STOPPED = "stopped"
    MAINTENANCE = "maintenance"
    ERROR = "error"


@dataclass
class ServerSpec:
    """Server specification for provisioning."""
    hostname: str
    plan: str
    zone: str = "fi-hel2"
    os_template: str = "01000000-0000-4000-8000-000030200200"
    ssh_keys: list[str] = field(default_factory=list)
    user_data: str = ""


@dataclass
class ServerStatus:
    """Current status of a server."""
    uuid: str
    hostname: str
    state: ServerState
    plan: str
    cores: int
    memory_mb: int
    ip_addresses: list[str]
    created_at: str
    uptime_seconds: float
    gpu_info: str = ""


@dataclass
class AccountUsage:
    """Account resource usage."""
    credit_remaining: float
    servers_active: int = 0
    servers_total: int = 0
    storage_gb_used: float = 0
    storage_gb_total: float = 0
    bandwidth_gb_used: float = 0


class UpCloudClient:
    """Fail-safe UpCloud API client."""

    BASE_URL = "https://api.upcloud.com/1.3"

    def __init__(self, token: str | None = None) -> None:
        self._token = token or os.environ.get("THINKBOX_UPCLOUD_API_TOKEN", "")
        self._zone = os.environ.get("UPCLOUD_ZONE", "fi-hel2")

    def _request(
        self,
        path: str,
        method: str = "GET",
        body: dict | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Make an API request with error handling."""
        url = f"{self.BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            logger.error("UpCloud API error", extra={"status": e.code, "path": path, "error": error_body})
            return _error_result(f"API error {e.code}", path=path)
        except urllib.error.URLError as e:
            logger.error("UpCloud connection error", extra={"error": str(e)})
            return _error_result("Connection failed")
        except Exception as e:
            logger.error("UpCloud unexpected error", extra={"error": str(e)})
            return _error_result(str(e))

    def health_check(self) -> dict[str, Any]:
        """Check if UpCloud API is accessible."""
        start = time.monotonic()
        result = self._request("/account")
        duration = time.monotonic() - start
        if "error" in result:
            return {"status": "error", "duration_ms": round(duration * 1000, 2), "error": result.get("error")}
        return {"status": "ok", "duration_ms": round(duration * 1000, 2)}

    def list_servers(self) -> list[ServerStatus]:
        """List all servers."""
        result = self._request("/server")
        if "error" in result:
            return []
        servers = []
        for s in result.get("servers", {}).get("server", []):
            ips = [ip.get("address", "") for ip in s.get("ip_addresses", {}).get("ip_address", [])]
            servers.append(ServerStatus(
                uuid=s.get("uuid", ""),
                hostname=s.get("title", ""),
                state=ServerState(s.get("state", "stopped")),
                plan=s.get("plan", "unknown"),
                cores=int(s.get("core_number", 0)),
                memory_mb=int(s.get("memory_amount", 0)),
                ip_addresses=ips,
                created_at=s.get("created_at", ""),
                uptime_seconds=float(s.get("uptime", 0)),
            ))
        return servers

    def get_account_usage(self) -> AccountUsage | None:
        """Get account credit and usage."""
        result = self._request("/account")
        if "error" in result:
            return None
        return AccountUsage(credit_remaining=result.get("credits", 0))

    def get_gpu_plans(self) -> list[dict[str, Any]]:
        """Get available GPU server plans."""
        result = self._request("/plan")
        if "error" in result:
            return []
        return [
            {
                "name": p.get("name", ""),
                "cores": p.get("core_number", 0),
                "memory_mb": p.get("memory_amount", 0),
                "memory_gb": round(p.get("memory_amount", 0) / 1024, 1),
            }
            for p in result.get("plans", {}).get("plan", [])
            if "GPU" in p.get("name", "").upper()
        ]


def get_client() -> UpCloudClient:
    """Factory for UpCloudClient."""
    return UpCloudClient()


def get_dashboard_data() -> dict[str, Any]:
    """Get all data needed for the dashboard."""
    client = get_client()
    health = client.health_check()
    servers = client.list_servers()
    usage = client.get_account_usage()
    gpu_plans = client.get_gpu_plans()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_health": health,
        "servers": [
            {
                "uuid": s.uuid,
                "hostname": s.hostname,
                "state": s.state.value,
                "plan": s.plan,
                "cores": s.cores,
                "memory_gb": round(s.memory_mb / 1024, 1),
                "ip_addresses": s.ip_addresses,
                "uptime_seconds": s.uptime_seconds,
            }
            for s in servers
        ],
        "usage": {"credit_remaining": usage.credit_remaining if usage else 0},
        "gpu_plans_available": len(gpu_plans),
        "gpu_plans": gpu_plans[:5],
    }
