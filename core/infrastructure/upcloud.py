"""UpCloud connection and management for Think Box AI.

Provides:
- Server provisioning and management
- GPU instance deployment
- LongCat model hosting
- Status monitoring
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any

logger = __import__("logging").getLogger(__name__)


@dataclass
class UpCloudConfig:
    """UpCloud connection configuration."""
    api_token: str = ""
    username: str = ""
    zone: str = "fi-hel2"
    base_url: str = "https://api.upcloud.com/1.3"

    def __post_init__(self) -> None:
        if not self.api_token:
            self.api_token = os.environ.get("THINKBOX_UPCLOUD_API_TOKEN", "")


@dataclass
class ServerSpec:
    """Server specification for provisioning."""
    hostname: str
    plan: str
    zone: str = "fi-hel2"
    os_template: str = "01000000-0000-4000-8000-000030200200"  # Ubuntu 22.04
    ssh_keys: list[str] = field(default_factory=list)
    user_data: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class ServerStatus:
    """Current status of a server."""
    uuid: str
    hostname: str
    state: str
    plan: str
    cores: int
    memory_mb: int
    ip_addresses: list[str]
    created_at: str


class UpCloudConnection:
    """Manages UpCloud infrastructure for KUDBEE deployments."""

    GPU_PLANS = {
        "gpu-l4-spot": "GPU-SPOT-8xCPU-64GB-1xL4",
        "gpu-l40s": "GPU-16xCPU-128GB-1xL40S",
        "gpu-h100": "GPU-24xCPU-240GB-1xH100",
        "gpu-b200": "GPU-96xCPU-1920GB-1xB200",
    }

    def __init__(self, config: UpCloudConfig | None = None) -> None:
        self._config = config or UpCloudConfig()

    def _request(
        self,
        path: str,
        method: str = "GET",
        body: dict | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Make an API request with error handling."""
        url = f"{self._config.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._config.api_token}",
            "Content-Type": "application/json",
        }

        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ""
            logger.error(f"UpCloud API error {e.code}: {error_body[:500]}")
            return {"error": error_body, "status": e.code}
        except urllib.error.URLError as e:
            logger.error(f"UpCloud connection error: {e}")
            return {"error": str(e), "status": 0}

    def health_check(self) -> dict[str, Any]:
        """Check if UpCloud API is accessible."""
        start = time.monotonic()
        result = self._request("/account")
        duration = time.monotonic() - start

        if "error" in result:
            return {"status": "error", "duration_ms": round(duration * 1000, 2), "error": result.get("error", "")}

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
                state=s.get("state", ""),
                plan=s.get("plan", ""),
                cores=int(s.get("core_number", 0)),
                memory_mb=int(s.get("memory_amount", 0)),
                ip_addresses=ips,
                created_at=s.get("created_at", ""),
            ))
        return servers

    def get_server(self, uuid: str) -> ServerStatus | None:
        """Get a specific server by UUID."""
        result = self._request(f"/server/{uuid}")
        if "error" in result:
            return None
        s = result.get("server", {})
        ips = [ip.get("address", "") for ip in s.get("ip_addresses", {}).get("ip_address", [])]
        return ServerStatus(
            uuid=s.get("uuid", ""),
            hostname=s.get("title", ""),
            state=s.get("state", ""),
            plan=s.get("plan", ""),
            cores=int(s.get("core_number", 0)),
            memory_mb=int(s.get("memory_amount", 0)),
            ip_addresses=ips,
            created_at=s.get("created_at", ""),
        )

    def create_server(self, spec: ServerSpec) -> dict[str, Any]:
        """Provision a new server."""
        body = {
            "server": {
                "title": spec.hostname,
                "hostname": spec.hostname,
                "plan": spec.plan,
                "zone": spec.zone,
                "storage_devices": {
                    "storage_device": [{
                        "action": "create",
                        "size": 100,
                        "tier": "maxiops",
                        "title": f"{spec.hostname}-disk",
                    }]
                },
                "login_user": {"username": "root"},
            }
        }
        if spec.user_data:
            body["server"]["user_data"] = spec.user_data
        if spec.tags:
            body["server"]["tags"] = {"tag": spec.tags}

        return self._request("/server", method="POST", body=body)

    def stop_server(self, uuid: str) -> dict[str, Any]:
        """Stop a server."""
        return self._request(f"/server/{uuid}/stop", method="POST", body={"stop_type": "soft"})

    def start_server(self, uuid: str) -> dict[str, Any]:
        """Start a stopped server."""
        return self._request(f"/server/{uuid}/start", method="POST")

    def delete_server(self, uuid: str) -> dict[str, Any]:
        """Delete a server and its storage."""
        return self._request(f"/server/{uuid}", method="DELETE")

    def get_gpu_plans(self) -> list[dict[str, Any]]:
        """Get available GPU server plans."""
        result = self._request("/plan")
        if "error" in result:
            return []
        plans = []
        for p in result.get("plans", {}).get("plan", []):
            name = p.get("name", "")
            if "GPU" in name.upper():
                plans.append({
                    "name": name,
                    "cores": p.get("core_number", 0),
                    "memory_gb": round(p.get("memory_amount", 0) / 1024, 1),
                })
        return plans

    def deploy_longcat(self, server_uuid: str) -> dict[str, Any]:
        """Deploy LongCat model on a server."""
        # This would SSH into the server and set up LongCat
        # For now, return the deployment plan
        return {
            "server": server_uuid,
            "model": "LongCat-2.0",
            "status": "planned",
            "steps": [
                "SSH into server",
                "Install Python 3.10+",
                "Install Think Box AI",
                "Configure LongCat API key",
                "Start API server",
            ],
        }


def get_connection() -> UpCloudConnection:
    """Factory for UpCloudConnection."""
    return UpCloudConnection()


def get_dashboard_data() -> dict[str, Any]:
    """Get all data needed for the dashboard."""
    conn = get_connection()
    health = conn.health_check()
    servers = conn.list_servers()
    gpu_plans = conn.get_gpu_plans()

    return {
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "api_health": health,
        "servers": [
            {
                "uuid": s.uuid,
                "hostname": s.hostname,
                "state": s.state,
                "plan": s.plan,
                "cores": s.cores,
                "memory_gb": round(s.memory_mb / 1024, 1),
                "ip_addresses": s.ip_addresses,
            }
            for s in servers
        ],
        "gpu_plans_available": len(gpu_plans),
        "gpu_plans": gpu_plans[:6],
    }
