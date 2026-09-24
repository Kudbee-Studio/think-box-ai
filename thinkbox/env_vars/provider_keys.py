"""Provider env schema (PR #200)."""

from __future__ import annotations

from thinkbox.env_vars.schema import EnvField, EnvValueKind

PROVIDER_FIELDS: tuple[EnvField, ...] = (
    EnvField(
        key="THINKBOX_DEFAULT_PROVIDER",
        kind=EnvValueKind.STRING,
        required=False,
        sensitive=False,
        description="Default model provider id",
    ),
    EnvField(
        key="THINKBOX_OPENAI_COMPAT_API_KEY",
        kind=EnvValueKind.STRING,
        required=False,
        sensitive=True,
        description="OpenAI-compatible API key",
    ),
    EnvField(
        key="THINKBOX_OPENAI_COMPAT_BASE_URL",
        kind=EnvValueKind.URL,
        required=False,
        sensitive=False,
        description="OpenAI-compatible base URL",
    ),
    EnvField(
        key="INCEPTION_API_KEY",
        kind=EnvValueKind.STRING,
        required=False,
        sensitive=True,
        description="Inception/Mercury API key",
    ),
)
