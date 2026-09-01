#!/usr/bin/env python3
"""Think Box CLI v3 — Complete command-line interface."""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog="thinkbox", description="Think Box AI — v1.0.0")
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    subparsers = parser.add_subparsers(dest="command")

    # Global flags
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="JSON output")
    output.add_argument("--plain", action="store_true", help="Plain text")
    parser.add_argument("--quiet", "-q", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-color", action="store_true")

    # job
    job_p = subparsers.add_parser("job", help="Job management")
    job_sub = job_p.add_subparsers(dest="job_command")

    job_list = job_sub.add_parser("list", help="List jobs")
    job_list.add_argument("-s", "--state", choices=["queue", "active", "done", "blocked"])
    job_list.add_argument("--limit", type=int, default=50)

    job_show = job_sub.add_parser("show", help="Show job details")
    job_show.add_argument("job_id")

    job_submit = job_sub.add_parser("submit", help="Submit from template")
    job_submit.add_argument("template")
    job_submit.add_argument("args", nargs="*")

    job_create = job_sub.add_parser("create", help="Create job")
    job_create.add_argument("--intent", required=True)
    job_create.add_argument("--hat", default="researcher")
    job_create.add_argument("--file", help="JSON file with job data")

    job_run = job_sub.add_parser("run", help="Run queue worker")
    job_run.add_argument("--once", action="store_true")

    job_cancel = job_sub.add_parser("cancel", help="Cancel job")
    job_cancel.add_argument("job_id")

    job_retry = job_sub.add_parser("retry", help="Retry blocked/failed")
    job_retry.add_argument("job_id")

    job_diff = job_sub.add_parser("diff", help="Compare two jobs")
    job_diff.add_argument("id1")
    job_diff.add_argument("id2")

    # findings
    findings_p = subparsers.add_parser("findings", help="Findings browser")
    findings_sub = findings_p.add_subparsers(dest="findings_command")
    findings_sub.add_parser("list")
    findings_show = findings_sub.add_parser("show")
    findings_show.add_argument("name")
    findings_preview = findings_sub.add_parser("preview")
    findings_preview.add_argument("name")
    findings_export = findings_sub.add_parser("export")
    findings_export.add_argument("--output", "-o")

    # config
    config_p = subparsers.add_parser("config", help="Configuration")
    config_sub = config_p.add_subparsers(dest="config_command")
    config_sub.add_parser("show")
    config_set = config_sub.add_parser("set")
    config_set.add_argument("key")
    config_set.add_argument("value")
    config_profile = config_sub.add_parser("profile")
    config_profile.add_argument("name")

    # box
    box_p = subparsers.add_parser("box", help="Upstash box")
    box_sub = box_p.add_subparsers(dest="box_command")
    box_sub.add_parser("status")
    box_sub.add_parser("health")
    box_logs = box_sub.add_parser("logs")
    box_logs.add_argument("--follow", "-f", action="store_true")

    # memory
    mem_p = subparsers.add_parser("memory", help="Project memory")
    mem_sub = mem_p.add_subparsers(dest="memory_command")
    mem_search = mem_sub.add_parser("search")
    mem_search.add_argument("query")
    mem_search.add_argument("--limit", type=int, default=10)
    mem_show = mem_sub.add_parser("show")
    mem_show.add_argument("session_id")
    mem_list = mem_sub.add_parser("list")
    mem_remember = mem_sub.add_parser("remember")
    mem_remember.add_argument("key")
    mem_remember.add_argument("value")
    mem_forget = mem_sub.add_parser("forget")
    mem_forget.add_argument("key")
    mem_context = mem_sub.add_parser("context")

    # doctor
    subparsers.add_parser("doctor", help="System diagnostics")

    # init
    subparsers.add_parser("init", help="Initialize project")

    # watch
    watch_p = subparsers.add_parser("watch", help="Live monitoring")
    watch_p.add_argument("--interval", type=int, default=5)

    # serve
    serve_p = subparsers.add_parser("serve", help="Start backend")
    serve_p.add_argument("--host", default="0.0.0.0")
    serve_p.add_argument("--port", type=int, default=8000)

    # remote
    remote_p = subparsers.add_parser("remote", help="Remote connections")
    remote_sub = remote_p.add_subparsers(dest="remote_command")
    remote_add = remote_sub.add_parser("add")
    remote_add.add_argument("name")
    remote_add.add_argument("host")
    remote_add.add_argument("--port", type=int, default=22)
    remote_remove = remote_sub.add_parser("remove")
    remote_remove.add_argument("name")
    remote_sub.add_parser("list")
    remote_connect = remote_sub.add_parser("connect")
    remote_connect.add_argument("name", nargs="?")
    remote_discover = remote_sub.add_parser("discover")
    remote_discover.add_argument("--subnet", default="10.0.0")

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
