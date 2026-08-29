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
DEFAULT_KERNEL = "/srv/firecracker/vmlinux"
DEFAULT_ROOTFS = "/srv/firecracker/rootfs.ext4"
DEFAULT_FIRECRACKER = shutil.which("firecracker") or "/usr/local/bin/firecracker"


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _kvm_usable() -> bool:
    """Mirror the provider's honest KVM detection without importing internals."""
    if not FirecrackerExecProvider._real_kvm_device():
        return False
    return True


@unittest.skipUnless(
    os.path.exists(DEFAULT_FIRECRACKER)
    and os.path.exists(DEFAULT_KERNEL)
    and os.path.exists(DEFAULT_ROOTFS)
    and _kvm_usable(),
    "Firecracker proof-of-life requires /dev/kvm, firecracker, kernel and rootfs",
)
class TestFirecrackerProofOfLife(unittest.TestCase):
    """Real microVM boot + in-guest command execution (skips if impossible)."""

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
