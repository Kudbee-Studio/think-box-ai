"""Command-line interface for Think Box AI."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from think_box_ai import __version__
from think_box_ai.token import SYMBOL


def _cmd_harness(args: argparse.Namespace) -> int:
    from core.foundation.logging import setup_logging
    from core.runtime.harness import HarnessConfig, HarnessRunner, docker_available

    setup_logging(os.environ.get("THINKBOX_LOG_LEVEL", "INFO"))

    if not docker_available():
        print("ERROR: Docker is not available. Start Docker or set HARNESS=0.", file=sys.stderr)
        return 1

    runner = HarnessRunner(HarnessConfig())

    if args.harness_action == "run":
        return _harness_run(args, runner)
    if args.harness_action == "status":
        return _harness_status(runner)
    if args.harness_action == "stop":
        return _harness_stop(args, runner)
    print(f"Unknown harness action: {args.harness_action}", file=sys.stderr)
    return 1


def _harness_run(args: argparse.Namespace, runner: HarnessRunner) -> int:
    token = args.token
    cmd = args.cmd
    if not token or not cmd:
        print("ERROR: --token and --cmd are required", file=sys.stderr)
        return 1
    container = runner.start_container(agent_id=token)
    print(f"STARTED {container.container_name} {container.container_id}")
    result = asyncio.run(
        runner.exec_in_container(container.container_id, ["sh", "-c", cmd], timeout=args.timeout)
    )
    print(f"STDOUT: {result.get('stdout', '').strip()}")
    print(f"STDERR: {result.get('stderr', '').strip()}")
    print(f"RC: {result.get('return_code', -1)}")
    return 0 if result.get("success") else 1


def _harness_status(runner: HarnessRunner) -> int:
    containers = runner.list_containers()
    if not containers:
        print("No active harness containers.")
        return 0
    for c in containers:
        print(f"{c.container_name} {c.container_id} network={c.network_mode}")
    return 0


def _harness_stop(args: argparse.Namespace, runner: HarnessRunner) -> int:
    token = args.token
    if not token:
        print("ERROR: --token is required", file=sys.stderr)
        return 1
    targets = [c for c in runner.list_containers() if c.container_name.startswith(f"ku3bee-{token}-")]
    if not targets:
        print(f"No containers found for token: {token}")
        return 1
    for c in targets:
        runner.stop_container(c.container_id)
        print(f"STOPPED {c.container_name} {c.container_id}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="think-box-ai",
        description="Think Box AI — Think Token CLI",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("info", help="Show token info").set_defaults(func=_cmd_info)

    harness_parser = subparsers.add_parser("harness", help="Docker execution harness")
    harness_sub = harness_parser.add_subparsers(dest="harness_action", required=True)

    run_parser = harness_sub.add_parser("run", help="Run a command in a sandbox container")
    run_parser.add_argument("--token", required=True, help="Session token (used in container name)")
    run_parser.add_argument("--cmd", required=True, help="Command to execute")
    run_parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds")

    harness_sub.add_parser("status", help="List active harness containers")

    stop_parser = harness_sub.add_parser("stop", help="Stop container(s) for a token")
    stop_parser.add_argument("--token", required=True, help="Session token to stop")

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    elif hasattr(args, "harness_action"):
        _cmd_harness(args)
    else:
        parser.print_help()


def _cmd_info(args: argparse.Namespace) -> None:
    print(f"Token symbol : {SYMBOL}")
    print(f"Version      : {__version__}")


if __name__ == "__main__":
    main()
