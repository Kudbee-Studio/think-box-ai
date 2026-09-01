"""System diagnostics command."""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, red, yellow

CHECKS = [
    ("core", "Core package"),
    ("core.indexing.database", "Database module"),
    ("core.indexing.search", "Search engine"),
    ("core.indexing.memory", "Memory module"),
    ("core.tools.registry", "Tool registry"),
    ("core.providers.base", "Provider base"),
    ("core.runtime.agent", "Agent runtime"),
    ("backend.main", "Backend (FastAPI)"),
]


def handle_doctor(args) -> None:
    print(bold("\n  Think Box AI — System Diagnostics"))
    print(dim("  " + "─" * 50))

    _check_environment()
    _check_modules()
    _check_directories()
    _check_connectivity()
    _check_gpu_queue()
    _check_jobs()

    print(bold("\n  Doctor complete."))


def _check_environment() -> None:
    print(f"\n  {bold('Environment:')}")
    print(f"    Python: {cyan(sys.version.split()[0])}")
    print(f"    Platform: {cyan(sys.platform)}")
    print(f"    CWD: {cyan(str(Path.cwd()))}")


def _check_modules() -> None:
    print(f"\n  {bold('Modules:')}")
    for module_path, label in CHECKS:
        try:
            importlib.import_module(module_path)
            print(f"    {green('✓')} {label}")
        except ImportError as e:
            print(f"    {red('✗')} {label} — {dim(str(e)[:50])}")


def _check_directories() -> None:
    print(f"\n  {bold('Directories:')}")
    dirs = ["data", "data/jobs", "data/findings", "data/raw", "data/fixtures", "backend", "core"]
    for d in dirs:
        path = Path(d)
        if path.exists():
            count = len(list(path.iterdir())) if path.is_dir() else 0
            print(f"    {green('✓')} {d}/ ({count} items)")
        else:
            print(f"    {yellow('⚠')} {d}/ (missing)")


def _check_connectivity() -> None:
    print(f"\n  {bold('Connectivity:')}")
    import urllib.request
    import urllib.error

    hosts = [
        ("https://api.github.com", "GitHub API"),
        ("https://httpbin.org/get", "HTTPBin"),
    ]
    for url, label in hosts:
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "thinkbox-doctor/1.0")
            urllib.request.urlopen(req, timeout=5)
            print(f"    {green('✓')} {label}")
        except Exception as e:
            print(f"    {yellow('⚠')} {label} — {dim(str(e)[:40])}")


def _check_gpu_queue() -> None:
    print(f"\n  {bold('GPU Queue:')}")
    queue_file = Path("data/gpu_queue.jsonl")
    if queue_file.exists():
        lines = [l for l in queue_file.read_text().strip().split("\n") if l.strip()]
        print(f"    Queue file: {green('exists')} ({len(lines)} jobs)")
    else:
        print(f"    Queue file: {dim('not created yet')}")


def _check_jobs() -> None:
    print(f"\n  {bold('Jobs:')}")
    jobs_dir = Path("data/jobs")
    if jobs_dir.exists():
        jobs = list(jobs_dir.glob("*.json"))
        print(f"    Total jobs: {cyan(str(len(jobs)))}")
    else:
        print(f"    Jobs dir: {dim('not created yet')}")
