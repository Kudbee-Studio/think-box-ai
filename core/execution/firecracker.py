"""Firecracker microVM execution provider for THINK BOX AI.

This provider runs commands inside a Firecracker microVM to give Think Box
work a strong isolation boundary (separate kernel, separate address space).

IMPORTANT — honesty constraints
--------------------------------
Firecracker REQUIRES a real ``/dev/kvm`` character device exposing the
``KVM_GET_API_VERSION`` ioctl. On hosts where that is unavailable (e.g. the
current UpCloud Managed Kubernetes worker, which is itself a KVM guest with
nested virtualization disabled), this provider MUST NOT pretend to work.

- ``health_check()`` returns ``False`` unless a real ``/dev/kvm`` char device
  exists, the Firecracker binary is present, and a guest-command transport
  (virtio-vsock) is usable.
- ``execute()`` raises ``ExecutionUnavailableError`` when not healthy. We
  never return a fake ``KUDBEE_FIRECRACKER_OK``.

When KVM IS available, the provider:
  1. starts the Firecracker VMM process (optionally under the jailer),
  2. configures machine/boot/drive via the REST API over a Unix socket,
  3. boots the microVM,
  4. sends the command to a minimal guest agent over virtio-vsock,
  5. captures structured stdout/stderr/exit-code,
  6. shuts the microVM down and cleans up the process + socket.

The host-side vsock protocol is documented in
``docs/decisions/003-execution-provider.md`` and a reference guest agent is
described there. The runtime never sees Firecracker internals — only the
``ExecutionProvider`` contract.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import time
import uuid
from typing import Any

from core.execution.base import (
    ExecResult,
    ExecutionProvider,
    ExecutionProviderRegistry,
    ExecutionUnavailableError,
)
from core.foundation.logging import get_logger

logger = get_logger(__name__)

# virtio-vsock guest CID used by the Firecracker guest agent.
DEFAULT_GUEST_CID = 3
DEFAULT_VSOCK_PORT = 1024

# AF_VSOCK is not always exposed by Python's socket module; use the
# well-known Linux constant (40) when unavailable.
_AF_VSOCK = getattr(socket, "AF_VSOCK", 40)


class _VsockClient:
    """Minimal virtio-vsock client for host<->guest command transport.

    Firecracker's vsock proxy uses a Unix domain socket on the host. The
    protocol is:
      1. Connect to the Unix socket (uds_path from the /vsock API).
      2. Send "CONNECT <port>\\n".
      3. Read "OK <guest_cid>\\n" (or an error).
      4. Send command as a JSON line.
      5. Read response JSON lines (stream data + exit code).

    All socket operations are blocking; use asyncio.to_thread() or
    loop.run_in_executor() to avoid blocking the event loop.
    """

    def __init__(
        self,
        guest_cid: int,
        port: int,
        vsock_uds: str,
        connect_timeout: float = 10.0,
    ) -> None:
        self._guest_cid = guest_cid
        self._port = port
        self._vsock_uds = vsock_uds
        self._connect_timeout = connect_timeout
        self._sock: "socket.socket | None" = None

    @staticmethod
    def available() -> bool:
        """Return True if the host kernel supports AF_VSOCK sockets."""
        try:
            with socket.socket(_AF_VSOCK, socket.SOCK_STREAM) as s:
                return True
        except OSError:
            return False

    def connect(self) -> None:
        """Connect to the Firecracker vsock Unix socket and handshake."""
        last_err: Exception | None = None
        for attempt in range(50):
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(self._connect_timeout)
                sock.connect(self._vsock_uds)
                # Firecracker vsock handshake: request connection to guest port
                sock.sendall(f"CONNECT {self._port}\n".encode("utf-8"))
                buf = b""
                while b"\n" not in buf:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                if not buf.startswith(b"OK"):
                    raise ExecutionUnavailableError(
                        message=f"vsock handshake failed: {buf.decode(errors='replace')!r}"
                    )
                self._sock = sock
                return
            except (OSError, ExecutionUnavailableError) as e:
                last_err = e
                try:
                    sock.close()
                except OSError:
                    pass
                time.sleep(0.2)
        raise ExecutionUnavailableError(
            message=f"vsock connect failed after retries: {last_err}"
        )

    def send_command(self, command: str) -> None:
        if self._sock is None:
            raise ExecutionUnavailableError(message="vsock not connected")
        payload = json.dumps({"cmd": command}).encode("utf-8")
        self._sock.sendall(payload + b"\n")

    def execute_command(self, command: str, timeout: float) -> ExecResult:
        """Execute a command over vsock and return the result. Blocking."""
        self.connect()
        try:
            self.send_command(command)
            stdout_chunks: list[str] = []
            stderr_chunks: list[str] = []
            return_code = -1
            deadline = time.monotonic() + timeout
            while True:
                remaining = max(1.0, deadline - time.monotonic())
                try:
                    msg = self.read_response(remaining)
                except (socket.timeout, TimeoutError):
                    raise ExecutionUnavailableError(message="guest agent response timed out")
                if "exit" in msg:
                    return_code = int(msg["exit"])
                    break
                stream = msg.get("stream", "stdout")
                data = msg.get("data", "")
                (stdout_chunks if stream == "stdout" else stderr_chunks).append(data)
                if time.monotonic() >= deadline:
                    raise ExecutionUnavailableError(message="command timed out in guest")
            return ExecResult(
                stdout="".join(stdout_chunks),
                stderr="".join(stderr_chunks),
                return_code=return_code,
                duration=0.0,
                provider="firecracker",
            )
        finally:
            self.close()

    def read_response(self, timeout: float) -> dict[str, Any]:
        """Read a single JSON line from the guest agent."""
        if self._sock is None:
            raise ExecutionUnavailableError(message="vsock not connected")
        self._sock.settimeout(timeout)
        buf = b""
        while b"\n" not in buf:
            chunk = self._sock.recv(65536)
            if not chunk:
                break
            buf += chunk
        line = buf.split(b"\n", 1)[0].decode("utf-8", errors="replace")
        if not line:
            raise ExecutionUnavailableError(
                message=f"vsock read returned empty response (buf={buf!r})"
            )
        return json.loads(line)

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None


@ExecutionProviderRegistry.register("firecracker")
class FirecrackerExecProvider:
    """Execute commands inside a Firecracker microVM."""

    name = "firecracker"

    def __init__(self, config: "dict[str, Any] | None" = None) -> None:
        self._config = config or {}
        self._firecracker_bin: str = self._config.get("firecracker_bin", "/usr/local/bin/firecracker")
        self._jailer_bin: str = self._config.get("jailer_bin", "/usr/local/bin/jailer")
        self._kernel_image: str | None = self._config.get("kernel_image")
        self._rootfs: str | None = self._config.get("rootfs")
        self._socket_dir: str = self._config.get("socket_dir", "/srv/firecracker")
        self._vcpu_count: int = int(self._config.get("vcpu_count", 1))
        self._mem_size_mib: int = int(self._config.get("mem_size_mib", 128))
        self._guest_cid: int = int(self._config.get("guest_cid", DEFAULT_GUEST_CID))
        self._vsock_port: int = int(self._config.get("vsock_port", DEFAULT_VSOCK_PORT))
        self._use_jailer: bool = bool(self._config.get("use_jailer", False))
        self._boot_args: str = self._config.get(
            "boot_args", "console=ttyS0 reboot=k panic=1 pci=realloc init=/usr/local/bin/vsock-agent"
        )
        # Transient per-execution state, cleared on cleanup.
        self._active: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Health / capability detection (never fakes KVM availability)
    # ------------------------------------------------------------------
    async def health_check(self) -> bool:
        """Return True only if a REAL microVM can be booted here."""
        if not os.path.exists(self._firecracker_bin):
            logger.warning("Firecracker binary not found", extra={"path": self._firecracker_bin})
            return False
        if not self._kernel_image or not os.path.exists(self._kernel_image):
            logger.warning("Firecracker kernel image missing", extra={"kernel": self._kernel_image})
            return False
        if not self._rootfs or not os.path.exists(self._rootfs):
            logger.warning("Firecracker rootfs missing", extra={"rootfs": self._rootfs})
            return False
        if not self._real_kvm_device():
            logger.warning("/dev/kvm is not a usable KVM character device")
            return False
        if not _VsockClient.available():
            logger.warning("virtio-vsock (AF_VSOCK) unavailable on host")
            return False
        return True

    @staticmethod
    def _real_kvm_device() -> bool:
        """True only if /dev/kvm is a character device exposing KVM ioctl.

        A directory named /dev/kvm (as on the current UpCloud worker) does
        NOT satisfy this check.
        """
        try:
            st = os.stat("/dev/kvm")
        except OSError:
            return False
        import stat as _stat

        if not _stat.S_ISCHR(st.st_mode):
            return False
        # Attempt the KVM_GET_API_VERSION ioctl (0xAE00) to prove the
        # device is genuinely a KVM node, not a placeholder.
        import fcntl

        KVM_GET_API_VERSION = 0xAE00
        try:
            with open("/dev/kvm", "rb") as fd:
                return fcntl.ioctl(fd, KVM_GET_API_VERSION) > 0
        except OSError:
            return False

    # ------------------------------------------------------------------
    # Execution lifecycle
    # ------------------------------------------------------------------
    async def execute(self, command: str, timeout: float = 30.0) -> ExecResult:
        if not await self.health_check():
            raise ExecutionUnavailableError(
                message="Firecracker execution unavailable: KVM/guest transport missing"
            )

        microvm_id = f"kudbee-{uuid.uuid4().hex[:12]}"
        api_socket = os.path.join(self._socket_dir, f"{microvm_id}.sock")
        vsock_uds = os.path.join(self._socket_dir, f"{microvm_id}-vsock.sock")
        os.makedirs(self._socket_dir, exist_ok=True)

        started = time.monotonic()
        process: "asyncio.subprocess.Process | None" = None
        vsock: "_VsockClient | None" = None
        try:
            process = await self._start_vmm(microvm_id, api_socket)
            await self._configure(microvm_id, api_socket)
            await self._boot(api_socket)

            vsock = _VsockClient(self._guest_cid, self._vsock_port, vsock_uds)
            result = await asyncio.to_thread(vsock.execute_command, command, timeout)
            result.microvm_id = microvm_id
            result.metadata = {"api_socket": api_socket}
            duration = time.monotonic() - started
            result.duration = duration
            return result

            duration = time.monotonic() - started
            return ExecResult(
                stdout="".join(stdout_chunks),
                stderr="".join(stderr_chunks),
                return_code=return_code,
                duration=duration,
                provider=self.name,
                microvm_id=microvm_id,
                metadata={"api_socket": api_socket},
            )
        except ExecutionUnavailableError:
            raise
        except Exception as e:  # noqa: BLE001 - report as ExecResult, never swallow
            duration = time.monotonic() - started
            logger.error("Firecracker execution error", extra={"error": str(e)})
            return ExecResult(
                stdout="",
                stderr=str(e),
                return_code=-1,
                duration=duration,
                provider=self.name,
                microvm_id=microvm_id,
                error="firecracker_error",
            )
        finally:
            if vsock is not None:
                vsock.close()
            await self._shutdown(api_socket, process)
            self._cleanup(api_socket, microvm_id)

    # ------------------------------------------------------------------
    # Low-level helpers (kept separate so unit tests can mock them)
    # ------------------------------------------------------------------
    async def _start_vmm(self, microvm_id: str, api_socket: str) -> "asyncio.subprocess.Process":
        args = [self._firecracker_bin, "--api-sock", api_socket, "--id", microvm_id]
        if self._use_jailer:
            # The jailer spawns firecracker itself; exec the jailer instead.
            args = [
                self._jailer_bin,
                "--id", microvm_id,
                "--exec-file", self._firecracker_bin,
                "--uid", "0",
                "--gid", "0",
                "--",
                "--api-sock", api_socket,
            ]
        return await asyncio.create_subprocess_exec(*args)

    async def _configure(self, microvm_id: str, api_socket: str) -> None:
        await self._api_put(
            api_socket,
            "/machine-config",
            {"vcpu_count": self._vcpu_count, "mem_size_mib": self._mem_size_mib, "smt": False},
        )
        await self._api_put(
            api_socket,
            "/boot-source",
            {"kernel_image_path": self._kernel_image, "boot_args": self._boot_args},
        )
        await self._api_put(
            api_socket,
            "/drives/rootfs",
            {
                "drive_id": "rootfs",
                "path_on_host": self._rootfs,
                "is_root_device": True,
                "is_read_only": False,
            },
        )
        # Configure the virtio-vsock device so the host can reach the guest
        # agent over the Firecracker vsock Unix socket.
        vsock_uds = os.path.join(self._socket_dir, f"{microvm_id}-vsock.sock")
        await self._api_put(
            api_socket,
            "/vsock",
            {"guest_cid": self._guest_cid, "uds_path": vsock_uds},
        )

    async def _boot(self, api_socket: str) -> None:
        await self._api_put(api_socket, "/actions", {"action_type": "InstanceStart"})

    async def _shutdown(self, api_socket: str, process: "asyncio.subprocess.Process | None") -> None:
        try:
            await self._api_put(api_socket, "/actions", {"action_type": "SendCtrlAltDel"})
        except Exception:  # noqa: BLE001 - best-effort graceful shutdown
            logger.debug("SendCtrlAltDel failed; will terminate process")
        if process is not None:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except (ProcessLookupError, asyncio.TimeoutError):
                process.kill()

    def _cleanup(self, api_socket: str, microvm_id: str) -> None:
        try:
            os.remove(api_socket)
        except OSError:
            pass
        self._active.pop(microvm_id, None)

    async def _api_put(self, api_socket: str, path: str, payload: "dict[str, Any]") -> Any:
        """PUT *payload* to the Firecracker API over a Unix socket.

        Uses only the standard library (``http.client`` bound to an
        ``AF_UNIX`` socket). Isolated here so tests can mock it. The
        Firecracker API returns ``204 No Content`` for successful PUTs;
        we return the parsed JSON body when one is present.
        """
        import http.client

        body = json.dumps(payload).encode("utf-8")
        conn = http.client.HTTPConnection("localhost")
        # Route the connection over the Firecracker Unix socket.
        conn.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.sock.settimeout(10)
        conn.sock.connect(api_socket)
        try:
            conn.request(
                "PUT",
                path,
                body=body,
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8", errors="replace")
            if resp.status >= 400:
                raise ExecutionUnavailableError(
                    message=f"Firecracker API {path} failed: {resp.status} {raw}"
                )
            return json.loads(raw) if raw else None
        finally:
            conn.sock.close()

    async def shutdown(self) -> None:
        """Release any persistent resources (none held between executions)."""
        return None
        return body
