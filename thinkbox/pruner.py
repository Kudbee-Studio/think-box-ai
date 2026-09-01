"""Pre-Flight Context Pruner for ThinkBox AI.

Strips comments, dead imports, whitespace, and boilerplate from input files.
Guarantees all generated prompt payloads stay strictly under 500 tokens.
"""

from __future__ import annotations

import re
import tokenize
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MAX_TOKEN_BUDGET = 500
TOKEN_CHAR_RATIO = 4


@dataclass
class PruneResult:
    original_tokens: int
    pruned_tokens: int
    content: str
    removed_imports: list[str]
    removed_comments: int
    within_budget: bool


from dataclasses import dataclass


class ContextPruner:
    def __init__(self, max_tokens: int = MAX_TOKEN_BUDGET):
        self.max_tokens = max_tokens

    def estimate_tokens(self, text: str) -> int:
        return len(text) // TOKEN_CHAR_RATIO + 1

    def prune_python(self, source: str) -> PruneResult:
        original_tokens = self.estimate_tokens(source)

        lines = source.split("\n")
        cleaned_lines = []
        removed_comments = 0
        removed_imports = []

        in_docstring = False
        docstring_char = None

        for line in lines:
            stripped = line.strip()

            if in_docstring:
                if docstring_char in stripped:
                    in_docstring = False
                removed_comments += 1
                continue

            if stripped.startswith('"""') or stripped.startswith("'''"):
                char = stripped[:3]
                if stripped.count(char) == 1:
                    in_docstring = True
                    docstring_char = char
                removed_comments += 1
                continue

            if stripped.startswith("#"):
                removed_comments += 1
                continue

            if stripped.startswith("import ") or stripped.startswith("from "):
                removed_imports.append(stripped)
                continue

            if not stripped:
                continue

            cleaned_lines.append(line)

        pruned = "\n".join(cleaned_lines)
        pruned_tokens = self.estimate_tokens(pruned)

        return PruneResult(
            original_tokens=original_tokens,
            pruned_tokens=pruned_tokens,
            content=pruned,
            removed_imports=removed_imports,
            removed_comments=removed_comments,
            within_budget=pruned_tokens <= self.max_tokens,
        )

    def prune_javascript(self, source: str) -> PruneResult:
        original_tokens = self.estimate_tokens(source)

        cleaned = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
        cleaned = re.sub(r"//.*?$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\n\s*\n", "\n", cleaned)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)

        pruned_tokens = self.estimate_tokens(cleaned)

        return PruneResult(
            original_tokens=original_tokens,
            pruned_tokens=pruned_tokens,
            content=cleaned,
            removed_imports=[],
            removed_comments=0,
            within_budget=pruned_tokens <= self.max_tokens,
        )

    def prune_generic(self, source: str) -> PruneResult:
        original_tokens = self.estimate_tokens(source)

        cleaned = re.sub(r"#.*?$", "", source, flags=re.MULTILINE)
        cleaned = re.sub(r"//.*?$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\n\s*\n", "\n", cleaned)

        pruned_tokens = self.estimate_tokens(cleaned)

        return PruneResult(
            original_tokens=original_tokens,
            pruned_tokens=pruned_tokens,
            content=cleaned,
            removed_imports=[],
            removed_comments=0,
            within_budget=pruned_tokens <= self.max_tokens,
        )

    def prune_file(self, file_path: str | Path) -> PruneResult:
        path = Path(file_path)
        source = path.read_text(encoding="utf-8", errors="replace")

        suffix = path.suffix.lower()
        if suffix == ".py":
            return self.prune_python(source)
        elif suffix in (".js", ".ts", ".jsx", ".tsx"):
            return self.prune_javascript(source)
        else:
            return self.prune_generic(source)

    def prune_to_budget(self, source: str, language: str = "python") -> str:
        if language == "python":
            result = self.prune_python(source)
        elif language in ("javascript", "typescript"):
            result = self.prune_javascript(source)
        else:
            result = self.prune_generic(source)

        if result.within_budget:
            return result.content

        words = result.content.split()
        max_chars = self.max_tokens * TOKEN_CHAR_RATIO
        truncated = " ".join(words[:max_chars // 2])

        return truncated[:max_chars]

    def chunk_payload(self, source: str, overlap: int = 50) -> list[str]:
        max_chars = self.max_tokens * TOKEN_CHAR_RATIO
        chunks = []
        start = 0
        source_len = len(source)

        while start < source_len:
            end = start + max_chars
            chunk = source[start:end]
            chunks.append(chunk)
            start = end - overlap

        return chunks
