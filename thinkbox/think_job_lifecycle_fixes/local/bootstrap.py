"""Repository root and import path bootstrap for local runs."""

from __future__ import annotations

import sys
from pathlib import Path

from thinkbox.kilo_live_proof_readiness import REPO_ROOT


def ensure_repo_on_path(repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else REPO_ROOT
    root_str = str(root.resolve())
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root
