"""CLI command mirror registry for SDK consumers (PR #177 F23)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CliMirrorCommand:
    cli_path: str
    sdk_method: str
    hermetic: bool
    description: str


CLI_MIRROR_COMMANDS: tuple[CliMirrorCommand, ...] = (
    CliMirrorCommand("thinkbox swarm status", "KudbeeClient.swarmStatus", True, "Swarm evidence summary"),
    CliMirrorCommand("thinkbox ledger verify", "KudbeeClient.ledgerVerify", True, "Ledger hash chain"),
    CliMirrorCommand("thinkbox proof check", "KudbeeClient.proofCheck", True, "Validate proof JSON"),
    CliMirrorCommand("thinkbox env status", "KudbeeClient.envStatus", True, "Redacted env status"),
    CliMirrorCommand("thinkbox session list", "KudbeeClient.sessionList", True, "Recent sessions"),
    CliMirrorCommand("thinkbox swarm agents", "KudbeeClient.swarmAgents", True, "Population stats"),
)


def list_cli_mirrors() -> tuple[CliMirrorCommand, ...]:
    return CLI_MIRROR_COMMANDS
