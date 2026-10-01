#!/usr/bin/env python3
"""Generate docs/INDEX.md: a directory of every tracked Markdown file.

    python3 scripts/generate_docs_index.py           # rewrite docs/INDEX.md
    python3 scripts/generate_docs_index.py --check   # exit 1 if a file is missing from / extra in docs/INDEX.md

The index is derived from ``git ls-files '*.md'`` (titles from each file's first heading), so it cannot drift from
the tree. Copies under ``.kilo/worktrees/`` are excluded. Run it whenever a Markdown file is added, moved or renamed.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = REPO_ROOT / "docs" / "INDEX.md"
EXCLUDED_PREFIXES = (".kilo/",)
ROOT_ALLOW_LIST = ("AGENTS.md", "CLAUDE.md", "README.md", "STATUS.md")

# (section title, predicate on the repo-relative path). First match wins; leftovers go to "Other".
SECTIONS: list[tuple[str, "callable"]] = [
    ("Start here (repository root)", lambda p: "/" not in p),
    ("Decisions (ADRs)", lambda p: p.startswith("docs/decisions/")),
    ("Enterprise Agent OS plan", lambda p: p.startswith("docs/enterprise/")),
    ("Guides", lambda p: p.startswith("docs/guides/")),
    ("Runbooks", lambda p: p.startswith("docs/runbooks/")),
    ("Roadmaps, status and continuity", lambda p: p.startswith("docs/roadmaps/") or p in {
        "docs/roadmap.md", "docs/STATUS.md", "docs/PREP.md", "docs/CONTINUITY.md", "docs/known-defects.md"}),
    ("Security and incidents", lambda p: p.startswith("docs/incidents/") or p.startswith("docs/SECURITY")),
    ("Project policies", lambda p: p == "docs/CONTRIBUTING.md"),
    ("Architecture, plans and deployment", lambda p: p.startswith(("docs/architecture/", "docs/plans/", "docs/deployment/"))
        or p in {"docs/architecture-v1.md", "docs/project-foundation.md"}),
    ("Audits and reviews", lambda p: p.startswith(("docs/audit/", "docs/audits/", "docs/RED/"))),
    ("Research and strategy", lambda p: p.startswith(("docs/research/", "docs/strategy/"))),
    ("Archive", lambda p: p.startswith("docs/archive/")),
    ("Other documents in docs/", lambda p: p.startswith("docs/")),
    ("Agent definitions", lambda p: p.startswith(("agents/", ".agents/"))),
    ("Evidence and data documents", lambda p: p.startswith("data/")),
    ("Tests and examples", lambda p: p.startswith(("tests/", "examples/"))),
]

MOVED = [
    ("CI_TEST.md", "docs/archive/CI_TEST.md"),
    ("CONTRIBUTING.md", "docs/CONTRIBUTING.md"),
    ("DEPLOYMENT.md", "docs/deployment/DEPLOYMENT.md"),
    ("FEATURE1_PHASE2_INTEGRATION.md", "docs/plans/FEATURE1_PHASE2_INTEGRATION.md"),
    ("FORCE_PUSH_READY.md", "docs/incidents/FORCE_PUSH_READY.md"),
    ("INCIDENT_RESPONSE_2026-09-28.md", "docs/incidents/INCIDENT_RESPONSE_2026-09-28.md"),
    ("KUDBEE_AGENT_RUNTIME_CONTRACT.md", "docs/architecture/KUDBEE_AGENT_RUNTIME_CONTRACT.md"),
    ("PHASE9_INDEX.md", "docs/archive/PHASE9_INDEX.md"),
    ("RESEARCH.md", "docs/research/RESEARCH.md"),
    ("ROADMAP.md", "docs/roadmaps/ROADMAP.md"),
    ("SECURITY.md", "docs/SECURITY.md"),
    ("TEST_SYNC.md", "docs/archive/TEST_SYNC.md"),
    ("THINK_TOKEN_STRATEGY.md", "docs/strategy/THINK_TOKEN_STRATEGY.md"),
]

SKIP_LINE = re.compile(
    r"^(\*\*(Date|Status|Last|Generated|Project|Author|Session|Agent|Priority|Scope|Technology|Goal|As of|Canonical)[^*]*\*\*|"
    r"---+|```|\||!\[|<|\[!\[)",
    re.IGNORECASE,
)


# Descriptions never quote host addresses or identifiers.
NETWORK_ID = re.compile(r"\b\d{1,3}(\.\d{1,3}){3}\b|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-", re.IGNORECASE)


def tracked_markdown() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    rel = [p for p in out if not p.startswith(EXCLUDED_PREFIXES) and p != "docs/INDEX.md"]
    return sorted(set(rel), key=str.lower)


def clean(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_]{1,3}", "", text)
    return re.sub(r"\s+", " ", text).strip()


def describe(rel: str) -> tuple[str, str]:
    title, about = Path(rel).name, ""
    try:
        lines = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace").splitlines()[:80]
    except OSError:
        return title, about
    seen_title = not any(re.match(r"#\s+\S", ln.strip()) for ln in lines)
    for line in lines:
        stripped = line.strip()
        if not seen_title:
            m = re.match(r"#\s+(.+)", stripped)
            if m:
                title, seen_title = clean(m.group(1)), True
            continue
        body = re.sub(r"^>\s*", "", stripped).strip()
        if not body or body.startswith("#") or SKIP_LINE.match(body) or NETWORK_ID.search(body):
            continue
        body = clean(body)
        if len(body) >= 20:
            about = body if len(body) <= 120 else body[:117].rsplit(" ", 1)[0] + "..."
            break
    return title.replace("|", "\\|"), about.replace("|", "\\|")


def link(rel: str) -> str:
    target = os.path.relpath(REPO_ROOT / rel, REPO_ROOT / "docs").replace(os.sep, "/")
    return f"[{rel}]({target})"


def build() -> str:
    files = tracked_markdown()
    grouped: dict[str, list[str]] = {name: [] for name, _ in SECTIONS}
    grouped["Other"] = []
    for rel in files:
        for name, pred in SECTIONS:
            if pred(rel):
                grouped[name].append(rel)
                break
        else:
            grouped["Other"].append(rel)

    out = [
        "# Documentation index",
        "",
        f"Every tracked Markdown file in this repository, by area ({len(files)} files). "
        "**Generated** by `python3 scripts/generate_docs_index.py`; do not edit by hand. "
        "A test fails when this page is stale, so run the script whenever you add, move or rename a `.md` file.",
        "",
        "## Where Markdown lives, and why",
        "",
        "- **Repository root keeps four files on purpose:** `README.md` (GitHub renders it), `CLAUDE.md` and `AGENTS.md` "
        "(Claude Code and other agents load them by path; AGENTS.md section 4.3 names the rules), and `STATUS.md` "
        "(named in AGENTS.md section 4.3 and section 13.1; `docs/STATUS.md` also exists, so it cannot move there). "
        "A test fails if any other `.md` file appears at the root.",
        "- **Everything else lives in a folder.** Most documents are under `docs/`.",
        "- **Left where they are because code or tooling reads them there:** `agents/` and `.agents/` (agent definitions), "
        "`data/` (evidence and proof documents that gates and docs cite), `tests/` and `examples/` (fixtures).",
        "- **Not listed:** copies under `.kilo/worktrees/` (working-tree duplicates).",
        "",
        "## Moved files",
        "",
        "These files used to sit at the repository root. Older notes and chronicle entries may still mention the old path; "
        "the file names did not change.",
        "",
        "| Old path | New path |",
        "|---|---|",
    ]
    for old, new in MOVED:
        out.append(f"| `{old}` | [`{new}`]({os.path.relpath(REPO_ROOT / new, REPO_ROOT / 'docs').replace(os.sep, '/')}) |")
    out += ["", "## Contents", ""]
    names = [n for n, _ in SECTIONS] + ["Other"]
    for name in names:
        if grouped[name]:
            anchor = re.sub(r"[^a-z0-9 -]", "", name.lower()).replace(" ", "-")
            out.append(f"- [{name}](#{anchor}) ({len(grouped[name])})")
    for name in names:
        if not grouped[name]:
            continue
        out += ["", f"## {name}", "", "| File | Title | About |", "|---|---|---|"]
        for rel in grouped[name]:
            title, about = describe(rel)
            out.append(f"| {link(rel)} | {title} | {about} |")
    return "\n".join(out) + "\n"


def listed_files() -> set[str]:
    """Repo-relative paths listed in the index's per-section tables (not the "Moved files" table)."""
    if not INDEX_PATH.exists():
        return set()
    text = INDEX_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"^\| \[([^\]]+\.md)\]\(", text.split("\n## Contents", 1)[-1], re.MULTILINE))


def check() -> tuple[list[str], list[str]]:
    """(tracked files missing from the index, listed files that are no longer tracked).

    Only the set of files is compared, not titles or descriptions, so editing a document's first paragraph never
    makes the index "stale"; adding, moving or deleting a file does.
    """
    tracked, listed = set(tracked_markdown()), listed_files()
    return sorted(tracked - listed), sorted(listed - tracked)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if docs/INDEX.md is stale instead of rewriting it")
    args = parser.parse_args()
    if args.check:
        missing, extra = check()
        if missing or extra:
            for rel in missing:
                print(f"not in docs/INDEX.md: {rel}", file=sys.stderr)
            for rel in extra:
                print(f"listed in docs/INDEX.md but not tracked: {rel}", file=sys.stderr)
            print("docs/INDEX.md is stale. Run: python3 scripts/generate_docs_index.py", file=sys.stderr)
            return 1
        print("docs/INDEX.md lists every tracked Markdown file")
        return 0
    fresh = build()
    INDEX_PATH.write_text(fresh, encoding="utf-8")
    print(f"wrote {INDEX_PATH.relative_to(REPO_ROOT)} ({fresh.count(chr(10))} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
