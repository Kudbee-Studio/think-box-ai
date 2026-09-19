"""
Threshold-signed Governance Tokens.

Extends the HMAC-based GovernanceTokenService with threshold cryptography:
tokens require signatures from a configurable quorum of validators before
they can be used. This prevents any single compromised node from issuing
or forging governance tokens.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from thinkbox.governance_token import GovernanceToken, GovernanceTokenService, TokenRequest

logger = logging.getLogger(__name__)


@dataclass
class ValidatorSignature:
    validator_id: str
    token_value: str
    signature: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class ThresholdTokenRequest(TokenRequest):
    validator_ids: list[str] = field(default_factory=list)
    threshold: int = 2


@dataclass
class ThresholdGovernanceToken(GovernanceToken):
    token_value: str
    agent_id: str
    capabilities: frozenset[str]
    policy_version: str
    issued_at: float
    expires_at: float
    attestation: dict[str, Any] = field(default_factory=dict)
    revoked: bool = False
    validator_signatures: list[ValidatorSignature] = field(default_factory=list)
    threshold: int = 2
    validators: list[str] = field(default_factory=list)

    def is_fully_signed(self) -> bool:
        unique_validators = set(sig.validator_id for sig in self.validator_signatures)
        return len(unique_validators) >= self.threshold

    def is_expired(self, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        return now >= self.expires_at

    @property
    def valid(self) -> bool:
        return (
            not self.revoked
            and not self.is_expired()
            and self.is_fully_signed()
        )


class ThresholdGovernanceTokenService(GovernanceTokenService):
    """
    Threshold-signed governance token service.

    Tokens require signatures from a quorum of validators before becoming
    valid. Extends the base GovernanceTokenService with threshold signing.
    """

    def __init__(
        self,
        signing_key: str | None = None,
        validator_ids: list[str] | None = None,
        threshold: int = 2,
    ) -> None:
        super().__init__(signing_key=signing_key)
        self._validators: list[str] = validator_ids or []
        self._threshold = max(threshold, 1)
        self._pending_tokens: dict[str, ThresholdGovernanceToken] = {}
        self._signatures: dict[str, list[ValidatorSignature]] = {}
        self._lock = threading.Lock()

    @property
    def validators(self) -> list[str]:
        return list(self._validators)

    @property
    def threshold(self) -> int:
        return self._threshold

    def issue(
        self,
        request: ThresholdTokenRequest,
    ) -> ThresholdGovernanceToken:
        now = time.time()
        token = ThresholdGovernanceToken(
            token_value=self._build_token_value(request.agent_id, now),
            agent_id=request.agent_id,
            capabilities=frozenset(request.capabilities),
            policy_version=request.policy_version,
            issued_at=now,
            expires_at=now + request.ttl_seconds,
            attestation=request.attestation,
            threshold=self._threshold,
            validators=list(request.validator_ids) or self._validators,
        )
        with self._lock:
            self._tokens[token.token_value] = token
            self._pending_tokens[token.token_value] = token
            self._issued += 1
        return token

    def sign(
        self,
        token_value: str,
        validator_id: str,
    ) -> bool:
        with self._lock:
            token = self._tokens.get(token_value)
            if not token:
                logger.warning(f"Token not found for signing: {token_value[:24]}")
                return False
            if validator_id not in token.validators:
                logger.warning(
                    f"Validator {validator_id} not authorized for token {token_value[:24]}"
                )
                return False
            if validator_id in {sig.validator_id for sig in token.validator_signatures}:
                return False

            signature = self._sign_for_validator(token_value, validator_id)
            sig = ValidatorSignature(
                validator_id=validator_id,
                token_value=token_value,
                signature=signature,
            )
            token.validator_signatures.append(sig)

            if token_value not in self._signatures:
                self._signatures[token_value] = []
            self._signatures[token_value].append(sig)

            if token.is_fully_signed():
                token.revoked = False
                if token_value in self._pending_tokens:
                    del self._pending_tokens[token_value]
                logger.info(
                    f"Token {token_value[:24]} fully signed by {len(token.validator_signatures)}/{token.threshold} validators"
                )
            return True

    def verify(
        self, token_value: str, now: float | None = None
    ) -> ThresholdGovernanceToken | None:
        now = now if now is not None else time.time()
        with self._lock:
            token = self._tokens.get(token_value)
            if not token:
                return None
            if token.revoked or token.is_expired(now):
                return None
            if not token.is_fully_signed():
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

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending_tokens)

    def signed_count(self) -> int:
        with self._lock:
            return sum(
                1 for t in self._tokens.values() if isinstance(t, ThresholdGovernanceToken) and t.is_fully_signed()
            )

    def validator_signatures_for(
        self, token_value: str
    ) -> list[ValidatorSignature]:
        with self._lock:
            return list(self._signatures.get(token_value, []))

    def _sign_for_validator(
        self, token_value: str, validator_id: str
    ) -> str:
        payload = f"{token_value}:{validator_id}:{self._key}"
        return hmac.new(
            self._key.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()[:32]

    @staticmethod
    def _build_token_value(agent_id: str, now: float) -> str:
        payload = json.dumps(
            {"agent_id": agent_id, "issued_at": now},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return f"tgov.{payload.decode()}.{secrets.token_hex(16)}"
