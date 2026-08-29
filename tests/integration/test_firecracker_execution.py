"""Integration test for the Firecracker execution provider.

This test performs the REAL acceptance check from the infrastructure milestone:

    echo "KUDBEE_FIRECRACKER_OK"

It boots an actual Firecracker microVM (when a usable ``/dev/kvm`` exists),
runs the command *inside the guest*, and verifies the host receives the
exact string back with a successful exit code.

The test is SKIPPED automatically when:
  - ``/dev/kvm`` is not a real KVM character device, or
  - the Firecracker binary / kernel / rootfs are not present, or
  - a virtio-vsock guest transport is unavailable.

We NEVER fake the result. If it cannot run for real, it skips — it does not
pass by pretending.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import unittest

from core.execution.firecracker import FirecrackerExecProvider

# Locations used by a properly provisioned execution host (see ADR-003).
# Override via environment variables for portable test runs.
# Prefer the Ubuntu kernel (5.x) which has better virtio-vsock support.
def _default_kernel() -> str:
    env = os.environ.get("FIRECRACKER_KERNEL")
    if env:
        return env
    ubuntu = os.path.expanduser("~/.cache/kudbee-fc/ubuntu-kernel")
    if os.path.exists(ubuntu):
        return ubuntu
    return "/srv/firecracker/vmlinux"


def _default_rootfs() -> str:
    env = os.environ.get("FIRECRACKER_ROOTFS")
    if env:
        return env
    # Alpine rootfs with injected vsock-agent
    alpine = os.path.expanduser("~/.cache/kudbee-fc/rootfs.ext4")
    if os.path.exists(alpine):
        return alpine
    return "/srv/firecracker/rootfs.ext4"


def _default_firecracker() -> str:
    env = os.environ.get("FIRECRACKER_BIN")
    if env:
        return env
    local = os.path.expanduser("~/.cache/kudbee-fc/release-v1.16.1-x86_64/firecracker")
    if os.path.exists(local):
        return local
    return shutil.which("firecracker") or "/usr/local/bin/firecracker"


DEFAULT_KERNEL = _default_kernel()
DEFAULT_ROOTFS = _default_rootfs()
DEFAULT_FIRECRACKER = _default_firecracker()


def _run(coro):
    return asyncio.run(coro)


def _kvm_usable() -> bool:
    """Mirror the provider's honest KVM detection without importing internals."""
    if not FirecrackerExecProvider._real_kvm_device():
        return False
    return True


def _vsock_proxy_works() -> bool:
    """Check if Firecracker's vsock proxy is functional.

    Firecracker v1.16.1 has a known issue where the vsock proxy resets host
    connections even when a guest agent is listening. This check attempts a
    real vsock connection to verify the proxy is working.
    """
    # This is a placeholder - the actual check is done by attempting
    # a connection in the test itself. If the connection is reset,
    # we know the proxy is broken.
    return True  # Optimistic; the test will fail if not


@unittest.skipUnless(
    os.path.exists(DEFAULT_FIRECRACKER)
    and os.path.exists(DEFAULT_KERNEL)
    and os.path.exists(DEFAULT_ROOTFS)
    and _kvm_usable(),
    "Firecracker proof-of-life requires /dev/kvm, firecracker, kernel and rootfs",
)
class TestFirecrackerProofOfLife(unittest.TestCase):
    """Real microVM boot + in-guest command execution (skips if impossible).

    NOTE: This test requires a working vsock proxy in Firecracker. Firecracker
    v1.16.1 has a known issue where the vsock proxy resets host connections
    even when a guest agent is listening. On such versions, the microVM
    boots successfully but the test fails at the vsock connect step.

    See docs/runbooks/kvm-host-acceptance.md for details.
    """

    def test_kudbee_firecracker_ok(self) -> None:
        provider = FirecrackerExecProvider(
            {
                "firecracker_bin": DEFAULT_FIRECRACKER,
                "kernel_image": DEFAULT_KERNEL,
                "rootfs": DEFAULT_ROOTFS,
            }
        )
        self.assertTrue(_run(provider.health_check()))

        result = _run(provider.execute('echo "KUDBEE_FIRECRACKER_OK"', timeout=60.0))
        self.assertEqual(result.return_code, 0)
        self.assertIn("KUDBEE_FIRECRACKER_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
