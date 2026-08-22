"""Mayor Boot Runtime — session initialization / continuity layer.

This is the canonical boot mechanism for every Mayor Cloud Agent session.
It replaces the repeated "giant discovery checklist" with a single call:

    from core.mayor.boot import mayor_boot
    state = mayor_boot()

or, from the CLI, the `/mayor-boot` command (see .kilo/command/mayor-boot.md).

The contract of this layer is strict:

1. Memory (`memory/`) and decisions (`docs/decisions/`) are the FIRST source
   of continuity. They are read before any repository-wide discovery.
2. It performs MINIMUM necessary recovery. It does NOT re-read the entire
   repository. It reports what is recorded, then reports what is missing.
3. It is design-only with respect to the execution substrate. It does NOT
   implement Upstash, QStash, Box runtime, or ADR-003 protocols. Those are
   downstream chunks.
4. It returns a structured `MayorBootState` so the calling session can verify
   claims against the live repository rather than trusting history blindly.

Historical claims recovered from prior Mayor sessions are treated as
UNVERIFIED until checked against the live repo (see `verify()`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.foundation.logging import get_logger

logger = get_logger(__name__)


DEFAULT_MEMORY_DIR = Path("memory")
DEFAULT_DECISIONS_DIR = Path("docs") / "decisions"


@dataclass
class DecisionRecord:
    """A recovered architecture decision record (ADR)."""

    adr_id: str
    path: Path
    title: str = ""
    status: str = "unknown"
    summary: str = ""
    raw_lines: int = 0


@dataclass
class MemoryFile:
    """A recovered persistent memory file."""

    name: str
    path: Path
    verified_facts: list[str] = field(default_factory=list)
    raw_lines: int = 0


@dataclass
class MayorBootState:
    """Result of a Mayor boot. The single continuity object for a session."""

    project_root: Path
    boot_timestamp: str = ""
    memory_files: list[MemoryFile] = field(default_factory=list)
    decisions: list[DecisionRecord] = field(default_factory=list)
    recovered_claims: list[str] = field(default_factory=list)
    missing_expected: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_action: str = ""

    def to_briefing(self) -> str:
        """Render a concise briefing string for the calling session."""
        lines: list[str] = []
        lines.append("=== MAYOR BOOT BRIEFING ===")
        lines.append(f"project_root: {self.project_root}")
        lines.append(f"memory files: {len(self.memory_files)}")
        for m in self.memory_files:
            lines.append(
                f"  - {m.name} ({m.raw_lines} lines, {len(m.verified_facts)} verified facts)"
            )
        lines.append(f"decisions (ADRs): {len(self.decisions)}")
        for d in self.decisions:
            lines.append(f"  - {d.adr_id}: {d.title} [{d.status}]")
        if self.recovered_claims:
            lines.append("recovered claims (UNVERIFIED):")
            for c in self.recovered_claims:
                lines.append(f"  - {c}")
        if self.missing_expected:
            lines.append("MISSING (expected but not found):")
            for m in self.missing_expected:
                lines.append(f"  - {m}")
        if self.warnings:
            lines.append("warnings:")
            for w in self.warnings:
                lines.append(f"  - {w}")
        lines.append(f"next_action: {self.next_action}")
        return "\n".join(lines)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_front_matterish(path: Path, max_bytes: int = 4000) -> str:
    """Read the head of a file for title/status extraction without loading all."""
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return data[:max_bytes]


def _extract_adr_meta(path: Path) -> DecisionRecord:
    """Best-effort extraction of ADR id/title/status from a markdown file."""
    adr_id = path.stem
    text = _read_front_matterish(path)
    title = ""
    status = "unknown"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ADR") or stripped.startswith("# "):
            title = stripped.lstrip("#").strip()
        if stripped.lower().startswith("**status**"):
            status = stripped.split(":", 1)[-1].strip().strip("*").strip()
    return DecisionRecord(
        adr_id=adr_id,
        path=path,
        title=title,
        status=status,
        raw_lines=len(text.splitlines()),
    )


def _extract_memory_facts(path: Path) -> MemoryFile:
    """Extract VERIFIED-### fact labels from an organizational memory file."""
    name = path.name
    text = path.read_text(encoding="utf-8", errors="replace")
    facts: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## VERIFIED-"):
            facts.append(stripped.lstrip("#").strip())
    return MemoryFile(
        name=name,
        path=path,
        verified_facts=facts,
        raw_lines=len(text.splitlines()),
    )


