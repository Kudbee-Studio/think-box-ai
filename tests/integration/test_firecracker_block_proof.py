"""Block-device proof for Firecracker execution provider.

When vsock is unavailable, this test proves guest execution by having
the guest write KUDBEE_FIRECRACKER_OK to the rootfs, then reading it
after clean shutdown. This does NOT use vsock.

The test boots a microVM with a custom init script that writes the
marker file, then reads it from the host using debugfs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest

from core.execution.firecracker import FirecrackerExecProvider

DEFAULT_KERNEL = os.environ.get(
    "FIRECRACKER_KERNEL",
    os.path.expanduser("~/.cache/kudbee-fc/ubuntu-kernel"),
)
DEFAULT_ROOTFS = os.environ.get(
    "FIRECRACKER_ROOTFS",
    os.path.expanduser("~/.cache/kudbee-fc/rootfs.ext4"),
)
DEFAULT_FIRECRACKER = os.environ.get(
    "FIRECRACKER_BIN",
    os.path.expanduser("~/.cache/kudbee-fc/release-v1.16.1-x86_64/firecracker"),
)

MARKER_FILE = "/kudbee_proof.txt"
MARKER_CONTENT = "KUDBEE_FIRECRACKER_OK"


def _kvm_usable() -> bool:
    """Check if /dev/kvm is a usable KVM character device."""
    try:
        st = os.stat("/dev/kvm")
    except OSError:
        return False
    import stat as _stat
    if not _stat.S_ISCHR(st.st_mode):
        return False
    return True


@unittest.skipUnless(
    os.path.exists(DEFAULT_FIRECRACKER)
    and os.path.exists(DEFAULT_KERNEL)
    and _kvm_usable(),
    "Firecracker block proof requires /dev/kvm, firecracker and kernel",
)
class TestFirecrackerBlockProof(unittest.TestCase):
    """Block-device proof: guest writes marker to rootfs, host reads after shutdown."""

    def test_kudbee_firecracker_block_ok(self) -> None:
        """Boot a guest that writes KUDBEE_FIRECRACKER_OK to the rootfs."""
        # Create a temporary copy of the rootfs
        with tempfile.NamedTemporaryFile(suffix=".ext4", delete=False) as tmp:
            tmp_rootfs = tmp.name

        try:
            shutil.copy2(DEFAULT_ROOTFS, tmp_rootfs)

            # Create an init script that writes the marker
            init_script = f"""#!/bin/sh
echo "{MARKER_CONTENT}" > {MARKER_FILE}
sync
poweroff
"""
            # Inject the init script into the rootfs
            with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
                f.write(init_script)
                init_path = f.name

            os.chmod(init_path, 0o755)

            # Write the init script to the rootfs
            subprocess.run(
                ["debugfs", "-w", "-R", f"write {init_path} /init.sh", tmp_rootfs],
                capture_output=True,
                check=True,
            )
            os.unlink(init_path)

            # Create a provider with the temporary rootfs
            provider = FirecrackerExecProvider(
                {
                    "firecracker_bin": DEFAULT_FIRECRACKER,
                    "kernel_image": DEFAULT_KERNEL,
                    "rootfs": tmp_rootfs,
                    "boot_args": "console=ttyS0 reboot=k panic=1 init=/init.sh",
                    "vcpu_count": 1,
                    "mem_size_mib": 128,
                }
            )

            # Health check
            import asyncio
            health = asyncio.run(provider.health_check())
            self.assertTrue(health, "health_check should pass")

            # Boot and wait for shutdown (the guest will poweroff)
            # We can't use execute() because there's no vsock agent
            # Instead, we boot the VM and wait for it to shut down
            import time
            import uuid

            microvm_id = f"kudbee-{uuid.uuid4().hex[:12]}"
            api_socket = os.path.join("/srv/firecracker", f"{microvm_id}.sock")
            os.makedirs("/srv/firecracker", exist_ok=True)

            async def boot_and_wait():
                # Start Firecracker
                process = await asyncio.create_subprocess_exec(
                    DEFAULT_FIRECRACKER,
                    "--api-sock", api_socket,
                    "--id", microvm_id,
                )
                await asyncio.sleep(0.5)

                # Configure
                import http.client
                def api_put(path, payload):
                    body = json.dumps(payload).encode()
                    c = http.client.HTTPConnection("localhost")
                    c.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    c.sock.settimeout(10)
                    c.sock.connect(api_socket)
                    c.request("PUT", path, body, {"Content-Type": "application/json"})
                    r = c.getresponse()
                    r.read()
                    c.sock.close()

                api_put("/machine-config", {"vcpu_count": 1, "mem_size_mib": 128, "smt": False})
                api_put("/boot-source", {
                    "kernel_image_path": DEFAULT_KERNEL,
                    "boot_args": "console=ttyS0 reboot=k panic=1 init=/init.sh",
                })
                api_put("/drives/rootfs", {
                    "drive_id": "rootfs",
                    "path_on_host": tmp_rootfs,
                    "is_root_device": True,
                    "is_read_only": False,
                })
                api_put("/actions", {"action_type": "InstanceStart"})

                # Wait for the guest to shut down (up to 30 seconds)
                try:
                    await asyncio.wait_for(process.wait(), timeout=30.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

                # Cleanup
                try:
                    os.remove(api_socket)
                except OSError:
                    pass

            import json
            import socket
            asyncio.run(boot_and_wait())

            # Read the marker from the rootfs
            result = subprocess.run(
                ["debugfs", "-R", f"cat {MARKER_FILE}", tmp_rootfs],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"debugfs failed: {result.stderr}")
            self.assertIn(MARKER_CONTENT, result.stdout)

        finally:
            try:
                os.unlink(tmp_rootfs)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
