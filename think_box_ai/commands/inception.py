"""Inception API commands."""

from __future__ import annotations

import os

from ..ui.colors import bold, cyan, dim, green, yellow
from ..utils.output import is_json_mode, output_json


def handle_inception_command(args) -> None:
    sub = args.inception_command

    if sub == "run":
        _inception_run(args)
    elif sub == "models":
        _inception_models(args)
    elif sub == "usage":
        _inception_usage(args)
    else:
        print("Usage: thinkbox inception {run|models|usage}")


def _inception_run(args) -> None:
    api_key = os.environ.get("INCEPTION_API_KEY")
    if not api_key:
        print(yellow("  INCEPTION_API_KEY not set."))
        print(dim("  Set it with: export INCEPTION_API_KEY=your_key"))
        print(dim("  Note: Inception API does not work from cloud/AWS IPs due to CDN SNI reject."))
        return

    if is_json_mode():
        output_json({
            "model": args.model,
            "prompt": args.prompt[:100],
            "status": "simulated",
        })
        return

    print(bold("\n  Inception API — Mercury 2"))
    print(dim("  " + "─" * 40))
    print(f"  Model: {cyan(args.model)}")
    print(f"  Prompt: {args.prompt[:80]}")
    print(dim("\n  (Simulated — requires Inception API access from local machine)"))


def _inception_models(args) -> None:
    models = [
        {"id": "mercury-2", "name": "Mercury 2", "context": 128000, "type": "chat"},
        {"id": "mercury-2-mini", "name": "Mercury 2 Mini", "context": 64000, "type": "chat"},
    ]

    if is_json_mode():
        output_json(models)
        return

    print(bold("\n  Inception Models:"))
    print(dim("  " + "─" * 50))
    for m in models:
        mid = green(m["id"])
        mname = m["name"]
        mctx = m["context"]
        print(f"  {mid:20} {mname:20} ctx={mctx}")


def _inception_usage(args) -> None:
    usage = {
        "tokens_used": 0,
        "tokens_remaining": 1000000,
        "cost_usd": 0.0,
    }

    if is_json_mode():
        output_json(usage)
        return

    print(bold("\n  Inception Usage:"))
    print(dim("  " + "─" * 40))
    print(f"  Tokens used: {cyan(str(usage['tokens_used']))}")
    print(f"  Tokens remaining: {cyan(str(usage['tokens_remaining']))}")
    print(f"  Cost: ${usage['cost_usd']:.4f}")
