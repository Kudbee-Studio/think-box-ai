"""Exit-code contract for Phase 4 CLI commands (PR #196 F05)."""

from __future__ import annotations

from dataclasses import dataclass

from thinkbox.cli_inspect import CLI_EXIT_FAIL, CLI_EXIT_OK, CLI_EXIT_USAGE

CLI_PHASE4_EXIT_CONTRACT: dict[str, int] = {
    "ok": CLI_EXIT_OK,
    "usage": CLI_EXIT_USAGE,
    "fail": CLI_EXIT_FAIL,
    "sandbox_denied": 3,
    "profile_missing": 4,
    "batch_partial": 5,
}


@dataclass(frozen=True)
class ExitMapping:
    name: str
    code: int


def map_outcome(outcome: str) -> int:
    """Map a named outcome to a process exit code."""
    if outcome not in CLI_PHASE4_EXIT_CONTRACT:
        return CLI_EXIT_FAIL
    return CLI_PHASE4_EXIT_CONTRACT[outcome]
