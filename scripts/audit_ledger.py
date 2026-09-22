#!/usr/bin/env python3
"""CLI for the docs/audit tracking filesystem (PR #125).

Hermetic-safe: all paths default to docs/audit under the repo root.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

Status = Literal["pass", "fail", "warn", "skip"]

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "docs" / "audit"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def resolve_root(explicit: str | None) -> Path:
    """Return audit root directory."""
    if explicit:
        return Path(explicit).resolve()
    return DEFAULT_ROOT.resolve()


def git_head_sha(repo_root: Path) -> str:
    """Best-effort HEAD SHA; empty string if git unavailable."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def path_changed_since_commit(repo_root: Path, rel_path: str, commit_sha: str) -> bool:
    """True if rel_path differs between commit_sha and HEAD."""
    if not commit_sha or not rel_path:
        return False
    full = repo_root / rel_path
    if not full.is_file():
        return True
    try:
        subprocess.check_call(
            ["git", "cat-file", "-e", f"{commit_sha}:{rel_path}"],
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return True
    try:
        out = subprocess.check_output(
            ["git", "diff", "--quiet", commit_sha, "HEAD", "--", rel_path],
            cwd=repo_root,
        )
        return False
    except subprocess.CalledProcessError:
        return True


def load_checked_area(root: Path, area: str) -> dict[str, Any]:
    path = root / "checked" / f"{area}.json"
    if not path.is_file():
        return {"area": area, "items": []}
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"invalid checked file: {path}")
    data.setdefault("area", area)
    data.setdefault("items", [])
    return data


def save_checked_area(root: Path, area: str, data: dict[str, Any]) -> Path:
    path = root / "checked" / f"{area}.json"
    _write_json(path, data)
    return path


def mark_checked(
    root: Path,
    area: str,
    rel_path: str,
    status: Status,
    *,
    commit_sha: str,
    checker: str,
    finding_ids: list[str],
    notes: str,
) -> dict[str, Any]:
    """Append or replace a checked item for area."""
    data = load_checked_area(root, area)
    items: list[dict[str, Any]] = list(data.get("items", []))
    entry = {
        "path": rel_path,
        "checked_at": _utc_now_iso(),
        "commit_sha": commit_sha,
        "checker": checker,
        "status": status,
        "finding_ids": finding_ids,
        "notes": notes,
    }
    replaced = False
    for idx, existing in enumerate(items):
        if existing.get("path") == rel_path:
            items[idx] = entry
            replaced = True
            break
    if not replaced:
        items.append(entry)
    data["items"] = items
    save_checked_area(root, area, data)
    return entry


def list_items(
    root: Path,
    area_filter: str | None = None,
    status_filter: Status | None = None,
) -> list[dict[str, Any]]:
    """Flatten checked items across areas."""
    checked_dir = root / "checked"
    if not checked_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(checked_dir.glob("*.json")):
        area = path.stem
        if area_filter and area != area_filter:
            continue
        data = _read_json(path)
        for item in data.get("items", []):
            if status_filter and item.get("status") != status_filter:
                continue
            row = dict(item)
            row["area"] = area
            rows.append(row)
    return rows


def stale_items(
    root: Path,
    repo_root: Path,
    head_sha: str | None = None,
) -> list[dict[str, Any]]:
    """Items whose commit_sha != HEAD or whose path changed since check."""
    head = head_sha or git_head_sha(repo_root)
    stale: list[dict[str, Any]] = []
    for row in list_items(root):
        commit = row.get("commit_sha", "")
        rel = row.get("path", "")
        reasons: list[str] = []
        if head and commit and commit != head:
            reasons.append("commit_sha_behind_head")
        if commit and path_changed_since_commit(repo_root, rel, commit):
            reasons.append("path_changed_since_check")
        if reasons:
            stale.append({**row, "stale_reasons": reasons})
    return stale


def load_latest_pass(root: Path) -> dict[str, Any] | None:
    index_path = root / "AUDIT_INDEX.json"
    if not index_path.is_file():
        return None
    index = _read_json(index_path)
    passes = index.get("passes") or []
    if not passes:
        return None
    pass_rel = passes[-1]
    pass_path = root / pass_rel if not str(pass_rel).startswith("/") else Path(pass_rel)
    if not pass_path.is_file():
        return None
    return _read_json(pass_path)


def cmd_list(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    rows = list_items(root, args.area, args.status)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for row in rows:
            print(
                f"{row.get('area')}\t{row.get('status')}\t{row.get('path')}\t"
                f"{row.get('commit_sha', '')[:12]}"
            )
    return 0


def cmd_mark_checked(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    repo_root = Path(args.repo_root).resolve()
    commit = args.commit or git_head_sha(repo_root)
    finding_ids = [p.strip() for p in (args.finding_ids or "").split(",") if p.strip()]
    entry = mark_checked(
        root,
        args.area,
        args.path,
        args.status,
        commit_sha=commit,
        checker=args.checker,
        finding_ids=finding_ids,
        notes=args.notes or "",
    )
    if args.json:
        print(json.dumps(entry, indent=2))
    else:
        print(f"marked {args.area}:{args.path} -> {args.status} @ {commit[:12]}")
    return 0


def cmd_stale(args: argparse.Namespace) -> int:
    root = resolve_root(args.root)
    repo_root = Path(args.repo_root).resolve()
    rows = stale_items(root, repo_root)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for row in rows:
            reasons = ",".join(row.get("stale_reasons", []))
            print(f"STALE\t{row.get('area')}\t{row.get('path')}\t{reasons}")
    return 1 if rows and args.fail_on_stale else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit ledger for docs/audit/")
    parser.add_argument("--root", help="Audit root (default: docs/audit)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List checked items")
    p_list.add_argument("--area", help="Filter by area name")
    p_list.add_argument("--status", choices=["pass", "fail", "warn", "skip"])
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_mark = sub.add_parser("mark-checked", help="Record a checked path in an area file")
    p_mark.add_argument("area", help="Area name (maps to checked/<area>.json)")
    p_mark.add_argument("path", help="Repository-relative path checked")
    p_mark.add_argument(
        "status",
        choices=["pass", "fail", "warn", "skip"],
        help="Check outcome",
    )
    p_mark.add_argument("--commit", help="commit_sha (default: git HEAD)")
    p_mark.add_argument("--checker", default="audit-ledger")
    p_mark.add_argument("--finding-ids", help="Comma-separated finding ids")
    p_mark.add_argument("--notes", default="")
    p_mark.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    p_mark.add_argument("--json", action="store_true")
    p_mark.set_defaults(func=cmd_mark_checked)

    p_stale = sub.add_parser("stale", help="List stale checked items vs HEAD")
    p_stale.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    p_stale.add_argument("--json", action="store_true")
    p_stale.add_argument(
        "--fail-on-stale",
        action="store_true",
        help="Exit 1 when any stale items exist",
    )
    p_stale.set_defaults(func=cmd_stale)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
