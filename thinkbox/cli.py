"""ThinkBox CLI — main entrypoint for the ThinkBox AI engine."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from thinkbox.engine import ThinkBoxEngine, EngineConfig
from thinkbox.model_client import ModelConfig


def cmd_run(args: argparse.Namespace) -> None:
    config = EngineConfig(
        model_config=ModelConfig(
            model=args.model or "llama3.1:8b",
            temperature=args.temperature or 0.1,
        ),
        speculative=not args.no_speculation,
    )
    engine = ThinkBoxEngine(config)

    print(f"ThinkBox Engine [{engine.engine_id}]")
    print(f"Goal: {args.goal}")
    print(f"Model: {config.model_config.model}")
    print(f"Speculative: {config.speculative}")
    print("-" * 50)

    async def run():
        result = await engine.execute_goal(args.goal)
        print("\n" + "=" * 50)
        print("Execution Complete")
        for key, value in result.items():
            print(f"  {key}: {value}")

    asyncio.run(run())


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn
    from backend.main import app

    print(f"ThinkBox Server starting on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


def cmd_benchmark(args: argparse.Namespace) -> None:
    config = EngineConfig(
        model_config=ModelConfig(
            model=args.model or "llama3.1:8b",
        ),
        speculative=True,
    )
    engine = ThinkBoxEngine(config)

    print(f"ThinkBox Benchmark [{engine.engine_id}]")
    print("-" * 50)

    async def run():
        goal = "Run a system benchmark: check CPU, memory, and disk usage"
        result = await engine.execute_goal(goal)
        print("\nBenchmark Results:")
        for key, value in result.items():
            print(f"  {key}: {value}")

        stats = engine.get_stats()
        print("\nEngine Stats:")
        print(f"  Events: {stats['events_processed']}")
        print(f"  Workers: {stats['autoscaler']['current_workers']}")

    asyncio.run(run())


def main() -> None:
    parser = argparse.ArgumentParser(prog="thinkbox", description="ThinkBox AI Engine")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Execute a goal")
    run_parser.add_argument("--goal", required=True, help="Goal string to execute")
    run_parser.add_argument("--model", default="llama3.1:8b", help="Model name")
    run_parser.add_argument("--temperature", type=float, default=0.1, help="Temperature")
    run_parser.add_argument("--no-speculation", action="store_true", help="Disable speculative execution")

    serve_parser = subparsers.add_parser("serve", help="Run the API server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port")

    bench_parser = subparsers.add_parser("benchmark", help="Run benchmark")
    bench_parser.add_argument("--model", default="llama3.1:8b", help="Model name")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
