#!/usr/bin/env python3
"""KUDBEE 30-Minute Autonomous Production Sprint

Maximizes GPU utilization, continuous production, full logging.
Reports every 5 minutes via memory relay.
"""

import json
import os
import subprocess
import time
import urllib.request
import sqlite3
from datetime import datetime, timezone

DB_PATH = "/opt/kudbee/memory/think_tokens.db"
RELAY_LOG = "/opt/kudbee/logs/sprint_relay.log"
PRODUCTION_LOG = "/opt/kudbee/logs/sprint_production.log"

os.makedirs("/opt/kudbee/logs", exist_ok=True)


def relay(msg):
    """Send message to relay log."""
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = f"[{timestamp}] {msg}"
    with open(RELAY_LOG, "a") as f:
        f.write(entry + "\n")
    print(entry)


def get_gpu_stats():
    """Get GPU utilization."""
    result = subprocess.run([
        "nvidia-smi", "--query-gpu=index,utilization.gpu,memory.used,memory.total",
        "--format=csv,noheader"
    ], capture_output=True, text=True, timeout=10)
    return result.stdout.strip()


def get_cost_estimate():
    """Estimate hourly cost (UpCloud GPU-SPOT ~$3.82/hr)."""
    return 3.82


def phase1_audit():
    """Phase 1: Diagnostic audit (Minute 0-5)."""
    relay("=== PHASE 1: INITIALIZATION & AUDIT ===")
    
    # GPU stats
    gpu = get_gpu_stats()
    relay(f"GPU STATUS:\n{gpu}")
    
    # Docker containers
    containers = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}: {{.Status}}"],
        capture_output=True, text=True, timeout=10
    )
    relay(f"CONTAINERS:\n{containers.stdout.strip()}")
    
    # Services
    services = subprocess.run(
        ["systemctl", "list-units", "--state=running", "--no-pager"],
        capture_output=True, text=True, timeout=10
    )
    active = [l for l in services.stdout.split("\n") if "kudbee" in l.lower() or "ollama" in l.lower() or "nginx" in l.lower()]
    relay(f"ACTIVE SERVICES: {len(active)}")
    
    # Models
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            models = json.loads(resp.read().decode()).get("models", [])
            relay(f"LOADED MODELS: {len(models)}")
            for m in models:
                relay(f"  {m['name']}: {m.get('size', 0)/1e9:.1f}GB")
    except:
        relay("MODELS: Ollama not responding")
    
    # Cost
    relay(f"ESTIMATED COST: ${get_cost_estimate():.2f}/hr")
    
    return {"gpu": gpu, "containers": containers.stdout.strip()}


def phase2_production(duration_seconds=1200):
    """Phase 2: Continuous production (Minute 5-25)."""
    relay("=== PHASE 2: AUTONOMOUS PRODUCTION QUEUE ===")
    
    start = time.time()
    tasks_completed = 0
    tokens_processed = 0
    
    production_tasks = [
        "Generate storyboard for 15-second micro-ad",
        "Write cinematographer JSON parameters",
        "Create image generation prompt set",
        "Compose background music prompt",
        "Generate voiceover narration script",
        "Design UI mockup description",
        "Write marketing copy variants",
        "Create product showcase animation plan",
    ]
    
    task_index = 0
    last_report = start
    
    while time.time() - start < duration_seconds:
        # Pick next task
        task = production_tasks[task_index % len(production_tasks)]
        task_index += 1
        
        # Execute via Think Box
        try:
            data = json.dumps({
                "type": "script-writer",
                "task": f"{task} - optimize for social media engagement and conversion"
            }).encode()
            
            req = urllib.request.Request(
                "http://localhost:9090/create", data=data,
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())
                output_len = len(str(result.get("result", "")))
                tokens_processed += output_len
                tasks_completed += 1
                
        except Exception as e:
            relay(f"Task failed: {e}")
        
        # Report every 5 minutes
        if time.time() - last_report >= 300:
            elapsed = time.time() - start
            relay(f"PROGRESS: {tasks_completed} tasks, {tokens_processed} chars, {elapsed:.0f}s elapsed")
            relay(f"GPU: {get_gpu_stats()}")
            last_report = time.time()
        
        # Small delay to prevent overload
        time.sleep(2)
    
    return {
        "tasks_completed": tasks_completed,
        "tokens_processed": tokens_processed,
        "duration": time.time() - start,
    }


def phase3_telemetry():
    """Phase 3: Compile metrics (Minute 25-30)."""
    relay("=== PHASE 3: TELEMETRY & CLEANUP ===")
    
    # Final stats
    gpu = get_gpu_stats()
    relay(f"FINAL GPU STATUS:\n{gpu}")
    
    # Database stats
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    stats = {}
    for table in ["think_tokens", "token_containers", "red_team_challenges", "swarm_votes"]:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cur.fetchone()[0]
        except:
            stats[table] = 0
    
    conn.close()
    
    relay(f"DATABASE STATS: {json.dumps(stats)}")
    
    # Output files
    outputs = subprocess.run(
        ["ls", "-la", "/opt/kudbee/outputs/"],
        capture_output=True, text=True, timeout=10
    )
    relay(f"OUTPUT FILES:\n{outputs.stdout[:500]}")
    
    # Cost summary
    relay(f"TOTAL ESTIMATED COST: ${get_cost_estimate() * 0.5:.2f} (30 min @ ${get_cost_estimate():.2f}/hr)")
    
    return stats


def commit_progress():
    """Commit progress to git."""
    try:
        subprocess.run(["git", "add", "-A"], capture_output=True, timeout=30)
        subprocess.run(
            ["git", "commit", "-m", f"sprint: {datetime.now().strftime('%H:%M')} progress checkpoint"],
            capture_output=True, timeout=30
        )
        subprocess.run(["git", "push"], capture_output=True, timeout=30)
        relay("GIT: Progress committed and pushed")
    except:
        relay("GIT: Commit failed (non-critical)")


def main():
    start_time = time.time()
    
    relay("=" * 60)
    relay("  KUDBEE 30-MINUTE AUTONOMOUS SPRINT")
    relay(f"  Started: {datetime.now(timezone.utc).isoformat()}")
    relay("=" * 60)
    
    # Phase 1: Audit
    audit = phase1_audit()
    commit_progress()
    
    # Phase 2: Production
    production = phase2_production(duration_seconds=1200)  # 20 minutes
    
    # Phase 3: Telemetry
    final_stats = phase3_telemetry()
    commit_progress()
    
    # Final report
    total_time = time.time() - start_time
    relay("=" * 60)
    relay("  SPRINT COMPLETE")
    relay(f"  Total time: {total_time:.0f}s")
    relay(f"  Tasks: {production['tasks_completed']}")
    relay(f"  Tokens: {production['tokens_processed']}")
    relay(f"  DB stats: {json.dumps(final_stats)}")
    relay("=" * 60)


if __name__ == "__main__":
    main()
