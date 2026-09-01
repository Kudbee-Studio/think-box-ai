#!/usr/bin/env python3
"""Handoff skill for Think Box AI.

Bootstraps new agents with full project context.
Run: python3 skills/handoff/handoff.py [status|bootstrap|queue|memory|verify]
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def get_git_info() -> dict:
    """Get current git state."""
    try:
        branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=REPO_ROOT).stdout.strip()
        last_commit = subprocess.run(["git", "log", "-1", "--oneline"], capture_output=True, text=True, cwd=REPO_ROOT).stdout.strip()
        ahead = subprocess.run(["git", "rev-list", "--count", f"origin/{branch}...{branch}"], capture_output=True, text=True, cwd=REPO_ROOT).stdout.strip()
        return {"branch": branch, "last_commit": last_commit, "commits_ahead": ahead}
    except Exception:
        return {"branch": "unknown", "last_commit": "unknown", "commits_ahead": "?"}


def get_job_counts() -> dict:
    """Count jobs by state."""
    counts = {"queue": 0, "active": 0, "done": 0, "blocked": 0}
    jobs_dir = REPO_ROOT / "jobs"
    for state in counts:
        d = jobs_dir / state
        if d.exists():
            counts[state] = len(list(d.glob("job_*.json")))
    return counts


def get_memory_stats() -> dict:
    """Get memory database stats."""
    db_path = REPO_ROOT / "data" / "thinkbox_memory.db"
    if not db_path.exists():
        return {"exists": False, "entries": 0}
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0]
    conn.close()
    return {"exists": True, "entries": count, "path": str(db_path)}


def get_frontend_pages() -> list[str]:
    """List all frontend pages."""
    public_dir = REPO_ROOT / "public"
    if not public_dir.exists():
        return []
    pages = []
    for f in sorted(public_dir.rglob("*.html")):
        rel = f.relative_to(public_dir)
        pages.append(str(rel))
    return pages


def get_tool_count() -> int:
    """Count registered tools."""
    tools_dir = REPO_ROOT / "core" / "tools"
    if not tools_dir.exists():
        return 0
    return len([f for f in tools_dir.glob("*.py") if f.name != "__init__.py"])


def get_test_count() -> int:
    """Count test files."""
    tests_dir = REPO_ROOT / "tests"
    if not tests_dir.exists():
        return 0
    return len(list(tests_dir.rglob("test_*.py")))


def cmd_status():
    """Show current project state."""
    git = get_git_info()
    jobs = get_job_counts()
    memory = get_memory_stats()
    pages = get_frontend_pages()
    tools = get_tool_count()
    tests = get_test_count()

    print("=" * 60)
    print("THINK BOX AI — Project Status")
    print("=" * 60)
    print(f"Branch: {git['branch']}")
    print(f"Last commit: {git['last_commit']}")
    print(f"Commits ahead: {git['commits_ahead']}")
    print()
    print("Jobs:")
    for state, count in jobs.items():
        print(f"  {state}: {count}")
    print(f"  Total: {sum(jobs.values())}")
    print()
    print(f"Frontend pages: {len(pages)}")
    print(f"Tools: {tools}")
    print(f"Tests: {tests}")
    print(f"Memory entries: {memory.get('entries', 0)}")
    print("=" * 60)


def cmd_bootstrap():
    """Full bootstrap for new agent."""
    print("=" * 60)
    print("THINK BOX AI — Agent Bootstrap")
    print("=" * 60)
    print()

    # Git info
    git = get_git_info()
    print(f"[GIT] Branch: {git['branch']}")
    print(f"[GIT] Last commit: {git['last_commit']}")
    print(f"[GIT] Commits ahead of origin: {git['commits_ahead']}")
    print()

    # Jobs
    jobs = get_job_counts()
    print(f"[JOBS] Queue: {jobs['queue']} | Active: {jobs['active']} | Done: {jobs['done']} | Blocked: {jobs['blocked']}")
    print()

    # Memory
    memory = get_memory_stats()
    print(f"[MEMORY] Entries: {memory.get('entries', 0)}")
    print()

    # Frontend
    pages = get_frontend_pages()
    print(f"[FRONTEND] {len(pages)} pages:")
    for p in pages[:10]:
        print(f"  - {p}")
    if len(pages) > 10:
        print(f"  ... and {len(pages) - 10} more")
    print()

    # Environment
    env_vars = ["CURSOR_API_KEY", "INCEPTION_API_KEY", "UPSTASH_BOX_API_KEY", "THINKBOX_UPCLOUD_API_TOKEN"]
    print("[ENV]")
    for var in env_vars:
        val = os.environ.get(var, "")
        status = "SET" if val else "MISSING"
        print(f"  {var}: {status}")
    print()

    # Blocked
    print("[BLOCKED]")
    print("  GPU stopped (Kudbee must start)")
    print("  SSH blocked (firewall drop-all)")
    print("  No LLM on box")
    print("  Wallet APIs not public")
    print()

    # Next actions
    print("[NEXT ACTIONS]")
    print("  1. Read STATUS.md, MEMORY.md, SESSION.md")
    print("  2. Read WORK_QUEUE.md for priority items")
    print("  3. Check BEST_PRACTICES.md for rules")
    print("  4. Pick up from 'In Progress' items")
    print()

    print("=" * 60)
    print("Bootstrap complete. Read the docs and get to work.")
    print("=" * 60)


def cmd_queue():
    """Show GPU queue status."""
    queue_file = REPO_ROOT / "data" / "gpu_queue.jsonl"
    if not queue_file.exists():
        print("No GPU queue file found.")
        return

    jobs = []
    with open(queue_file) as f:
        for line in f:
            jobs.append(json.loads(line.strip()))

    queued = [j for j in jobs if j["status"] == "queued"]
    completed = [j for j in jobs if j["status"] == "completed"]

    print("=" * 60)
    print("GPU Queue Status")
    print("=" * 60)
    print(f"Queued: {len(queued)}")
    print(f"Completed: {len(completed)}")
    if queued:
        total_cost = sum(j.get("cost_estimate", 0) for j in queued)
        total_time = sum(j.get("gpu_time_estimate", 0) for j in queued)
        print(f"Estimated cost: ${total_cost:.2f}")
        print(f"Estimated GPU time: {total_time:.1f} minutes")
        print()
        print("Top queued jobs:")
        for j in sorted(queued, key=lambda x: x.get("priority_val", 1))[:5]:
            print(f"  [{j['priority']}] {j['id']}: {j['intent'][:50]}")
    print("=" * 60)


def cmd_memory():
    """Show memory system status."""
    print("=" * 60)
    print("Memory System Status")
    print("=" * 60)

    # Agents memory
    db_path = REPO_ROOT / "data" / "thinkbox_memory.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0]
        layers = dict(conn.execute("SELECT layer, COUNT(*) FROM memory_entries GROUP BY layer").fetchall())
        print(f"[AGENTS MEMORY] {count} entries")
        for layer, c in layers.items():
            print(f"  {layer}: {c}")
        conn.close()
    else:
        print("[AGENTS MEMORY] Not initialized")

    # CLI memory
    cli_db = REPO_ROOT / "data" / "cli_memory.db"
    if cli_db.exists():
        conn = sqlite3.connect(str(cli_db))
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        print(f"[CLI MEMORY] {count} entries")
        conn.close()
    else:
        print("[CLI MEMORY] Not initialized")

    # Obsidian vault
    vault_path = REPO_ROOT / "memory"
    if vault_path.exists():
        notes = list(vault_path.rglob("*.md"))
        print(f"[OBSIDIAN VAULT] {len(notes)} notes")
    else:
        print("[OBSIDIAN VAULT] Not initialized")

    print("=" * 60)


def cmd_verify():
    """Run verification checks."""
    print("=" * 60)
    print("Verification Checks")
    print("=" * 60)

    checks = []

    # 1. Git secrets
    try:
        result = subprocess.run(
            ["git", "log", "-p", "--all"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        has_secrets = bool(result.stdout and (
            "sk-" in result.stdout or
            "gsk_" in result.stdout or
            "password" in result.stdout.lower()
        ))
        checks.append(("Git secrets scan", "PASS" if not has_secrets else "FAIL"))
    except Exception:
        checks.append(("Git secrets scan", "SKIP"))

    # 2. Job JSON validity
    jobs_dir = REPO_ROOT / "jobs"
    invalid = 0
    total = 0
    for state_dir in ["queue", "active", "done", "blocked"]:
        d = jobs_dir / state_dir
        if d.exists():
            for jf in d.glob("job_*.json"):
                total += 1
                try:
                    json.loads(jf.read_text())
                except json.JSONDecodeError:
                    invalid += 1
    checks.append(("Job JSON validity", "PASS" if invalid == 0 else f"FAIL ({invalid}/{total})"))

    # 3. Frontend pages have meta tags
    public_dir = REPO_ROOT / "public"
    missing_meta = 0
    if public_dir.exists():
        for html in public_dir.rglob("*.html"):
            content = html.read_text()
            if "og:title" not in content or "description" not in content:
                missing_meta += 1
    checks.append(("Frontend SEO", "PASS" if missing_meta == 0 else f"FAIL ({missing_meta} pages)"))

    # 4. Memory DB exists
    checks.append(("Memory DB", "PASS" if (REPO_ROOT / "data" / "thinkbox_memory.db").exists() else "FAIL"))

    # 5. Tests exist
    tests_dir = REPO_ROOT / "tests"
    test_count = len(list(tests_dir.rglob("test_*.py"))) if tests_dir.exists() else 0
    checks.append(("Tests", "PASS" if test_count > 0 else f"SKIP ({test_count} files)"))

    for name, status in checks:
        icon = "✓" if status == "PASS" else "✗" if status == "FAIL" else "○"
        print(f"  {icon} {name}: {status}")

    print("=" * 60)


def main():
    if len(sys.argv) < 2:
        cmd_bootstrap()
        return

    cmd = sys.argv[1]
    commands = {
        "status": cmd_status,
        "bootstrap": cmd_bootstrap,
        "queue": cmd_queue,
        "memory": cmd_memory,
        "verify": cmd_verify,
    }

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"Unknown command: {cmd}")
        print(f"Available: {', '.join(commands.keys())}")


if __name__ == "__main__":
    main()
