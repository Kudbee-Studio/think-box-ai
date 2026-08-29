# KVM Host Acceptance Runbook

This document describes the **empirical checks** a human operator runs on a
candidate Linux host to confirm it can run KUDBEE's Firecracker execution
provider. Passing these checks unskips the real integration test
(`tests/integration/test_firecracker_execution.py`).

## What we are validating

A host is accepted only when **all** of the following are true empirically:

1. `/dev/kvm` is a **character device** (not a directory)
2. The **KVM API is usable** (`KVM_GET_API_VERSION` ioctl succeeds)
3. The current process can **open `/dev/kvm` read-write**

We do NOT accept a host because a provider "supports nested virtualization".
We accept it because we can prove it.

---

## Step 1 — OS and architecture

```bash
uname -a
uname -m
```

Expected: `x86_64` (or `aarch64` if the implementation explicitly supports it).
Linux kernel 5.7+ recommended (for UFFD snapshot support).

---

## Step 2 — Virtualization mode

```bash
systemd-detect-virt --vm
```

- `none` → bare metal or KVM guest with full hardware access. **Good.**
- `kvm` → you are inside a KVM guest. Nested virtualization **might** be
  exposed — continue to Step 3 to find out.
- Anything else (xen, vmware, oracle) → check that provider's nested-virt docs.

---

## Step 3 — CPU flags

```bash
lscpu | grep -E "Virtualization|vmx|svm"
grep -E "vmx|svm" /proc/cpuinfo | head -1
```

- `vmx` (Intel) or `svm` (AMD) **must** be present in `/proc/cpuinfo`.
- `lscpu` should report `Virtualization: VT-x` (Intel) or `AMD-V` (AMD).

If neither flag appears, the hypervisor is not passing through hardware
virtualization extensions. **Stop — this host cannot run Firecracker.**

---

## Step 4 — `/dev/kvm` existence and file type

```bash
ls -l /dev/kvm
stat -c '%F' /dev/kvm
test -c /dev/kvm && echo "CHAR_DEVICE_OK" || echo "NOT_A_CHAR_DEVICE"
```

Expected:
- `ls -l` shows `crw-rw-rw-` (the leading `c` = character device)
- `stat` reports `character special file`
- `test -c /dev/kvm` succeeds

**Critical distinction:**
- `/dev/kvm` **exists** — not sufficient.
- `/dev/kvm` **is a character device** — required.
- `/dev/kvm` **is a directory** — this is the failure mode on the current
  UpCloud host. **Stop.**

---

## Step 5 — KVM API usability (ioctl)

Run this Python one-liner to verify the KVM API actually works:

```bash
python3 - <<'PY'
import fcntl, os, struct

KVM_GET_API_VERSION = 0xAE00

try:
    fd = os.open("/dev/kvm", os.O_RDWR | os.O_CLOEXEC)
    try:
        version = fcntl.ioctl(fd, KVM_GET_API_VERSION, 0)
        print(f"KVM_API_VERSION={version}  IOCTL_OK")
    finally:
        os.close(fd)
except PermissionError:
    print("KVM_PERMISSION_DENIED")
except OSError as e:
    print(f"KVM_API_UNAVAILABLE: {e}")
PY
```

Expected: `KVM_API_VERSION=12  IOCTL_OK`

Anything else means the device exists but KVM is not functional. **Stop.**

---

## Step 6 — Process can open `/dev/kvm`

```bash
python3 -c 'open("/dev/kvm", "rb").close(); print("OPEN_OK" if True else "")'
```

If this raises `PermissionError`, the user is not in the `kvm` group and
cannot use KVM without root. Fix: `sudo usermod -aG kvm $USER` and re-login.

---

## Step 7 — Environment variables for tests

Once the host passes Steps 1–6, set these to unskip the Firecracker
integration test:

```bash
export FIRECRACKER_BIN="/usr/local/bin/firecracker"
export FIRECRACKER_KERNEL="/srv/firecracker/vmlinux"
export FIRECRACKER_ROOTFS="/srv/firecracker/rootfs.ext4"
```

The test `tests/integration/test_firecracker_execution.py` will then run
(unskipped) and produce:

```
KUDBEE_FIRECRACKER_OK
```

---

## Known issues

### Firecracker v1.16.1 vsock proxy

The Firecracker v1.16.1 vsock proxy may reset connections from the host even
when a guest agent is listening. This has been observed on `cloudchamber`
(x86_64 KVM guest with working `/dev/kvm`) with the Firecracker CI minimal
kernel (vmlinux.bin) and Alpine rootfs (boottime-rootfs.ext4).

**Symptom:** `Connection reset by peer` (errno 104) when connecting to the
host-side vsock Unix socket or via `AF_VSOCK` to the guest CID, despite the
guest agent logging `listening on port 1024`.

**Possible causes:**
1. The minimal Firecracker CI kernel (4.14.x) has a virtio-mmio driver issue
   that prevents the vsock device from being fully initialized.
2. Firecracker's vsock proxy in v1.16.1 may have a bug with certain kernel
   versions.
3. The `pci=off` parameter (added by Firecracker by default after user boot
   args) may interfere with virtio-mmio device initialization.

**Workarounds to try:**
1. Use a newer kernel (5.10+) with built-in virtio-mmio and virtio-vsock
   support, such as the Ubuntu kernel from Firecracker CI:
   `https://s3.amazonaws.com/spec.ccfc.min/img/x86_64/ubuntu/kernel/vmlinux.bin`
2. Use a more recent Firecracker release (v1.7+) which may have vsock fixes.
3. Use the `debian_with_ssh_and_balloon` rootfs which includes a working
   init system and vsock setup.

### Verifying the guest agent

To verify the guest agent is running inside the microVM, enable the serial
console in the boot args (remove `console=ttyS0` or add `earlyprintk`) and
check the Firecracker process's stderr output. The agent logs to
`/dev/console` with the prefix `[vsock-agent]`.

When a host passes, record:

```
host: <hostname/ip>
date: <ISO8601>
uname -a: <output>
systemd-detect-virt: <output>
cpu flags: vmx|svm
/dev/kvm: char device (confirmed via stat + test -c)
KVM_GET_API_VERSION: 12 (ioctl OK)
integration test: KUDBEE_FIRECRACKER_OK
operator: <name>
```

This is the **only** acceptance record that matters. Provider marketing
claims are not a substitute.
