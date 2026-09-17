"""UpCloud infrastructure investigation and execution path.

UpCloud is an INFRASTRUCTURE / CONTROL-PLANE provider (read-only REST).
It is NOT the Think Box execution substrate. The live execution substrate
is the Upstash Box selected by thinkbox/substrate.py::detect_substrate().
SSH-to-UpCloud execution is unsupported and not required.

The UPCLOUD_API_MAIN env var is NOT available to runtime; UpCloud is marked
UNVERIFIED. This module investigates why and provides the trace.
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.dashboard_state import (
    InfrastructureEntry, ProviderEntry, DashboardCategory, DashboardEvent,
    get_dashboard_state,
)


@dataclass
class UpCloudConfig:
    """Control-plane config only. NOT an execution substrate.

    server_hostname/server_ip have no verified defaults: pass live values
    explicitly (e.g. from the UpCloud API server inventory). Historical
    defaults (kudbee-host-v1 / 212.147.250.183) are superseded — see
    data/thinkboxmd/artifacts/upcloud_runtime_state_20260917.json.
    SSH-to-UpCloud execution is unsupported; see thinkbox/substrate.py.
    """
    api_token: str = ""
    ssh_key_path: str = ""
    ssh_user: str = "root"
    server_hostname: str = ""
    server_ip: str = ""
    api_url: str = "https://api.upcloud.com/1.3"

    def __post_init__(self) -> None:
        if not self.api_token:
            self.api_token = os.environ.get("THINKBOX_UPCLOUD_API_TOKEN", "")
        if not self.ssh_key_path:
            self.ssh_key_path = os.environ.get("UPCLOUD_SSH_KEY_PATH", "")
        if not self.ssh_user:
            self.ssh_user = os.environ.get("UPCLOUD_SSH_USER", "root")
        if not self.server_hostname:
            self.server_hostname = os.environ.get("UPCLOUD_SERVER_HOSTNAME", "")
        if not self.server_ip:
            self.server_ip = os.environ.get("UPCLOUD_SERVER_IP", "")


@dataclass
class UpCloudCapability:
    name: str
    available: bool
    gpu_available: bool = False
    vcpu: int = 0
    memory_mb: int = 0
    storage_gb: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "gpu_available": self.gpu_available,
            "vcpu": self.vcpu,
            "memory_mb": self.memory_mb,
            "storage_gb": self.storage_gb,
            "details": self.details,
        }


@dataclass
class UpCloudTraceResult:
    step: str
    status: str
    details: dict[str, Any]
    timestamp: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def model_dump(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "status": self.status,
            "details": self.details,
            "timestamp": self.timestamp,
            "error": self.error,
        }


class UpCloudExecutionPath:
    """Traces the full UpCloud execution path."""

    def __init__(self, config: UpCloudConfig | None = None) -> None:
        self.config = config or UpCloudConfig()
        self.trace: list[UpCloudTraceResult] = []
        self._state = get_dashboard_state()

    def _add_trace(self, step: str, status: str, details: dict[str, Any] = {}, error: str = "") -> None:
        result = UpCloudTraceResult(step=step, status=status, details=details, error=error)
        self.trace.append(result)

    async def step1_discover_capabilities(self) -> UpCloudTraceResult:
        """Step 1: Discover UpCloud capabilities via API."""
        self._add_trace("discover_capabilities", "started")
        try:
            token = self.config.api_token
            if not token:
                self._add_trace("discover_capabilities", "failed", {}, "No API token")
                return self.trace[-1]
            req = urllib.request.Request(
                f"{self.config.api_url}/server",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                self._add_trace("discover_capabilities", "success", {"servers": len(data.get("servers", {}).get("server", []))})
        except urllib.error.HTTPError as e:
            self._add_trace("discover_capabilities", "failed", {}, f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            self._add_trace("discover_capabilities", "failed", {}, str(e))
        return self.trace[-1]

    async def step2_authenticate(self) -> UpCloudTraceResult:
        """Step 2: Authenticate with UpCloud."""
        self._add_trace("authenticate", "started")
        try:
            token = self.config.api_token
            if not token:
                self._add_trace("authenticate", "failed", {}, "No API token")
                return self.trace[-1]
            req = urllib.request.Request(
                f"{self.config.api_url}/account",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                self._add_trace("authenticate", "success", {"account": data.get("account", {}).get("username", "unknown")})
        except urllib.error.HTTPError as e:
            self._add_trace("authenticate", "failed", {}, f"HTTP {e.code}: {e.reason} — token may be invalid")
        except Exception as e:
            self._add_trace("authenticate", "failed", {}, str(e))
        return self.trace[-1]

    async def step3_verify_gpu(self) -> UpCloudTraceResult:
        """Step 3: Verify GPU availability on the explicitly configured server (control-plane inventory only)."""
        self._add_trace("verify_gpu", "started")
        try:
            token = self.config.api_token
            if not token:
                self._add_trace("verify_gpu", "failed", {}, "No API token")
                return self.trace[-1]
            req = urllib.request.Request(
                f"{self.config.api_url}/server/{self.config.server_hostname}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                server = data.get("server", {})
                self._add_trace("verify_gpu", "success", {
                    "hostname": server.get("hostname", ""),
                    "plan": server.get("plan", ""),
                    "memory": server.get("memory", 0),
                    "vcpu": server.get("vcpu", 0),
                    "gpu": server.get("gpu", False),
                })
        except urllib.error.HTTPError as e:
            self._add_trace("verify_gpu", "failed", {}, f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            self._add_trace("verify_gpu", "failed", {}, str(e))
        return self.trace[-1]

    async def step4_check_ssh_access(self) -> UpCloudTraceResult:
        """Step 4: Check SSH access to the server.

        UNSUPPORTED direction: SSH-to-UpCloud is not part of the Think Box
        execution roadmap (Upstash Box is the substrate). Kept for
        diagnostic reporting only.
        """
        self._add_trace("check_ssh", "started")
        ssh_key = self.config.ssh_key_path
        if not ssh_key or not os.path.exists(ssh_key.replace("~", os.path.expanduser("~"))):
            self._add_trace("check_ssh", "failed", {}, "SSH key not found")
            return self.trace[-1]
        try:
            import subprocess
            result = subprocess.run(
                ["ssh", "-i", ssh_key, "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                 f"{self.config.ssh_user}@{self.config.server_ip}", "echo", "ok"],
                capture_output=True, timeout=10,
            )
            if result.returncode == 0:
                self._add_trace("check_ssh", "success", {"response": result.stdout.decode().strip()})
            else:
                self._add_trace("check_ssh", "failed", {}, f"SSH failed: {result.stderr.decode().strip()}")
        except Exception as e:
            self._add_trace("check_ssh", "failed", {}, str(e))
        return self.trace[-1]

    async def step5_check_cloudflare(self) -> UpCloudTraceResult:
        """Step 5: Check if Cloudflare blocks direct access."""
        self._add_trace("check_cloudflare", "started")
        try:
            req = urllib.request.Request(
                f"http://{self.config.server_ip}/",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                self._add_trace("check_cloudflare", "success", {"status": resp.status, "headers": dict(resp.headers)})
        except urllib.error.HTTPError as e:
            if e.code == 1003:
                self._add_trace("check_cloudflare", "blocked", {}, "Cloudflare 1003 — direct IP access blocked")
            else:
                self._add_trace("check_cloudflare", "failed", {}, f"HTTP {e.code}")
        except Exception as e:
            self._add_trace("check_cloudflare", "failed", {}, str(e))
        return self.trace[-1]

    async def run_full_trace(self) -> list[UpCloudTraceResult]:
        """Run the complete UpCloud execution path trace."""
        self.trace = []
        await self.step1_discover_capabilities()
        await self.step2_authenticate()
        await self.step3_verify_gpu()
        await self.step4_check_ssh_access()
        await self.step5_check_cloudflare()

        for t in self.trace:
            infra = InfrastructureEntry(
                component=f"upcloud_{t.step}",
                type="upcloud",
                status=t.status,
                substrate="upcloud-gpu",
                verified=t.status == "success",
                details=t.model_dump(),
            )
            self._state.upsert_infrastructure(infra.component, infra)

        return self.trace

    def get_trace_summary(self) -> dict[str, Any]:
        """Get a summary of the trace."""
        steps = {t.step: t.status for t in self.trace}
        return {
            "trace": [t.model_dump() for t in self.trace],
            "summary": steps,
            "all_success": all(t.status == "success" for t in self.trace),
            "any_blocked": any(t.status == "blocked" for t in self.trace),
        }


async def investigate_upcloud() -> dict[str, Any]:
    """Investigate UpCloud execution path and update dashboard state."""
    path = UpCloudExecutionPath()
    trace = await path.run_full_trace()
    summary = path.get_trace_summary()

    provider = ProviderEntry(
        name="UpCloud",
        model="control-plane",
        status="unverified" if summary["any_blocked"] else "verified",
        endpoint="https://api.upcloud.com/1.3",
        verified=not summary["any_blocked"],
        details=summary,
    )
    path._state.upsert_provider(provider)

    await path._state.emit(
        DashboardCategory.INFRASTRUCTURE,
        DashboardEvent.INFRASTRUCTURE_CHANGED,
        {"provider": provider.model_dump(), "trace": summary["trace"]},
        "upcloud_investigation",
        evidence_label="inferred",
    )

    return summary