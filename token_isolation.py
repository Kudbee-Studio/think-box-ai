#!/usr/bin/env python3
"""KUDBEE THINK Token Isolation — Docker Edition

Provides isolated execution environments for Think Tokens
using Docker containers (works without KVM/Firecracker).

Each token gets its own container with:
- Scoped filesystem
- Network isolation
- Resource limits
- GPU access (optional)
"""

import os
import json
import subprocess
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = "/opt/kudbee/memory/think_tokens.db"
CONTAINER_PREFIX = "ku3bee-think-"
BASE_IMAGE = "python:3.12-slim"


class TokenContainer:
    """Manages a Docker container for a Think Token."""
    
    def __init__(self, token_id: str, capabilities: list[str],
                 vram_limit: str = "0", network_isolation: bool = True):
        self.token_id = token_id
        self.container_name = f"{CONTAINER_PREFIX}{token_id.lower()}"
        self.capabilities = capabilities
        self.vram_limit = vram_limit
        self.network_isolation = network_isolation
        self.status = "pending"
        self.container_id = None
    
    def deploy(self) -> bool:
        """Deploy the container for this token."""
        # Build the Docker run command
        cmd = ["docker", "run", "-d", "--name", self.container_name]
        
        # Resource limits
        cmd.extend(["--memory", "2g"])
        cmd.extend(["--cpus", "1.0"])
        
        # Network isolation
        if self.network_isolation:
            cmd.extend(["--network", "none"])
        else:
            cmd.extend(["--network", "ku3bee-net"])
        
        # GPU access (if requested)
        if self.vram_limit != "0":
            cmd.extend(["--gpus", f"all,self->{self.vram_limit}"])
        
        # Volume mounts (scoped)
        token_data = f"/opt/kudbee/tokens/{self.token_id}"
        os.makedirs(token_data, exist_ok=True)
        cmd.extend(["-v", f"{token_data}:/data"])
        
        # Environment
        cmd.extend(["-e", f"THINK_TOKEN_ID={self.token_id}"])
        cmd.extend(["-e", f"THINK_CAPABILITIES={','.join(self.capabilities)}"])
        
        # Base image
        cmd.append(BASE_IMAGE)
        
        # Keep container running
        cmd.extend(["sleep", "infinity"])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                self.container_id = result.stdout.strip()[:12]
                self.status = "running"
                self._register()
                return True
            else:
                self.status = "failed"
                return False
        except Exception as e:
            self.status = "failed"
            return False
    
    def execute(self, task: str) -> dict:
        """Execute a task inside the container."""
        if self.status != "running":
            return {"error": "Container not running"}
        
        # Write task to shared volume
        task_file = f"/opt/kudbee/tokens/{self.token_id}/task.json"
        with open(task_file, "w") as f:
            json.dump({
                "task": task,
                "capabilities": self.capabilities,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, f)
        
        # Execute in container
        cmd = [
            "docker", "exec", self.container_name,
            "python3", "-c",
            f"import json; task=json.load(open('/data/task.json')); print(f'Processing: {{task[\"task\"][:50]}}')"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return {
                "token_id": self.token_id,
                "output": result.stdout.strip()[:500],
                "success": result.returncode == 0,
            }
        except Exception as e:
            return {"error": str(e)}
    
    def stop(self):
        """Stop the container."""
        subprocess.run(["docker", "stop", self.container_name], capture_output=True, timeout=30)
        self.status = "stopped"
    
    def destroy(self):
        """Destroy the container."""
        subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=30)
        self.status = "destroyed"
    
    def _register(self):
        """Register container in database."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS token_containers (
                container_id TEXT PRIMARY KEY,
                token_id TEXT NOT NULL,
                container_name TEXT,
                capabilities TEXT,
                status TEXT,
                created TEXT NOT NULL,
                FOREIGN KEY (token_id) REFERENCES think_tokens(token_id)
            )
        """)
        conn.execute("""
            INSERT OR REPLACE INTO token_containers 
            (container_id, token_id, container_name, capabilities, status, created)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            self.container_id, self.token_id, self.container_name,
            json.dumps(self.capabilities), self.status,
            datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()


class TokenIsolationManager:
    """Manages isolated containers for all Think Tokens."""
    
    def __init__(self):
        self.containers = {}
        self._ensure_network()
    
    def _ensure_network(self):
        """Ensure Docker network exists."""
        subprocess.run(
            ["docker", "network", "create", "ku3bee-net", "--internal"],
            capture_output=True, timeout=10
        )
    
    def deploy_token(self, token_id: str, capabilities: list[str],
                     vram_limit: str = "0") -> TokenContainer:
        """Deploy an isolated container for a token."""
        container = TokenContainer(token_id, capabilities, vram_limit)
        
        if container.deploy():
            self.containers[token_id] = container
        
        return container
    
    def list_containers(self) -> list:
        """List all token containers."""
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={CONTAINER_PREFIX}",
             "--format", "{{.ID}}|{{.Names}}|{{.Status}}"],
            capture_output=True, text=True, timeout=10
        )
        
        containers = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|")
                if len(parts) >= 3:
                    containers.append({
                        "id": parts[0],
                        "name": parts[1],
                        "status": parts[2],
                    })
        
        return containers
    
    def cleanup(self):
        """Stop and remove all token containers."""
        for container in self.containers.values():
            container.destroy()
        self.containers = {}


if __name__ == "__main__":
    manager = TokenIsolationManager()
    
    # Deploy some test tokens
    print("Deploying THINK token containers...")
    
    c1 = manager.deploy_token("THINK-TEST-001", ["read", "execute"])
    print(f"Deployed: {c1.container_name} ({c1.status})")
    
    c2 = manager.deploy_token("THINK-TEST-002", ["read", "write"])
    print(f"Deployed: {c2.container_name} ({c2.status})")
    
    c3 = manager.deploy_token("THINK-TEST-003", ["gpu", "execute"], vram_limit="8GB")
    print(f"Deployed: {c3.container_name} ({c3.status})")
    
    print(f"\nRunning containers:")
    for c in manager.list_containers():
        print(f"  {c['name']}: {c['status']}")
