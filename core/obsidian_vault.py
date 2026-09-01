#!/usr/bin/env python3
"""Obsidian-like memory system for Think Box AI.

Drop markdown files into memory directories and they become indexed knowledge.
Directory structure mirrors Obsidian vaults for compatibility.

Vault structure:
  memory/
    daily/        — Daily notes (YYYY-MM-DD.md)
    projects/     — Project-specific notes
    people/       — People/character notes
    concepts/     — Concept definitions
    inbox/        — Unprocessed drops (auto-indexed)
    templates/    — Note templates
    attachments/  — Images, files
"""

from __future__ import annotations

import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.cli_memory import memory

VAULT_PATH = Path("memory")


class ObsidianVault:
    """Obsidian-compatible memory vault."""

    def __init__(self, path: Path = VAULT_PATH):
        self.path = path
        self._init_structure()

    def _init_structure(self):
        """Create vault directory structure."""
        dirs = ["daily", "projects", "people", "concepts", "inbox", "templates", "attachments"]
        for d in dirs:
            (self.path / d).mkdir(parents=True, exist_ok=True)

    def drop_file(self, source: str, target_dir: str = "inbox") -> Path:
        """Drop a file into the vault. Returns the new path."""
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(f"Source not found: {source}")

        target = self.path / target_dir / source.name
        target.write_bytes(source.read_bytes())
        self.index_file(target, category=target_dir)
        return target

    def create_note(self, name: str, content: str, target_dir: str = "concepts", tags: list[str] | None = None) -> Path:
        """Create a new markdown note with frontmatter."""
        now = datetime.now(timezone.utc).isoformat()
        tag_str = ", ".join(tags) if tags else ""
        frontmatter = f"""---
created: {now}
tags: [{tag_str}]
---

# {name}

{content}
"""
        # Sanitize filename
        safe_name = re.sub(r'[^\w\-_\. ]', '_', name).replace(" ", "_").lower()
        file_path = self.path / target_dir / f"{safe_name}.md"
        file_path.write_text(frontmatter)
        self.index_file(file_path, category=target_dir)
        return file_path

    def index_file(self, file_path: Path, category: str = ""):
        """Index a markdown file into persistent memory."""
        content = file_path.read_text()

        # Extract frontmatter
        frontmatter = {}
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                fm_text = content[3:end].strip()
                for line in fm_text.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        frontmatter[k.strip()] = v.strip()

        # Extract tags from content
        tags = re.findall(r'#(\w+)', content)
        if "tags" in frontmatter:
            tags.extend([t.strip() for t in frontmatter["tags"].strip("[]").split(",")])

        # Extract headers as structure
        headers = re.findall(r'^#{1,6}\s+(.+)$', content, re.MULTILINE)
        header_text = " > ".join(headers[:5])

        # Store in memory
        key = f"note:{category}/{file_path.stem}" if category else f"note:{file_path.stem}"
        memory.remember(
            key=key,
            value={
                "path": str(file_path),
                "category": category,
                "title": headers[0] if headers else file_path.stem,
                "tags": list(set(tags)),
                "content_preview": content[:500],
                "word_count": len(content.split()),
                "last_modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
            },
            category="context",
            importance=1.0,
        )

        return key

    def reindex_all(self):
        """Re-index all files in the vault."""
        count = 0
        for md_file in self.path.rglob("*.md"):
            # Skip templates
            if "templates" in str(md_file):
                continue
            rel = md_file.relative_to(self.path)
            category = rel.parts[0] if len(rel.parts) > 1 else ""
            self.index_file(md_file, category)
            count += 1
        return count

    def search(self, query: str) -> list[dict]:
        """Search indexed notes."""
        results = memory.search(query, category="context")
        return results

    def get_daily_note(self, date: str | None = None) -> Path:
        """Get or create daily note."""
        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self.path / "daily" / f"{date}.md"
        if not path.exists():
            self.create_note(f"Daily Note {date}", f"# {date}\n\n## Tasks\n\n## Notes\n\n## Reflections\n\n", "daily")
        return path

    def list_notes(self, category: str | None = None) -> list[Path]:
        """List all notes, optionally filtered by category."""
        if category:
            d = self.path / category
            return list(d.glob("*.md")) if d.exists() else []
        return [f for f in self.path.rglob("*.md") if "templates" not in str(f)]

    def get_stats(self) -> dict:
        """Get vault statistics."""
        stats = {"total_notes": 0, "by_category": {}, "total_words": 0}
        for md_file in self.path.rglob("*.md"):
            if "templates" in str(md_file):
                continue
            rel = md_file.relative_to(self.path)
            cat = rel.parts[0] if len(rel.parts) > 1 else "root"
            word_count = len(md_file.read_text().split())
            stats["total_notes"] += 1
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
            stats["total_words"] += word_count
        return stats


# Global vault
vault = ObsidianVault()


if __name__ == "__main__":
    # Demo: create sample notes
    vault.create_note("Think Box AI", "Think Box AI is a control plane for Think Jobs.", "projects", ["ai", "project"])
    vault.create_note("Doginals", "Doginals are digital inscriptions on Dogecoin.", "concepts", ["crypto", "dogecoin"])
    vault.reindex_all()
    print(f"Vault stats: {vault.get_stats()}")
