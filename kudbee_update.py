#!/usr/bin/env python3
"""KUDBEE Update Skill - Complete Project Status

Pulls comprehensive data from:
- UpCloud API (servers, storage, networks, floating IPs)
- GPU server (GPU status, models, services, disk, memory)
- Git repository (commits, branches, status)
- Production services (Ollama, Redis, Nginx, governance)

Usage:
    python3 kudbee_update.py
    python3 kudbee_update.py --format markdown
    python3 kudbee_update.py --format json
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

UPCLOUD_TOKEN = os.environ.get("THINKBOX_UPCLOUD_API_TOKEN", "")
GPU_IP = "87.58.149.157"
SSH_KEY = os.path.expanduser("~/.ssh/kilocloud")
WORKSPACE = "/workspace/bcdfac4f-1903-4a17-8abf-0b10fd495578/sessions/agent_7af7e70e-85ae-498e-a2cc-54314eddfe5a"

def api_call(method, path, data=None):
    """UpCloud API call."""
    base = "https://api.upcloud.com/1.3"
    cmd = ["curl", "-s", "-X", method, "-H", f"Authorization: Bearer {UPCLOUD_TOKEN}"]
    if data:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(data)]
    cmd.append(f"{base}{path}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(result.stdout)
    except:
        return {"error": result.stdout[:200]}

def ssh_cmd(cmd, timeout=30):
    """Run command on GPU server."""
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
         "-i", SSH_KEY, f"root@{GPU_IP}", cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip()

def get_upcloud_servers():
    """Get all UpCloud servers."""
    data = api_call("GET", "/server")
    servers = []
    for s in data.get("servers", {}).get("server", []):
        server = {
            "uuid": s["uuid"],
            "title": s["title"],
            "hostname": s["hostname"],
            "plan": s["plan"],
            "state": s["state"],
            "zone": s["zone"],
            "cores": s.get("core_number", "unknown"),
            "ram_mb": int(s.get("memory_amount", 0)),
            "ram_gb": int(s.get("memory_amount", 0)) // 1024,
            "ips": [],
            "storage": [],
        }
        for ip in s.get("ip_addresses", {}).get("ip_address", []):
            server["ips"].append({
                "address": ip["address"],
                "family": ip["family"],
                "access": ip["access"],
            })
        for sd in s.get("storage_devices", {}).get("storage_device", []):
            server["storage"].append({
                "uuid": sd.get("storage", "")[:8],
                "size_gb": int(sd.get("storage_size", 0)),
            })
        servers.append(server)
    return servers

def get_upcloud_storage():
    """Get all storage devices."""
    data = api_call("GET", "/storage")
    storages = []
    for s in data.get("storages", {}).get("storage", []):
        storages.append({
            "uuid": s["uuid"][:8],
            "title": s.get("title", "unknown"),
            "size": s.get("size", 0),
            "type": s.get("type", "unknown"),
            "state": s.get("state", "unknown"),
        })
    return storages

def get_upcloud_floating_ips():
    """Get floating IPs."""
    data = api_call("GET", "/ip_address")
    ips = []
    for ip in data.get("ip_addresses", {}).get("ip_address", []):
        if ip.get("floating") == "yes":
            ips.append({
                "address": ip["address"],
                "server": ip.get("server", "detached")[:8],
            })
    return ips

def get_gpu_status():
    """Get GPU status from server."""
    result = ssh_cmd("nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits 2>/dev/null || echo 'nvidia-smi failed'")
    gpus = []
    for line in result.split("\n"):
        if line.strip() and "failed" not in line:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "memory_used_mb": int(parts[2]),
                    "memory_total_mb": int(parts[3]),
                    "memory_used_pct": round(int(parts[2]) / int(parts[3]) * 100, 1) if int(parts[3]) > 0 else 0,
                    "utilization_pct": int(parts[4]),
                })
    return gpus

def get_server_resources():
    """Get CPU, RAM, disk usage."""
    output = ssh_cmd("echo '=== CPU ===' && uptime && echo '=== MEMORY ===' && free -h && echo '=== DISK ===' && df -h / /mnt/models && echo '=== DOCKER ===' && docker ps --format '{{.Names}}:{{.Status}}' 2>/dev/null || echo 'no docker'")
    return output

def get_services_status():
    """Get status of all services."""
    services = {}
    
    # Ollama
    ollama = ssh_cmd("curl -s http://localhost:11434/api/tags 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print([m['name'] for m in d.get('models',[])]\" 2>/dev/null || echo '[]'")
    services["ollama"] = {"status": "running" if "gpt" in ollama else "issue", "models": ollama}
    
    # Redis
    redis = ssh_cmd("redis-cli ping 2>/dev/null || echo 'DOWN'")
    services["redis"] = {"status": "running" if redis == "PONG" else "down"}
    
    # Nginx
    nginx = ssh_cmd("systemctl is-active nginx 2>/dev/null || echo 'unknown'")
    services["nginx"] = {"status": nginx}
    
    # ThinkBox
    thinkbox = ssh_cmd("curl -s http://localhost:9090/status 2>/dev/null | head -50")
    services["thinkbox"] = {"status": "running" if "boxes" in thinkbox else "down"}
    
    # Governance
    gov = ssh_cmd("curl -s http://localhost:8081/api/health 2>/dev/null | head -50")
    services["governance"] = {"status": "running" if "total_agents" in gov else "down"}
    
    return services

def get_game_progress():
    """Get game development progress."""
    output = ssh_cmd("find /opt/kudbee/projects -type f 2>/dev/null | head -20; echo '---'; ls -la /opt/kudbee/outputs/diffusion/*.png 2>/dev/null | wc -l; echo 'images generated'")
    return output

def get_git_status():
    """Get git repository status."""
    os.chdir(WORKSPACE)
    result = subprocess.run(["git", "log", "--oneline", "-10"], capture_output=True, text=True)
    commits = result.stdout.strip().split("\n")
    
    result2 = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    changes = result2.stdout.strip()
    
    result3 = subprocess.run(["git", "branch", "-a"], capture_output=True, text=True)
    branches = result3.stdout.strip().split("\n")
    
    return {
        "recent_commits": commits[:10],
        "uncommitted_changes": changes if changes else "clean",
        "branches": [b.strip().replace("* ", "") for b in branches[:10]],
    }

def generate_report(fmt="markdown"):
    """Generate comprehensive update report."""
    now = datetime.now(timezone.utc).isoformat()
    
    print(f"# 🎵 KUDBEE Project Status Report")
    print(f"**Generated:** {now}")
    print()
    
    # Infrastructure
    print("## 🖥️ Infrastructure (UpCloud)")
    print()
    servers = get_upcloud_servers()
    total_cost = 0
    for s in servers:
        print(f"### {s['title']} ({s['state']})")
        print(f"- **Plan:** {s['plan']}")
        print(f"- **Zone:** {s['zone']}")
        print(f"- **Cores:** {s['cores']} | **RAM:** {s['ram_gb']} GB")
        print(f"- **IPs:** {', '.join(ip['address'] for ip in s['ips'])}")
        print(f"- **Storage:** {', '.join(str(st['size_gb']) + 'GB' for st in s['storage'])}")
        print()
    
    floating = get_upcloud_floating_ips()
    if floating:
        print("### Floating IPs")
        for ip in floating:
            print(f"- {ip['address']} → {ip['server']}")
        print()
    
    # GPU Status
    print("## 🎮 GPU Fleet")
    print()
    gpus = get_gpu_status()
    for gpu in gpus:
        bar = "█" * int(gpu["memory_used_pct"] / 5) + "░" * (20 - int(gpu["memory_used_pct"] / 5))
        print(f"**GPU {gpu['index']}:** {gpu['name']}")
        print(f"- Memory: {bar} {gpu['memory_used_mb']}/{gpu['memory_total_mb']} MB ({gpu['memory_used_pct']}%)")
        print(f"- Utilization: {gpu['utilization_pct']}%")
        print()
    
    # Server Resources
    print("## 📊 Server Resources")
    print()
    resources = get_server_resources()
    print("```")
    print(resources[:500])
    print("```")
    print()
    
    # Services
    print("## 🔧 Running Services")
    print()
    services = get_services_status()
    for name, info in services.items():
        icon = "✅" if info["status"] in ["running", "active", "PONG"] else "❌"
        print(f"- {icon} **{name}:** {info['status']}")
        if "models" in info:
            print(f"  - Models: {info['models']}")
    print()
    
    # Game Progress
    print("## 🎬 Production Progress")
    print()
    progress = get_game_progress()
    print("```")
    print(progress[:300])
    print("```")
    print()
    
    # Git Status
    print("## 📝 Repository Status")
    print()
    git = get_git_status()
    print(f"**Branches:** {len(git['branches'])}")
    print(f"**Uncommitted:** {git['uncommitted_changes']}")
    print()
    print("### Recent Commits")
    for commit in git["recent_commits"][:5]:
        print(f"- {commit}")
    print()
    
    # Summary
    print("## 📋 Summary")
    print()
    print(f"- **Servers:** {len(servers)}")
    print(f"- **GPUs:** {len(gpus)} L40S")
    print(f"- **Total VRAM:** {sum(g['memory_total_mb'] for g in gpus) // 1024} GB")
    print(f"- **Used VRAM:** {sum(g['memory_used_mb'] for g in gpus) // 1024} GB")
    print(f"- **Services Running:** {sum(1 for s in services.values() if s['status'] in ['running', 'active', 'PONG'])}/{len(services)}")


if __name__ == "__main__":
    fmt = "markdown"
    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        if idx + 1 < len(sys.argv):
            fmt = sys.argv[idx + 1]
    
    if fmt == "json":
        # JSON output
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "servers": get_upcloud_servers(),
            "gpus": get_gpu_status(),
            "services": get_services_status(),
            "git": get_git_status(),
        }
        print(json.dumps(report, indent=2))
    else:
        generate_report(fmt)
