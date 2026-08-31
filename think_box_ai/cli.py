"""Command-line interface for Think Box AI."""

from __future__ import annotations

import argparse
import sys

from think_box_ai import __version__
from think_box_ai.commands import box, config, findings, job, watch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thinkbox",
        description="Think Box AI — Think Job control plane",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Global output flags
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    output.add_argument("--plain", action="store_true", help="Unformatted text output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress non-essential output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Increase verbosity")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    subparsers = parser.add_subparsers(dest="command")

    # job
    job_parser = subparsers.add_parser("job", help="Job management")
    job_sub = job_parser.add_subparsers(dest="job_command")

    job_list = job_sub.add_parser("list", help="List all jobs")
    job_list.add_argument("-s", "--state", help="Filter by state")
    job_list.set_defaults(func=lambda a: job.list_jobs(a.state))

    job_show = job_sub.add_parser("show", help="Show job details")
    job_show.add_argument("job_id", help="Job ID")
    job_show.set_defaults(func=lambda a: job.show_job(a.job_id))

    job_sub.add_parser("queue", help="Show queue contents").set_defaults(func=lambda a: job.show_queue())

    job_submit = job_sub.add_parser("submit", help="Submit a job from template")
    job_submit.add_argument("template", nargs="?", help="Template name")
    job_submit.add_argument("args", nargs="*", help="Key=value inputs")
    job_submit.set_defaults(func=lambda a: job.submit_job(a.template, a.args) if a.template else job.submit_wizard())

    job_diff = job_sub.add_parser("diff", help="Compare two jobs")
    job_diff.add_argument("id1", help="First job ID")
    job_diff.add_argument("id2", help="Second job ID")
    job_diff.set_defaults(func=lambda a: job.diff_jobs(a.id1, a.id2))

    job_run = job_sub.add_parser("run", help="Run queue worker")
    job_run.set_defaults(func=lambda a: print("Worker: python3 scripts/run_job.py"))

    # findings
    findings_parser = subparsers.add_parser("findings", help="Findings browser")
    findings_sub = findings_parser.add_subparsers(dest="findings_command")

    findings_sub.add_parser("list", help="List findings").set_defaults(func=lambda a: findings.list_findings())

    findings_show = findings_sub.add_parser("show", help="Show finding")
    findings_show.add_argument("name", help="Finding name or partial match")
    findings_show.set_defaults(func=lambda a: findings.show_finding(a.name))

    # config
    config_parser = subparsers.add_parser("config", help="Configuration")
    config_sub = config_parser.add_subparsers(dest="config_command")

    config_sub.add_parser("show", help="Show config").set_defaults(func=lambda a: config.show_config())

    config_set = config_sub.add_parser("set", help="Set config value")
    config_set.add_argument("key", help="Config key (provider, model)")
    config_set.add_argument("value", help="Config value")
    config_set.set_defaults(func=lambda a: config.set_config(a.key, a.value))

    # box
    box_parser = subparsers.add_parser("box", help="Upstash box")
    box_sub = box_parser.add_subparsers(dest="box_command")

    box_sub.add_parser("status", help="Box status").set_defaults(func=lambda a: box.box_status())
    box_sub.add_parser("health", help="Backend health").set_defaults(func=lambda a: box.box_health())

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start backend")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.set_defaults(func=lambda a: print("Use: python3 -m uvicorn backend.main:app"))

    # watch
    watch_parser = subparsers.add_parser("watch", help="Live job monitoring")
    watch_parser.add_argument("--interval", type=int, default=5, help="Refresh interval")
    watch_parser.set_defaults(func=lambda a: watch.watch(a.interval))

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
