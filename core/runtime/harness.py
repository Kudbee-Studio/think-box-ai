"""Docker-backed execution harness for THINK BOX AI.

Execution split (Phase 1 sandbox):
  Host:
    - Orchestrator: Agent, Planner, Actor, Observer
    - Model provider calls (LLM inference stays on host/GPU)
    - Memory reads, tool registry, audit logging
  Container:
    - ALL tool side effects: shell_exec, file_write, python exec, downloads
    - Isolated filesystem (only /data mount visible to agent)
    - No network by default (configurable via network_mode)
  The LLM process does NOT live in the container in Phase 1.
  This lets us run GPU-resident models on host while sandboxing tool effects.
  Firecracker/CloudVM is the Phase 2 isolation target (stub only here).
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("thinkbox.harness")


class SandboxBackend:
    """Stub for future Firecracker/CloudVM backends.

    Phase 1 uses Docker only. Phase 2 will add FirecrackerMicroVM and
    CloudVM implementations selected via HarnessConfig.backend.
    """

    DOCKER = "docker"
    FIRECRACKER = "firecracker"
    CLOUD_VM = "cloud_vm"


@dataclass
class HarnessLimits:
    memory: str = "2g"
    cpus: str = "1.0"
    pids_limit: int = 0
    read_only_rootfs: bool = False


@dataclass
class HarnessConfig:
    enabled: bool = True
    network_mode: str = "none"
    limits: HarnessLimits = field(default_factory=HarnessLimits)
    image: str = "ku3bee-harness:dev"
    workdir_root: str = ""
    backend: str = SandboxBackend.DOCKER


@dataclass
class HarnessContainer:
    container_id: str
    container_name: str
    workdir: str
    limits: HarnessLimits
    network_mode: str


def docker_available() -> bool:
    """Check if Docker is reachable on this host."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


class HarnessRunner:
    """Manages Docker containers for agent task execution.

    One container per agent token. Container name format:
        ku3bee-<token>-<shortid>
    where shortid is a 12-char uuid fragment.
    """

    def __init__(self, config: HarnessConfig | None = None) -> None:
        self.config = config or HarnessConfig()
        self._containers: dict[str, HarnessContainer] = {}

    def _docker(self, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
        cmd = ["docker", *args]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def start_container(
        self,
        agent_id: str,
        mounts: dict[str, str] | None = None,
        limits: HarnessLimits | None = None,
        network_mode: str | None = None,
    ) -> HarnessContainer:
        limits = limits or self.config.limits
        network_mode = network_mode or self.config.network_mode
        mounts = mounts or {}

        shortid = str(uuid.uuid4())[:12]
        container_name = f"ku3bee-{agent_id}-{shortid}"

        workdir = tempfile.mkdtemp(prefix=f"ku3bee-work-{agent_id}-")

        cmd = ["docker", "run", "-d", "--name", container_name]

        cmd.extend(["--memory", limits.memory])
        cmd.extend(["--cpus", limits.cpus])

        if limits.pids_limit > 0:
            cmd.extend(["--pids-limit", str(limits.pids_limit)])

        if limits.read_only_rootfs:
            cmd.append("--read-only")
            cmd.extend(["--tmpfs", "/tmp"])

        cmd.extend(["--network", network_mode])

        cmd.extend(["--cap-drop", "ALL"])

        cmd.append("--no-new-privileges")

        cmd.extend(["-v", f"{workdir}:/data"])

        for host_path, container_path in mounts.items():
            cmd.extend(["-v", f"{host_path}:{container_path}"])

        cmd.extend(["-e", f"HARNESS_AGENT_ID={agent_id}"])
        cmd.extend(["-e", f"HARNESS_CONTAINER_ID={shortid}"])

        cmd.append(self.config.image)
        cmd.extend(["sleep", "infinity"])

        start_t = time.monotonic()
        result = self._docker(*cmd, timeout=60)
        elapsed_ms = int((time.monotonic() - start_t) * 1000)

        if result.returncode != 0:
            shutil.rmtree(workdir, ignore_errors=True)
            logger.error(
                "container_start_failed name=%s elapsed_ms=%d stderr=%s",
                container_name, elapsed_ms, result.stderr.strip(),
            )
            raise RuntimeError(
                f"Failed to start container: {result.stderr.strip()}"
            )

        container = HarnessContainer(
            container_id=shortid,
            container_name=container_name,
            workdir=workdir,
            limits=limits,
            network_mode=network_mode,
        )
        self._containers[shortid] = container
        logger.info(
            "container_start name=%s id=%s elapsed_ms=%d",
            container_name, shortid, elapsed_ms,
        )
        return container

    async def exec_in_container(
        self,
        container_id: str,
        argv: list[str],
        timeout: int = 60,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        container = self._containers.get(container_id)
        if container is None:
            return {"success": False, "error": f"Unknown container: {container_id}"}

        cmd = ["docker", "exec", "-i"]

        if env:
            for k, v in env.items():
                cmd.extend(["-e", f"{k}={v}"])

        cmd.append(container.container_name)
        cmd.extend(argv)

        start_t = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            elapsed_ms = int((time.monotonic() - start_t) * 1000)
            logger.info(
                "container_exec name=%s id=%s rc=%d elapsed_ms=%d",
                container.container_name, container_id,
                proc.returncode, elapsed_ms,
            )
            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "return_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            elapsed_ms = int((time.monotonic() - start_t) * 1000)
            logger.warning(
                "container_exec_timeout name=%s id=%s elapsed_ms=%d",
                container.container_name, container_id, elapsed_ms,
            )
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_t) * 1000)
            logger.error(
                "container_exec_error name=%s id=%s elapsed_ms=%d error=%s",
                container.container_name, container_id, elapsed_ms, str(e),
            )
            return {"success": False, "error": str(e)}

    def stop_container(self, container_id: str, timeout: int = 30) -> bool:
        container = self._containers.pop(container_id, None)
        if container is None:
            return False

        start_t = time.monotonic()
        try:
            self._docker("rm", "-f", container.container_name, timeout=timeout)
        except Exception:
            pass

        shutil.rmtree(container.workdir, ignore_errors=True)
        elapsed_ms = int((time.monotonic() - start_t) * 1000)
        logger.info(
            "container_stop name=%s id=%s elapsed_ms=%d",
            container.container_name, container_id, elapsed_ms,
        )
        return True

    def stop_all(self) -> None:
        for container_id in list(self._containers.keys()):
            self.stop_container(container_id)

    def list_containers(self) -> list[HarnessContainer]:
        return list(self._containers.values())
