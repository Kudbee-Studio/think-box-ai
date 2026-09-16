#!/usr/bin/env python3
"""Agent work-template runner.

Makes an agent work template *executable* instead of advisory:

    python3 scripts/agent_work.py list
    python3 scripts/agent_work.py check   --template dashboard-evolution [--branch <name>]
    python3 scripts/agent_work.py verify  --template dashboard-evolution
    python3 scripts/agent_work.py report  --template dashboard-evolution

`check`   validates branch naming and runs the template baseline.
`verify`  runs the verification commands and an in-process dashboard E2E.
`report`  prints the machine-checkable part of the final report.

The template registry below mirrors
``docs/agent-templates/<template>/contract.yaml``; a test asserts the two stay in
sync so the human-readable and machine-executable contracts cannot drift.
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Registry (mirrors the YAML contracts)
# ---------------------------------------------------------------------------

@dataclass
class Template:
    name: str
    domain: str
    branch_pattern: str
    accepted_prefixes: list[str]
    baseline: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)
    e2e_routes: list[str] = field(default_factory=list)
    contract_path: str = ""


TEMPLATES: dict[str, Template] = {
    "dashboard-evolution": Template(
        name="dashboard-evolution",
        domain="dashboard",
        branch_pattern=r"^agent/[a-z0-9-]+/[a-z0-9-]+-\d{8}$",
        accepted_prefixes=[
            "agent/dashboard-evolution/",
            "agent/dashboard-command-center/",
        ],
        baseline=[
            "python3 -m unittest discover tests/",
            "python3 experiments/verify_instrumentation.py",
        ],
        verification=[
            "python3 -m unittest discover tests/",
            "python3 experiments/verify_instrumentation.py --live",
        ],
        e2e_routes=[
            "/healthz",
            "/api/live",
            "/api/strength",
            "/api/instruments",
            "/api/proof",
            "/api/sessions",
        ],
        contract_path="docs/agent-templates/dashboard-evolution/AGENT_CONTRACT.md",
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: str, timeout: int = 600) -> tuple[int, str]:
    """Run a shell command from the repo root; returns (returncode, tail)."""
    try:
        p = subprocess.run(cmd, shell=True, cwd=str(ROOT), capture_output=True,
                           text=True, timeout=timeout)
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {cmd}"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _current_branch() -> str:
    rc, out = _run("git branch --show-current", timeout=30)
    return out.strip() if rc == 0 else ""


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

def cmd_check(tpl: Template, branch: str | None) -> int:
    branch = branch or _current_branch()
    print(f"template   : {tpl.name} ({tpl.domain})")
    print(f"branch     : {branch or '(detached)'}")

    ok = True
    if not branch:
        print("  FAIL  could not determine the current branch")
        ok = False
    elif branch in ("main", "master"):
        print("  FAIL  never work directly on main")
        ok = False
    elif not re.match(tpl.branch_pattern, branch):
        print(f"  FAIL  branch does not match {tpl.branch_pattern}")
        print(f"        accepted prefixes: {tpl.accepted_prefixes}")
        ok = False
    elif not any(branch.startswith(p) for p in tpl.accepted_prefixes):
        print(f"  FAIL  branch must start with one of {tpl.accepted_prefixes}")
        ok = False
    else:
        print("  PASS  branch naming compliant")

    print("\nbaseline:")
    for cmd in tpl.baseline:
        rc, tail = _run(cmd)
        status = "PASS" if rc == 0 else "FAIL"
        if rc != 0:
            ok = False
        summary = tail.splitlines()[-1] if tail.splitlines() else ""
        print(f"  {status}  {cmd}")
        if summary:
            print(f"        {summary}")

    print(f"\ncheck: {'OK' if ok else 'NOT OK'}")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

def _dashboard_e2e(tpl: Template) -> tuple[bool, list[str]]:
    """Start the dashboard in-process on a free port and hit every route."""
    sys.path.insert(0, str(ROOT))
    try:
        import importlib
        mod = importlib.import_module("experiments.swarm_dashboard")
    except Exception as e:  # noqa: BLE001
        return False, [f"import failed: {type(e).__name__}: {e}"]

    from http.server import ThreadingHTTPServer

    port = _free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", port), mod.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.4)

    lines: list[str] = []
    ok = True
    try:
        for route in tpl.e2e_routes:
            url = f"http://127.0.0.1:{port}{route}"
            try:
                with urllib.request.urlopen(url, timeout=10) as r:
                    body = r.read()
                    status = r.status
                    ctype = r.headers.get("Content-Type", "")
                    if status != 200:
                        ok = False
                        lines.append(f"  FAIL  {route} → HTTP {status}")
                        continue
                    if "json" in ctype:
                        try:
                            json.loads(body or b"{}")
                        except json.JSONDecodeError as e:
                            ok = False
                            lines.append(f"  FAIL  {route} → invalid JSON ({e})")
                            continue
                    lines.append(f"  PASS  {route} → {status} ({len(body)} bytes)")
            except urllib.error.HTTPError as e:
                ok = False
                lines.append(f"  FAIL  {route} → HTTP {e.code}")
            except Exception as e:  # noqa: BLE001
                ok = False
                lines.append(f"  FAIL  {route} → {type(e).__name__}: {e}")
    finally:
        srv.shutdown()
        srv.server_close()
    return ok, lines


def cmd_verify(tpl: Template) -> int:
    ok = True
    print("verification:")
    for cmd in tpl.verification:
        rc, tail = _run(cmd)
        status = "PASS" if rc == 0 else "FAIL"
        if rc != 0:
            ok = False
        print(f"  {status}  {cmd}")
        if tail:
            print(f"        {tail.splitlines()[-1]}")

    print("\ndashboard E2E (in-process):")
    e2e_ok, lines = _dashboard_e2e(tpl)
    for line in lines:
        print(line)
    ok = ok and e2e_ok

    print(f"\nverify: {'OK' if ok else 'NOT OK'}")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def cmd_report(tpl: Template) -> int:
    rc, tests = _run("python3 -m unittest discover tests/ 2>&1 | tail -3")
    _, branch = _run("git branch --show-current", timeout=30)
    _, sha = _run("git rev-parse --short HEAD", timeout=30)
    print("AGENT WORK REPORT")
    print("=" * 60)
    print(f"template        : {tpl.name}")
    print(f"branch          : {branch.strip()}")
    print(f"head            : {sha.strip()}")
    print(f"tests           : {tests.splitlines()[-1] if tests.splitlines() else 'n/a'}")
    print()
    print("fill in before merge:")
    for field_name in (
        "pr_number_url", "merge_commit", "final_main_sha", "commits", "test_counts",
        "verification_results", "dashboard_e2e_result", "capabilities_implemented",
        "known_limitations", "verification_commands", "live_dashboard_url",
        "next_larger_improvement",
    ):
        print(f"  - {field_name}:")
    return 0


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["list", "check", "verify", "report"])
    ap.add_argument("--template", default="dashboard-evolution")
    ap.add_argument("--branch", default=None)
    args = ap.parse_args()

    if args.action == "list":
        for name, t in TEMPLATES.items():
            print(f"{name:24s} {t.domain:12s} {t.branch_pattern}")
        return 0

    tpl = TEMPLATES.get(args.template)
    if not tpl:
        print(f"unknown template: {args.template}")
        return 2

    if args.action == "check":
        return cmd_check(tpl, args.branch)
    if args.action == "verify":
        return cmd_verify(tpl)
    return cmd_report(tpl)


if __name__ == "__main__":
    sys.exit(main())
