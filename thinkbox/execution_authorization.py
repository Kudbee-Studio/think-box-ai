"""One authorization binding for every path that can execute a governed shell command.

At admission, the backend persists an immutable ``admission_binding`` record on the job:
agent, capability, substrate, policy id/version, and a fingerprint of the command.
It holds no secret and no command text. Every later execution of that job (resume,
reclaim) must pass ``check_bound_execution``: the record must exist, the substrate and
command fingerprint must match it, and ``remote_exec_policy`` must still allow the
recorded capability, substrate and command. A resumed or reclaimed job therefore can
never be more privileged than its original admission. Callers cannot change the
agent, capability, substrate or command.

Token admission (``AdmissionGate``) is applied by the HTTP routes. This module is the
persisted-state binding that holds even for library callers that have no token.
"""

from __future__ import annotations

from typing import Any

from thinkbox.remote_exec_policy import (
    POLICY_ID,
    POLICY_VERSION,
    PolicyDecision,
    command_fingerprint,
    evaluate,
)

ADMISSION_BINDING_KEY = "admission_binding"
_FIELDS = ("agent_id", "capability", "execution_substrate", "command_fingerprint", "policy_id", "policy_version")


def authorization_record(*, agent_id: str, capability: str, execution_substrate: str, exec_command: str) -> dict[str, str]:
    return {
        "agent_id": agent_id,
        "capability": capability,
        "execution_substrate": (execution_substrate or "").strip().lower(),
        "command_fingerprint": command_fingerprint(exec_command or ""),
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
    }


def normalize_authorization(record: Any) -> dict[str, str] | None:
    """Return the record restricted to known fields, or None if it is missing or malformed."""
    if not isinstance(record, dict) or not all(isinstance(record.get(k), str) for k in _FIELDS):
        return None
    if not record["agent_id"] or not record["capability"]:
        return None
    return {k: record[k] for k in _FIELDS}


def check_bound_execution(authorization: Any, *, execution_substrate: str, exec_command: str) -> PolicyDecision:
    """Decide whether this execution matches the job's original authorization. Pure; fail-closed."""
    auth = normalize_authorization(authorization)
    if auth is None:
        return PolicyDecision(False, "missing_authorization_context")
    substrate = (execution_substrate or "").strip().lower()
    if substrate != auth["execution_substrate"]:
        return PolicyDecision(False, "authorization_substrate_mismatch")
    if command_fingerprint(exec_command or "") != auth["command_fingerprint"]:
        return PolicyDecision(False, "command_not_authorized_for_job")
    return evaluate(capability=auth["capability"], execution_substrate=substrate, exec_command=exec_command or "")
