"""Path safety / sandbox allowlists (PR #180 F19)."""

from __future__ import annotations

from pathlib import Path

from thinkbox.cli_phase3.errors import sandbox_error
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


def resolve_sandbox_path(
    relative: str,
    allowed_roots: tuple[str, ...],
    repo_root: Path | None = None,
) -> Path:
    root = repo_root if repo_root is not None else REPO_ROOT
    rel = relative.strip().replace("\\", "/")
    if rel.startswith("/") or ".." in rel.split("/"):
        raise sandbox_error("path escapes sandbox", path=relative)
    for prefix in allowed_roots:
        candidate = (root / prefix / rel).resolve()
        base = (root / prefix).resolve()
        try:
            candidate.relative_to(base)
        except ValueError:
            continue
        return candidate
    raise sandbox_error("path not under allowlist", path=relative, roots=allowed_roots)
