"""Backend-authoritative policy for governed remote shell execution on UpCloud.

The single source of truth for what the ``shell:upcloud-ssh:readonly`` capability
permits. Callers (the dashboard bridge, the CLI, tests) may pre-check, but the
backend enforces this module before admission and before any SSH connection.

- The capability authorizes exactly one substrate, ``upcloud-ssh``.
- The command must equal one of a fixed set of read-only commands, compared as
  exact strings. No arguments, metacharacters, chaining, redirects,
  substitution, shells, scripts, network fetches or privilege escalation can
  pass, because nothing is parsed: only exact equality admits a command.
- Conversely, ``upcloud-ssh`` execution requires this capability. A broader
  capability such as ``goal:execute`` cannot reach the worker.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

POLICY_ID = "upcloud-ssh-readonly"
POLICY_VERSION = "1"
CAPABILITY_UPCLOUD_SSH_READONLY = "shell:upcloud-ssh:readonly"
SUBSTRATE_UPCLOUD_SSH = "upcloud-ssh"

ALLOWED_READONLY_COMMANDS: frozenset[str] = frozenset(
    {"hostname", "uname -a", "uptime", "whoami", "df -h /", "free -m"}
)

# capability -> the only substrate it authorizes
CAPABILITY_SUBSTRATES: dict[str, str] = {CAPABILITY_UPCLOUD_SSH_READONLY: SUBSTRATE_UPCLOUD_SSH}
# substrate -> the only capability that may reach it
SUBSTRATE_REQUIRED_CAPABILITY: dict[str, str] = {SUBSTRATE_UPCLOUD_SSH: CAPABILITY_UPCLOUD_SSH_READONLY}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str

    @property
    def code(self) -> str:
        return self.reason


def command_fingerprint(command: str) -> str:
    """Deterministic, non-secret identity for a command (sha256 hex, first 16 chars)."""
    return hashlib.sha256(command.encode("utf-8")).hexdigest()[:16]


def evaluate(*, capability: str, execution_substrate: str, exec_command: str) -> PolicyDecision:
    """Decide whether (capability, substrate, command) is permitted. Pure; no side effects."""
    cap = (capability or "").strip()
    substrate = (execution_substrate or "").strip().lower()
    command = exec_command if isinstance(exec_command, str) else ""

    required = SUBSTRATE_REQUIRED_CAPABILITY.get(substrate)
    if required is not None and cap != required:
        return PolicyDecision(False, "substrate_requires_capability")

    bound = CAPABILITY_SUBSTRATES.get(cap)
    if bound is None:
        return PolicyDecision(True, "not_governed_by_policy")
    if substrate != bound:
        return PolicyDecision(False, "capability_substrate_mismatch")
    if command not in ALLOWED_READONLY_COMMANDS:
        return PolicyDecision(False, "command_not_allowed")
    return PolicyDecision(True, "allowed")


def policy_metadata(*, capability: str, execution_substrate: str, exec_command: str) -> dict[str, str]:
    """Non-secret policy facts recorded on the job result and receipt."""
    return {
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "capability": capability,
        "execution_substrate": execution_substrate,
        "command_fingerprint": command_fingerprint(exec_command),
    }
