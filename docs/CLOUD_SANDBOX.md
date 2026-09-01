# Cloud Sandbox Agents

**Issue:** #15 — Phase 4: Cloud Sandbox Agents (Firecracker/gVisor)
**Status:** Architecture design — implementation requires infrastructure

## Why Sandboxes?

- **Security** — Untrusted code can't escape
- **Isolation** — Each job runs in its own VM
- **Reproducibility** — Same environment every time
- **Resource limits** — CPU, memory, disk caps

## Sandbox Technologies

| Technology | Type | Overhead | Use Case |
|------------|------|----------|----------|
| Firecracker | MicroVM | ~125ms cold start | Production workloads |
| gVisor | Runtime sandbox | ~50ms | Container isolation |
| Docker + seccomp | Container | ~5ms | Development |
| WASM | Sandbox | ~1ms | Lightweight tasks |

## Architecture

```
┌─────────────────────────────────────────┐
│  API Gateway                            │
│  - Rate limiting                        │
│  - Auth (API key)                       │
│  - Job routing                          │
├─────────────────────────────────────────┤
│  Scheduler                              │
│  - Priority queue                       │
│  - Resource allocation                  │
│  - Retry logic                          │
├─────────────────────────────────────────┤
│  Sandbox Pool                           │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
│  │ VM1 │ │ VM2 │ │ VM3 │ │ VM4 │       │
│  └─────┘ └─────┘ └─────┘ └─────┘       │
├─────────────────────────────────────────┤
│  Storage                                │
│  - Job artifacts                        │
│  - Snapshots                            │
│  - Logs                                 │
└─────────────────────────────────────────┘
```

## Implementation: Firecracker

```python
import subprocess
import json

class FirecrackerSandbox:
    def __init__(self, vm_id: str, cpu: int = 1, mem_mb: int = 512):
        self.vm_id = vm_id
        self.cpu = cpu
        self.mem_mb = mem_mb

    def start(self):
        """Start a microVM."""
        subprocess.run([
            "firecracker", "--api-sock", f"/tmp/{self.vm_id}.sock"
        ])
        # Configure
        self._configure()

    def run_job(self, code: str) -> dict:
        """Execute code inside the sandbox."""
        # Send code to agent via VSOCK
        # Collect results
        return {"status": "completed", "output": ""}

    def stop(self):
        """Shutdown the microVM."""
        subprocess.run(["curl", "--unix-socket", f"/tmp/{self.vm_id}.sock",
                       "-X", "PUT", "http://localhost/actions",
                       "-d", '{"action_type": "SendCtrlAltDel"}'])
```

## Implementation: gVisor (runsc)

```python
import docker

client = docker.from_env()

def run_sandboxed(code: str, timeout: int = 30) -> dict:
    """Run code in a gVisor sandbox."""
    container = client.containers.run(
        "python:3.11-slim",
        f"python -c '{code}'",
        runtime="runsc",  # gVisor
        mem_limit="512m",
        cpu_quota=100000,
        network_mode="none",
        detach=True,
        remove=True
    )
    try:
        result = container.wait(timeout=timeout)
        logs = container.logs().decode()
        return {"status": "completed", "exit_code": result["StatusCode"], "output": logs}
    except Exception as e:
        container.kill()
        return {"status": "timeout", "error": str(e)}
```

## Security Rules

1. **No network** — Sandboxes are network-isolated by default
2. **Read-only root** — Only /tmp is writable
3. **Resource limits** — CPU, memory, disk, PID caps
4. **Timeout** — Max 5 minutes per job
5. **No privilege escalation** — Drop all capabilities

## Kudbee Action Items

1. [ ] Provision bare metal or cloud instance with KVM
2. [ ] Install Firecracker or gVisor
3. [ ] Build base VM image (Python + tools)
4. [ ] Implement scheduler
5. [ ] Add monitoring + logging
6. [ ] Load test with 100 concurrent jobs
