#!/usr/bin/env python3
"""List or delete merged remote cursor/* branches (founder-safe, dry-run default).

Never deletes protected branches. Never force-pushes main. Requires explicit
``--execute`` to delete remotes; default is dry-run only.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PROTECTED_BRANCHES: frozenset[str] = frozenset(
    {
        "main",
        "master",
        "develop",
        "development",
        "release",
        "production",
    }
)

DEFAULT_PREFIXES: tuple[str, ...] = ("cursor/", "convoy/")


def _run_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout


def list_remote_branches(prefixes: tuple[str, ...]) -> list[str]:
    """Return remote branch short names matching any prefix."""
    out = _run_git(["branch", "-r", "--format=%(refname:short)"])
    names: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.endswith("/HEAD"):
            continue
        if line.startswith("origin/"):
            short = line[len("origin/") :]
        else:
            short = line
        if any(short.startswith(p) for p in prefixes):
            names.append(short)
    return sorted(set(names))


def is_merged_into_main(branch: str) -> bool:
    """True when origin/branch is an ancestor of origin/main."""
    try:
        _run_git(["merge-base", "--is-ancestor", f"origin/{branch}", "origin/main"])
        return True
    except RuntimeError:
        return False


def filter_deletable(branches: list[str]) -> tuple[list[str], list[str]]:
    safe: list[str] = []
    skipped: list[str] = []
    for branch in branches:
        top = branch.split("/")[0]
        if branch in PROTECTED_BRANCHES or top in PROTECTED_BRANCHES:
            skipped.append(branch)
            continue
        if not is_merged_into_main(branch):
            skipped.append(branch)
            continue
        safe.append(branch)
    return safe, skipped


def delete_remote(branch: str, execute: bool) -> None:
    ref = f"origin/{branch}"
    if not execute:
        print(f"dry-run: would delete remote {ref}")
        return
    _run_git(["push", "origin", "--delete", branch])
    print(f"deleted remote {ref}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete merged branches (default: dry-run)",
    )
    parser.add_argument(
        "--prefix",
        action="append",
        default=list(DEFAULT_PREFIXES),
        help="Remote branch prefix to consider (repeatable)",
    )
    args = parser.parse_args(argv)
    prefixes = tuple(args.prefix)
    try:
        candidates = list_remote_branches(prefixes)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    deletable, skipped = filter_deletable(candidates)
    print(f"candidates={len(candidates)} deletable={len(deletable)} skipped={len(skipped)}")
    for branch in deletable:
        delete_remote(branch, execute=args.execute)
    if skipped:
        print("skipped (protected or not merged into origin/main):")
        for branch in skipped[:50]:
            print(f"  - {branch}")
        if len(skipped) > 50:
            print(f"  ... and {len(skipped) - 50} more")
    if not args.execute:
        print("dry-run complete — pass --execute to delete remotes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
