"""Inception API commands (Mercury-2 via the OpenAI-compatible endpoint).

Every subcommand either makes a real API call or says plainly that it cannot.
Nothing here returns simulated or placeholder results.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request

from ..ui.colors import bold, cyan, dim, green, red, yellow
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


def _config(model: str | None = None):
    from thinkbox.model_client import ModelConfig

    return ModelConfig.from_env(api_type="inception", model=model)


def _require_key() -> None:
    if os.environ.get("INCEPTION_API_KEY", "").strip():
        return
    if is_json_mode():
        output_json({"ok": False, "error": "INCEPTION_API_KEY not set"})
    else:
        print(yellow("  INCEPTION_API_KEY not set."))
        print(dim("  Set it with: export INCEPTION_API_KEY=your_key"))
    sys.exit(1)


def _inception_run(args) -> None:
    from thinkbox.model_client import AsyncModelClient, ModelCallError

    _require_key()
    cfg = _config(args.model)
    t0 = time.monotonic()
    try:
        text = asyncio.run(AsyncModelClient(cfg).generate(args.prompt))
    except ModelCallError as exc:
        if is_json_mode():
            output_json({"ok": False, "model": cfg.model, "error": str(exc)})
        else:
            print(red(f"  Inception call failed: {exc}"))
        sys.exit(1)
    latency = round(time.monotonic() - t0, 3)

    if is_json_mode():
        output_json({"ok": True, "model": cfg.model, "latency_s": latency, "output": text})
        return
    print(bold("\n  Inception API — live"))
    print(dim("  " + "─" * 40))
    print(f"  Model:   {cyan(cfg.model)}  ({latency}s)")
    print(f"  Output:  {text}")


def _inception_models(args) -> None:
    _require_key()
    cfg = _config()
    req = urllib.request.Request(
        f"{cfg.base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {cfg.api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        if is_json_mode():
            output_json({"ok": False, "error": str(exc)})
        else:
            print(red(f"  Could not list models: {exc}"))
        sys.exit(1)
    models = [m.get("id", "") for m in data.get("data", [])]

    if is_json_mode():
        output_json({"ok": True, "models": models})
        return
    print(bold("\n  Inception models (live from /models):"))
    print(dim("  " + "─" * 50))
    for mid in models:
        print(f"  {green(mid)}")


def _inception_usage(args) -> None:
    message = "Usage is not available: this client has no Inception usage endpoint. Check the Inception dashboard."
    if is_json_mode():
        output_json({"ok": False, "available": False, "reason": message})
    else:
        print(yellow(f"  {message}"))
