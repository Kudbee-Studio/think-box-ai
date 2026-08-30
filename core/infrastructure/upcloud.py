"""UpCloud infrastructure provider.

Manages UpCloud servers for KVM-capable Firecracker execution environments.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

BASE_URL = "https://api.upcloud.com/1.3"


@dataclass
class ServerSpec:
    """Specification for creating a new UpCloud server."""

    hostname: str
    plan: str = "PREMIUM-4xCPU-8GB"
    zone: str = "fi-hel2"
    os_template: str = "01000000-0000-4000-8000-000000000022"  # Ubuntu 24.04
    ssh_keys: list[str] = field(default_factory=list)
    user_data: str | None = None
    title: str = ""
    tags: list[str] = field(default_factory=list)

    def to_api_body(self) -> dict[str, Any]:
        body = {
            "server": {
                "hostname": self.hostname,
                "plan": self.plan,
                "zone": self.zone,
                "title": self.title or self.hostname,
                "storage_devices": {
                    "storage_device": [
                        {
                            "action": "clone",
                            "storage": self.os_template,
                            "title": "root-disk",
                            "size": 50,
                            "tier": "maxiops",
                        }
                    ]
                },
            }
        }

        if self.ssh_keys:
            body["server"]["login_user"] = {
                "username": "root",
                "ssh_keys": {"ssh_key": self.ssh_keys},
            }

        if self.user_data:
            body["server"]["user_data"] = self.user_data

        if self.tags:
            body["server"]["tags"] = {"tag": self.tags}

        return body


@dataclass
class ServerInfo:
    """Information about an UpCloud server."""

    uuid: str
    hostname: str
    title: str
    state: str
    plan: str
    zone: str
    cores: int
    memory_mb: int
    public_ips: list[str] = field(default_factory=list)
    private_ips: list[str] = field(default_factory=list)

    @property
    def is_running(self) -> bool:
        return self.state == "started"

    @property
    def primary_ip(self) -> str | None:
        return self.public_ips[0] if self.public_ips else None


class UpCloudClient:
    """Async-compatible UpCloud API client.

    Uses Bearer token authentication from THINKBOX_UPCLOUD_API_TOKEN
    environment variable.
    """

    def __init__(self, api_token: str | None = None, base_url: str = BASE_URL) -> None:
        self._token = api_token or os.environ.get("THINKBOX_UPCLOUD_API_TOKEN", "")
        self._base_url = base_url.rstrip("/")

    def _auth_header(self) -> str:
        return f"Bearer {self._token}"

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        import urllib.request
        import urllib.error

        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": self._auth_header(),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        body_bytes = None
        if body is not None:
            body_bytes = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                response_body = response.read()
                if not response_body:
                    return {}
                return json.loads(response_body.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise Exception(
                f"UpCloud API error {exc.code} on {method} {path}: {error_body}"
            ) from exc

    def list_servers(self) -> list[ServerInfo]:
        """List all servers in the account.

        Makes individual GET requests for each server to retrieve full
        IP address details, as the list endpoint doesn't include them.
        """
        response = self._request("GET", "/server")
        servers = []
        for server_data in response.get("servers", {}).get("server", []):
            uuid = server_data.get("uuid", "")
            if uuid:
                try:
                    servers.append(self.get_server(uuid))
                except Exception as exc:
                    logger.warning("Failed to get details for server %s: %s", uuid, exc)
                    servers.append(self._parse_server_info(server_data))
        return servers

    def get_server(self, uuid: str) -> ServerInfo:
        """Get details for a specific server."""
        response = self._request("GET", f"/server/{uuid}")
        return self._parse_server_info(response["server"])

    def create_server(self, spec: ServerSpec, wait: bool = True, timeout: float = 300.0) -> ServerInfo:
        """Create a new server and optionally wait for it to start."""
        body = spec.to_api_body()
        response = self._request("POST", "/server", body=body)
        server = self._parse_server_info(response["server"])

        if wait:
            server = self._wait_for_state(server.uuid, "started", timeout=timeout)

        return server

    def start_server(self, uuid: str, wait: bool = True, timeout: float = 120.0) -> ServerInfo:
        """Start a stopped server."""
        self._request("POST", f"/server/{uuid}/start")
        if wait:
            return self._wait_for_state(uuid, "started", timeout=timeout)
        return self.get_server(uuid)

    def stop_server(self, uuid: str, wait: bool = True, timeout: float = 120.0) -> ServerInfo:
        """Stop a running server."""
        body = {"stop_server": {"stop_type": "hard"}}
        self._request("POST", f"/server/{uuid}/stop", body=body)
        if wait:
            return self._wait_for_state(uuid, "stopped", timeout=timeout)
        return self.get_server(uuid)

    def delete_server(self, uuid: str, wait: bool = True, timeout: float = 120.0) -> None:
        """Delete a server and all its storage devices."""
        self._request("DELETE", f"/server/{uuid}")
        if wait:
            self._wait_for_deletion(uuid, timeout=timeout)

    def _parse_server_info(self, data: dict[str, Any]) -> ServerInfo:
        public_ips = []
        private_ips = []
        for ip_data in data.get("ip_addresses", {}).get("ip_address", []):
            access = ip_data.get("access", "")
            address = ip_data.get("address", "")
            if not address:
                continue
            if access == "public":
                public_ips.append(address)
            else:
                private_ips.append(address)

        return ServerInfo(
            uuid=data.get("uuid", ""),
            hostname=data.get("hostname", ""),
            title=data.get("title", ""),
            state=data.get("state", ""),
            plan=data.get("plan", ""),
            zone=data.get("zone", ""),
            cores=int(data.get("core_number", 0)),
            memory_mb=int(data.get("memory_amount", 0)),
            public_ips=public_ips,
            private_ips=private_ips,
        )

    def _wait_for_state(self, uuid: str, target_state: str, timeout: float = 120.0) -> ServerInfo:
        """Poll server until it reaches the target state."""
        deadline = time.monotonic() + timeout
        last_state = None

        while time.monotonic() < deadline:
            server = self.get_server(uuid)
            if server.state == target_state:
                return server
            if server.state != last_state:
                logger.info("Server %s state: %s (waiting for %s)", uuid, server.state, target_state)
                last_state = server.state
            time.sleep(5.0)

        raise TimeoutError(
            f"Server {uuid} did not reach state '{target_state}' within {timeout}s"
        )

    def _wait_for_deletion(self, uuid: str, timeout: float = 120.0) -> None:
        """Poll until the server no longer exists."""
        import urllib.request
        import urllib.error

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                self.get_server(uuid)
            except Exception:
                return
            time.sleep(5.0)

        raise TimeoutError(
            f"Server {uuid} still exists after {timeout}s"
        )


def create_kvm_server(
    hostname: str,
    plan: str = "PREMIUM-8xCPU-128GB",
    zone: str = "us-chi1",
    ssh_keys: list[str] | None = None,
) -> ServerInfo:
    """Convenience function to create a KVM-capable server."""
    client = UpCloudClient()
    spec = ServerSpec(
        hostname=hostname,
        plan=plan,
        zone=zone,
        ssh_keys=ssh_keys or [],
        title=f"KUDBEE Firecracker {hostname}",
        tags=["kudbee", "firecracker", "kvm"],
    )
    return client.create_server(spec)
