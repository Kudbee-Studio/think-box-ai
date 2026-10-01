"""Guards for the Markdown layout: every .md file is in a folder and is listed in docs/INDEX.md.

Fix for a failure here: run ``python3 scripts/generate_docs_index.py`` (and, for a new root-level file, move it into
``docs/`` first). See docs/INDEX.md, "Where Markdown lives, and why".
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_ALLOW_LIST = {"AGENTS.md", "CLAUDE.md", "README.md", "STATUS.md"}


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_docs_index", REPO_ROOT / "scripts" / "generate_docs_index.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _tracked_markdown() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "*.md"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError) as exc:  # not a git checkout (e.g. an exported tarball)
        raise unittest.SkipTest(f"git unavailable: {exc}") from exc
    return out


class DocsIndexTests(unittest.TestCase):
    def test_index_lists_every_tracked_markdown_file(self) -> None:
        _tracked_markdown()
        missing, extra = _load_generator().check()
        self.assertEqual(missing, [], "tracked Markdown files missing from docs/INDEX.md; run scripts/generate_docs_index.py")
        self.assertEqual(extra, [], "docs/INDEX.md lists files that are not tracked; run scripts/generate_docs_index.py")

    def test_only_the_allow_listed_markdown_files_sit_at_the_repo_root(self) -> None:
        root_files = {p for p in _tracked_markdown() if "/" not in p}
        self.assertEqual(
            root_files - ROOT_ALLOW_LIST,
            set(),
            f"Markdown files at the repo root must live in a docs/ folder (allowed at the root: {sorted(ROOT_ALLOW_LIST)})",
        )

    def test_every_link_in_the_index_resolves(self) -> None:
        _tracked_markdown()
        index = REPO_ROOT / "docs" / "INDEX.md"
        self.assertTrue(index.exists(), "docs/INDEX.md is missing")
        broken = []
        for target in re.findall(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)", index.read_text(encoding="utf-8")):
            if not (index.parent / target).resolve().exists():
                broken.append(target)
        self.assertEqual(broken, [], "docs/INDEX.md has links to files that do not exist")

    def test_moved_files_table_points_at_real_files(self) -> None:
        for old, new in _load_generator().MOVED:
            self.assertTrue((REPO_ROOT / new).exists(), f"{old} is listed as moved to {new}, which does not exist")
            self.assertFalse((REPO_ROOT / old).exists(), f"{old} is back at the repo root")


if __name__ == "__main__":
    unittest.main()
