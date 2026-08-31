"""Command-line interface for Think Box AI."""

from __future__ import annotations

import argparse
import sys

from think_box_ai import __version__
from think_box_ai.commands import box, config, findings, job, serve


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="thinkbox",
        description="Think Box AI — Think Job control plane",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    # job
    job_parser = subparsers.add_parser("job", help="Job management")
    job_sub = job_parser.add_subparsers(dest="job_command")

    job_sub.add_parser("list", help="List all jobs").set_defaults(func=lambda _: job.list_jobs())
    job_sub.add_parser("queue", help="Show queue contents").set_defaults(func=lambda _: job.show_queue())

    show_parser = job_sub.add_parser("show", help="Show job details")
    show_parser.add_argument("job_id", help="Job ID")
    show_parser.set_defaults(func=lambda args: job.show_job(args.job_id))

    submit_parser = job_sub.add_parser("submit", help="Submit a job from template")
    submit_parser.add_argument("template", help="Template name (without 'template_' prefix)")
    submit_parser.set_defaults(func=lambda args: job.submit_job(args.template))

    job_sub.add_parser("run", help="Run queue worker").set_defaults(func=lambda _: print("Use: python3 scripts/run_job.py"))

    # findings
    findings_parser = subparsers.add_parser("findings", help="Findings browser")
    findings_sub = findings_parser.add_subparsers(dest="findings_command")

    findings_sub.add_parser("list", help="List findings").set_defaults(func=lambda _: findings.list_findings())

    show_finding_parser = findings_sub.add_parser("show", help="Show finding")
    show_finding_parser.add_argument("name", help="Finding name or partial match")
    show_finding_parser.set_defaults(func=lambda args: findings.show_finding(args.name))

    # config
    config_parser = subparsers.add_parser("config", help="Configuration")
    config_sub = config_parser.add_subparsers(dest="config_command")

    config_sub.add_parser("show", help="Show config").set_defaults(func=lambda _: config.show_config())

    set_parser = config_sub.add_parser("set", help="Set provider")
    set_parser.add_argument("provider", help="Provider name")
    set_parser.set_defaults(func=lambda args: config.set_provider(args.provider))

    # box
    box_parser = subparsers.add_parser("box", help="Upstash box")
    box_sub = box_parser.add_subparsers(dest="box_command")

    box_sub.add_parser("status", help="Box status").set_defaults(func=lambda _: box.box_status())
    box_sub.add_parser("health", help="Backend health").set_defaults(func=lambda _: box.box_health())

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start backend")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.set_defaults(func=lambda args: serve.serve(args.host, args.port))

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
