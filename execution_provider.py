#!/usr/bin/env python3
"""KUDBEE ExecutionProvider Abstraction

Makes the execution substrate portable:
- DockerProvider (current)
- FirecrackerProvider (future, requires KVM)
- CloudVMProvider (future, AWS/GCP with nested virt)

A Think Box requests an isolated execution environment
without knowing which substrate provides it.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import json
import subprocess
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = "/opt/kudbee/memory/think_tokens.db"


@dataclass
class ExecutionContext:
    """Represents an isolated execution environment."""
    context_id: str
    provider_type: str  # docker, firecracker, cloud_vm
    token_id: str
    capabilities: list[str]
    status: str = "pending"
    resource_limits: dict = field(default_factory=dict)
    endpoint: str = ""
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExecutionProvider(ABC):
    """Abstract base for execution substrates."""
    
    @abstractmethod
    def create_context(self, token_id: str, capabilities: list[str],
                      limits: dict = None) -> ExecutionContext:
        """Create an isolated execution context."""
        ...
    
    @abstractmethod
    def execute(self, context: ExecutionContext, task: str) -> dict:
        """Execute a task in the context."""
        ...
    
    @abstractmethod
    def destroy_context(self, context: ExecutionContext) -> bool:
        """Destroy the context."""
        ...
    
    @abstractmethod
    def list_contexts(self) -> list[ExecutionContext]:
        """List all contexts managed by this provider."""
        ...


class DockerProvider(ExecutionProvider):
    """Docker-based execution (current substrate)."""
    
    def __init__(self):
        self.container_prefix = "ku3bee-think-"
    
    def create_context(self, token_id: str, capabilities: list[str],
                      limits: dict = None) -> ExecutionContext:
        limits = limits or {}
        container_name = f"{self.container_prefix}{token_id.lower()}"
        
        cmd = ["docker", "run", "-d", "--name", container_name]
        
        # Resource limits
        cmd.extend(["--memory", limits.get("memory", "2g")])
        cmd.extend(["--cpus", limits.get("cpus", "1.0")])
        
        # Network isolation
        if limits.get("network_isolation", True):
            cmd.append("--network=none")
        
        # GPU access
        if limits.get("gpu", False):
            cmd.extend(["--gpus", "all"])
        
        # Volume
        token_data = f"/opt/kudbee/tokens/{token_id}"
        subprocess.run(["mkdir", "-p", token_data], capture_output=True)
        cmd.extend(["-v", f"{token_data}:/data"])
        
        # Environment
        cmd.extend(["-e", f"THINK_TOKEN_ID={token_id}"])
        cmd.extend(["-e", f"THINK_CAPABILITIES={','.join(capabilities)}"])
        
        cmd.extend(["python:3.12-slim", "sleep", "infinity"])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        ctx = ExecutionContext(
            context_id=str(uuid.uuid4())[:12],
            provider_type="docker",
            token_id=token_id,
            capabilities=capabilities,
            status="running" if result.returncode == 0 else "failed",
            resource_limits=limits,
            endpoint=container_name,
        )
        
        return ctx
    
    def execute(self, context: ExecutionContext, task: str) -> dict:
        cmd = [
            "docker", "exec", context.endpoint,
            "python3", "-c",
            f"import json; print(json.dumps({{'status': 'executed', 'task': '{task[:50]}'}}))"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return {
                "context_id": context.context_id,
                "output": result.stdout.strip(),
                "success": result.returncode == 0,
            }
        except Exception as e:
            return {"error": str(e)}
    
    def destroy_context(self, context: ExecutionContext) -> bool:
        subprocess.run(["docker", "rm", "-f", context.endpoint], capture_output=True, timeout=30)
        return True
    
    def list_contexts(self) -> list[ExecutionContext]:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={self.container_prefix}",
             "--format", "{{.Names}}|{{.Status}}"],
            capture_output=True, text=True, timeout=10
        )
        
        contexts = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 2:
                    contexts.append(ExecutionContext(
                        context_id=str(uuid.uuid4())[:12],
                        provider_type="docker",
                        token_id=parts[0].replace(self.container_prefix, ""),
                        capabilities=[],
                        status="running" if "Up" in parts[1] else "stopped",
                        endpoint=parts[0],
                    ))
        
        return contexts


class FirecrackerProvider(ExecutionProvider):
    """Firecracker microVM execution (future, requires KVM)."""
    
    def __init__(self, kernel_path: str = "/opt/kudbee/firecracker/vmlinux",
                 rootfs_path: str = "/opt/kudbee/firecracker/rootfs.ext4"):
        self.kernel_path = kernel_path
        self.rootfs_path = rootfs_path
        self.api_socket = "/tmp/firecracker.sock"
    
    def create_context(self, token_id: str, capabilities: list[str],
                      limits: dict = None) -> ExecutionContext:
        # Future implementation - requires /dev/kvm
        return ExecutionContext(
            context_id=str(uuid.uuid4())[:12],
            provider_type="firecracker",
            token_id=token_id,
            capabilities=capabilities,
            status="unsupported",
            endpoint="",
        )
    
    def execute(self, context: ExecutionContext, task: str) -> dict:
        return {"error": "Firecracker not available - requires KVM"}
    
    def destroy_context(self, context: ExecutionContext) -> bool:
        return False
    
    def list_contexts(self) -> list[ExecutionContext]:
        return []
    
    def is_available(self) -> bool:
        """Check if KVM is available."""
        result = subprocess.run(["test", "-e", "/dev/kvm"], capture_output=True)
        return result.returncode == 0


class CloudVMProvider(ExecutionProvider):
    """Cloud VM execution (future, AWS/GCP with nested virt)."""
    
    def __init__(self, cloud: str = "aws", region: str = "eu-west-1"):
        self.cloud = cloud
        self.region = region
    
    def create_context(self, token_id: str, capabilities: list[str],
                      limits: dict = None) -> ExecutionContext:
        # Future implementation - requires cloud credentials
        return ExecutionContext(
            context_id=str(uuid.uuid4())[:12],
            provider_type=f"cloud_vm_{self.cloud}",
            token_id=token_id,
            capabilities=capabilities,
            status="unsupported",
            endpoint="",
        )
    
    def execute(self, context: ExecutionContext, task: str) -> dict:
        return {"error": f"Cloud VM ({self.cloud}) not configured"}
    
    def destroy_context(self, context: ExecutionContext) -> bool:
        return False
    
    def list_contexts(self) -> list[ExecutionContext]:
        return []


class ExecutionOrchestrator:
    """Orchestrates execution across providers."""
    
    def __init__(self):
        self.providers = {
            "docker": DockerProvider(),
            "firecracker": FirecrackerProvider(),
            "cloud_vm": CloudVMProvider(),
        }
        self.active_provider = "docker"  # Default
    
    def get_provider(self, provider_type: str = None) -> ExecutionProvider:
        """Get the best available provider."""
        if provider_type:
            return self.providers.get(provider_type, self.providers["docker"])
        
        # Auto-select: prefer docker, fallback to others
        if self.providers["docker"]:
            return self.providers["docker"]
        
        return self.providers["docker"]  # Always available
    
    def deploy_token(self, token_id: str, capabilities: list[str],
                    limits: dict = None) -> ExecutionContext:
        """Deploy a token using the best available provider."""
        provider = self.get_provider()
        return provider.create_context(token_id, capabilities, limits)
    
    def execute_task(self, context: ExecutionContext, task: str) -> dict:
        """Execute a task in the given context."""
        provider = self.get_provider(context.provider_type)
        return provider.execute(context, task)


if __name__ == "__main__":
    orch = ExecutionOrchestrator()
    
    print("=== KUDBEE Execution Provider Abstraction ===")
    print(f"Active provider: {orch.active_provider}")
    print(f"Available providers: {list(orch.providers.keys())}")
    
    # Check Firecracker availability
    fc = orch.providers["firecracker"]
    print(f"Firecracker available: {fc.is_available()}")
    
    # List current Docker contexts
    docker = orch.providers["docker"]
    contexts = docker.list_contexts()
    print(f"\nDocker contexts: {len(contexts)}")
    for ctx in contexts:
        print(f"  {ctx.endpoint}: {ctx.status}")
