#!/usr/bin/env python3
"""Think Box CLI v4 — Full integration with Cursor, Memory, Inception, and GPU Queue."""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add core to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.cli_memory import memory
from core.config import config
from core.foundation.logging import get_logger, setup_logging

setup_logging(os.environ.get("THINKBOX_LOG_LEVEL", "INFO"))
logger = get_logger("cli")


def main():
    parser = argparse.ArgumentParser(
        prog="thinkbox",
        description="Think Box AI — v1.0.0 | Cursor + Memory + Inception + GPU Queue",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")

    # Global flags
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="JSON output")
    output.add_argument("--plain", action="store_true", help="Plain text")
    parser.add_argument("--quiet", "-q", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-color", action="store_true")

    subparsers = parser.add_subparsers(dest="command")

    # ==========================================
    # JOB COMMANDS
    # ==========================================
    job_p = subparsers.add_parser("job", help="Job management")
    job_sub = job_p.add_subparsers(dest="job_command")

    job_list = job_sub.add_parser("list", help="List all jobs")
    job_list.add_argument("-s", "--state", choices=["queue", "active", "done", "blocked"])
    job_list.add_argument("--limit", type=int, default=50)

    job_show = job_sub.add_parser("show", help="Show job details")
    job_show.add_argument("job_id")

    job_create = job_sub.add_parser("create", help="Create a job")
    job_create.add_argument("--intent", required=True)
    job_create.add_argument("--hat", default="researcher", choices=["researcher", "runner", "director", "camera", "jury"])
    job_create.add_argument("--file", help="JSON file with job data")

    job_submit = job_sub.add_parser("submit", help="Submit from template")
    job_submit.add_argument("template")
    job_submit.add_argument("args", nargs="*")

    job_run = job_sub.add_parser("run", help="Run queue worker")
    job_run.add_argument("--dry-run", action="store_true")

    job_cancel = job_sub.add_parser("cancel", help="Cancel a queued job")
    job_cancel.add_argument("job_id")

    job_retry = job_sub.add_parser("retry", help="Retry a blocked/failed job")
    job_retry.add_argument("job_id")

    job_diff = job_sub.add_parser("diff", help="Compare two jobs")
    job_diff.add_argument("id1")
    job_diff.add_argument("id2")

    # ==========================================
    # MEMORY COMMANDS
    # ==========================================
    mem_p = subparsers.add_parser("memory", help="Project memory")
    mem_sub = mem_p.add_subparsers(dest="memory_command")

    mem_remember = mem_sub.add_parser("remember", help="Store a memory")
    mem_remember.add_argument("key")
    mem_remember.add_argument("value")
    mem_remember.add_argument("--category", default="fact", choices=["command", "preference", "fact", "result", "context"])
    mem_remember.add_argument("--importance", type=float, default=1.0)

    mem_recall = mem_sub.add_parser("recall", help="Recall a memory")
    mem_recall.add_argument("key")

    mem_search = mem_sub.add_parser("search", help="Search memories")
    mem_search.add_argument("query")
    mem_search.add_argument("--category", choices=["command", "preference", "fact", "result", "context"])
    mem_search.add_argument("--limit", type=int, default=10)

    mem_context = mem_sub.add_parser("context", help="Get current context")
    mem_context.add_argument("--limit", type=int, default=20)

    mem_list = mem_sub.add_parser("list", help="List all memories")
    mem_list.add_argument("--category", choices=["command", "preference", "fact", "result", "context"])

    mem_forget = mem_sub.add_parser("forget", help="Delete a memory")
    mem_forget.add_argument("key")

    # ==========================================
    # CURSOR COMMANDS
    # ==========================================
    cursor_p = subparsers.add_parser("cursor", help="Cursor SDK integration")
    cursor_sub = cursor_p.add_subparsers(dest="cursor_command")

    cursor_run = cursor_sub.add_parser("run", help="Run Cursor agent")
    cursor_run.add_argument("prompt")
    cursor_run.add_argument("--runtime", default="local", choices=["local", "cloud"])
    cursor_run.add_argument("--model", default="composer-2.5")
    cursor_run.add_argument("--repo", help="Git repo URL (cloud mode)")

    cursor_list = cursor_sub.add_parser("list", help="List Cursor agents")
    cursor_list.add_argument("--runtime", default="local", choices=["local", "cloud", "all"])

    cursor_logs = cursor_sub.add_parser("logs", help="Get agent logs")
    cursor_logs.add_argument("agent_id")

    # ==========================================
    # INCEPTION COMMANDS
    # ==========================================
    inception_p = subparsers.add_parser("inception", help="Inception API (Mercury 2)")
    inception_sub = inception_p.add_subparsers(dest="inception_command")

    inception_run = inception_sub.add_parser("run", help="Run Mercury 2 prompt")
    inception_run.add_argument("prompt")
    inception_run.add_argument("--model", default="mercury-2")

    inception_models = inception_sub.add_parser("models", help="List available models")

    inception_usage = inception_sub.add_parser("usage", help="Show usage stats")

    # ==========================================
    # QUEUE COMMANDS
    # ==========================================
    queue_p = subparsers.add_parser("queue", help="GPU job queue")
    queue_sub = queue_p.add_subparsers(dest="queue_command")

    queue_status = queue_sub.add_parser("status", help="Queue status")

    queue_add = queue_sub.add_parser("add", help="Add job to GPU queue")
    queue_add.add_argument("--intent", required=True)
    queue_add.add_argument("--priority", default="normal", choices=["urgent", "normal", "low"])

    queue_batch = queue_sub.add_parser("batch", help="Batch submit jobs")
    queue_batch.add_argument("--file", required=True, help="JSON file with jobs")

    queue_drain = queue_sub.add_parser("drain", help="Drain queue (when GPU starts)")

    # ==========================================
    # SPAWN COMMANDS
    # ==========================================
    spawn_p = subparsers.add_parser("spawn", help="Spawn sub-agents")
    spawn_sub = spawn_p.add_subparsers(dest="spawn_command")

    spawn_researcher = spawn_sub.add_parser("researcher", help="Spawn researcher agent")
    spawn_researcher.add_argument("goal")
    spawn_researcher.add_argument("--wait", action="store_true")

    spawn_runner = spawn_sub.add_parser("runner", help="Spawn runner agent")
    spawn_runner.add_argument("goal")

    # ==========================================
    # CONFIG COMMANDS
    # ==========================================
    config_p = subparsers.add_parser("config", help="Configuration")
    config_sub = config_p.add_subparsers(dest="config_command")

    config_sub.add_parser("show", help="Show config")

    config_set = config_sub.add_parser("set", help="Set config value")
    config_set.add_argument("key")
    config_set.add_argument("value")

    config_profile = config_sub.add_parser("profile", help="Load profile")
    config_profile.add_argument("name")

    # ==========================================
    # FINDINGS COMMANDS
    # ==========================================
    findings_p = subparsers.add_parser("findings", help="Findings browser")
    findings_sub = findings_p.add_subparsers(dest="findings_command")

    findings_sub.add_parser("list", help="List findings")

    findings_show = findings_sub.add_parser("show")
    findings_show.add_argument("name")

    findings_preview = findings_sub.add_parser("preview")
    findings_preview.add_argument("name")

    # ==========================================
    # OTHER COMMANDS
    # ==========================================
    subparsers.add_parser("doctor", help="System diagnostics")
    subparsers.add_parser("init", help="Initialize project")

    watch_p = subparsers.add_parser("watch", help="Live monitoring")
    watch_p.add_argument("--interval", type=int, default=5)

    serve_p = subparsers.add_parser("serve", help="Start backend")
    serve_p.add_argument("--host", default="0.0.0.0")
    serve_p.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
