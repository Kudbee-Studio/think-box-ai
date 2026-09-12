"""KUDBEE Control Fabric — Governance admission tokens.

Agents must obtain a governance token before executing side effects. A token
binds identity, capability scope, accepted policy version, and optional
attestation. Without a token an instance may draft or simulate; with a token
it may act within scope. Revocation is a first-class operation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class GovernanceToken:
    token_value: str
    agent_id: str
    capabilities: frozenset[str]
    policy_version: str
    issued_at: float
    expires_at: float
    attestation: dict[str, Any] = field(default_factory=dict)
    revoked: bool = False

    def is_expired(self, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        return now >= self.expires_at

    @property
    def valid(self) -> bool:
        return not self.revoked and not self.is_expired()


@dataclass
class TokenRequest:
    agent_id: str
    capabilities: list[str] = field(default_factory=list)
    policy_version: str = "0"
    ttl_seconds: float = 3600.0
    attestation: dict[str, Any] = field(default_factory=dict)


class GovernanceTokenService:
    """Issues, verifies, and revokes binding governance tokens."""

    def __init__(self, signing_key: str | None = None) -> None:
        self._key = signing_key or secrets.token_hex(32)
        self._tokens: dict[str, GovernanceToken] = {}
        self._lock = threading.Lock()
        self._issued = 0

    def issue(self, request: TokenRequest) -> GovernanceToken:
        now = time.time()
        payload = json.dumps(
            {
                "agent_id": request.agent_id,
                "capabilities": sorted(request.capabilities),
                "policy_version": request.policy_version,
                "issued_at": now,
                "expires_at": now + request.ttl_seconds,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        signature = hmac.new(self._key.encode(), payload, hashlib.sha256).hexdigest()
        token_value = f"govt.{payload.decode()}.{signature[:32]}"
        token = GovernanceToken(
            token_value=token_value,
            agent_id=request.agent_id,
            capabilities=frozenset(request.capabilities),
            policy_version=request.policy_version,
            issued_at=now,
            expires_at=now + request.ttl_seconds,
            attestation=request.attestation,
        )
        with self._lock:
            self._tokens[token_value] = token
            self._issued += 1
        return token

    def verify(self, token_value: str, now: float | None = None) -> GovernanceToken | None:
        now = now if now is not None else time.time()
        with self._lock:
            token = self._tokens.get(token_value)
            if not token or token.revoked or token.is_expired(now):
                return None
            return token

    def revoke(self, token_value: str) -> bool:
        with self._lock:
            token = self._tokens.get(token_value)
            if not token:
                return False
            token.revoked = True
            return True

    def revoke_for_agent(self, agent_id: str) -> int:
        with self._lock:
            revoked = 0
            for token in self._tokens.values():
                if token.agent_id == agent_id and not token.revoked:
                    token.revoked = True
                    revoked += 1
            return revoked

    def issued_count(self) -> int:
        with self._lock:
            return self._issued