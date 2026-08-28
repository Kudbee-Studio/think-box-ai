"""Secret resolution for THINK BOX AI.

Extends the THINKBOX_ environment variable pattern from config.py
for sensitive values (API keys, tokens, credentials).

Secrets are resolved lazily on access, never cached in memory
beyond the call lifetime, and never logged or printed.
"""

from __future__ import annotations

import os
from typing import Optional

from core.foundation.config import ENV_PREFIX


class SecretResolver:
    """Resolves secrets from environment variables with lazy evaluation.

    Resolution order:
      1. Environment variable (THINKBOX_{KEY})
      2. Provided default value
      3. None

    Values are read from os.environ on each access, never stored
    as instance state. This ensures secrets are not retained in
    memory longer than necessary.
    """

    def __init__(self, defaults: Optional[dict[str, str]] = None) -> None:
        """Initialize with optional default values.

        Args:
            defaults: Mapping of secret keys to default values.
                      Used when the corresponding env var is not set.
        """
        self._defaults: dict[str, str] = defaults if defaults is not None else {}

    def resolve(self, key: str) -> Optional[str]:
        """Resolve a secret by key.

        Looks for THINKBOX_{KEY} in environment variables.
        Falls back to the default provided at construction.

        Args:
            key: Secret name (e.g., "OPENAI_API_KEY" looks for
                 THINKBOX_OPENAI_API_KEY).

        Returns:
            The secret value, or None if not found.
        """
        env_key = f"{ENV_PREFIX}{key}"
        value = os.environ.get(env_key)
        if value is not None:
            return value
        return self._defaults.get(key)

    def resolve_required(self, key: str) -> str:
        """Resolve a secret that must exist.

        Args:
            key: Secret name.

        Returns:
            The secret value.

        Raises:
            SecretResolutionError: If the secret is not found
                in env vars or defaults.
        """
        value = self.resolve(key)
        if value is None:
            raise SecretResolutionError(key)
        return value

    def is_set(self, key: str) -> bool:
        """Check if a secret is available without resolving it.

        Args:
            key: Secret name.

        Returns:
            True if the secret can be resolved.
        """
        env_key = f"{ENV_PREFIX}{key}"
        return env_key in os.environ or key in self._defaults


class SecretResolutionError(Exception):
    """Raised when a required secret cannot be resolved."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(
            f"Required secret '{key}' not found. "
            f"Set THINKBOX_{key} environment variable or provide a default."
        )