def mayor_boot(
    project_root: Path | str | None = None,
    memory_dir: Path | str | None = None,
    decisions_dir: Path | str | None = None,
    verify_live: bool = False,
) -> MayorBootState:
    """Boot the Mayor session from recorded state.

    Args:
        project_root: Project root. Defaults to cwd.
        memory_dir: Override location of persistent memory files.
        decisions_dir: Override location of ADR files.
        verify_live: If True, perform light live-repo sanity checks
            (existence of core/, docs/) and append to warnings when
            recorded state diverges. Kept cheap on purpose.

    Returns:
        MayorBootState — the continuity object for this session.
    """
    root = Path(project_root) if project_root else Path.cwd()
    mem_dir = Path(memory_dir) if memory_dir else (root / DEFAULT_MEMORY_DIR)
    dec_dir = Path(decisions_dir) if decisions_dir else (root / DEFAULT_DECISIONS_DIR)

    state = MayorBootState(project_root=root, boot_timestamp=_now_iso())

    # 1. Memory first.
    if mem_dir.is_dir():
        for p in sorted(mem_dir.glob("*.md")):
            state.memory_files.append(_extract_memory_facts(p))
    else:
        state.missing_expected.append(str(mem_dir))

    # 2. Decisions (ADRs) next.
    if dec_dir.is_dir():
        for p in sorted(dec_dir.glob("*.md")):
            state.decisions.append(_extract_adr_meta(p))
    else:
        state.missing_expected.append(str(dec_dir))

    # 3. Recovered claims — explicit historical context, marked UNVERIFIED.
    state.recovered_claims = [
        "Mayor boot previously hit an output/reasoning limit; chunk large missions.",
        "ADR-001: Upstash Box accepted as execution-substrate design direction (design-only).",
        "ADR-002: six-phase architecture design exists (~1,405 lines).",
        "Conflicts: 3 competing runtimes, 2 tool systems, memory not shared correctly.",
        "Missing provider abstractions: VectorProvider, SecretProvider (per ADR-002).",
        "Kilo = bootstrap/provisioning only; never the permanent worker brain.",
        "LLM = provider-agnostic / BYOK.",
    ]

    # 4. Light live verification (cheap, bounded).
    if verify_live:
        for expected in ("core", "docs", "memory"):
            if not (root / expected).exists():
                state.warnings.append(f"expected dir missing in live repo: {expected}")
        adr_ids = {d.adr_id for d in state.decisions}
        if "002-architecture-design" not in adr_ids:
            state.warnings.append("recovered claim references ADR-002 but file not found")

    # 5. Next action: do NOT auto-implement. Point at the next chunk.
    state.next_action = (
        "Verify recovered claims against live repo if needed; then proceed to the "
        "next chunked mission (Mayor Boot Runtime hardening or ADR-003 protocols). "
        "Do NOT re-read the entire repository."
    )

    logger.info(
        "Mayor boot complete",
        extra={
            "memory_files": len(state.memory_files),
            "decisions": len(state.decisions),
            "missing": len(state.missing_expected),
            "warnings": len(state.warnings),
        },
    )
    return state


def boot_to_json(state: MayorBootState) -> str:
    """Serialize a boot state to JSON for hand-off / logging."""

    def _default(o: Any) -> Any:
        if isinstance(o, Path):
            return str(o)
        return str(o)

    payload = {
        "project_root": str(state.project_root),
        "boot_timestamp": state.boot_timestamp,
        "memory_files": [
            {
                "name": m.name,
                "path": str(m.path),
                "verified_facts": m.verified_facts,
            }
            for m in state.memory_files
        ],
        "decisions": [
            {"adr_id": d.adr_id, "title": d.title, "status": d.status}
            for d in state.decisions
        ],
        "recovered_claims": state.recovered_claims,
        "missing_expected": state.missing_expected,
        "warnings": state.warnings,
        "next_action": state.next_action,
    }
    return json.dumps(payload, indent=2, default=_default)
