"""Think Job control-plane env schema (PR #200)."""

from __future__ import annotations

from thinkbox.env_vars.schema import EnvField, EnvValueKind

THINK_JOB_FIELDS: tuple[EnvField, ...] = (
    EnvField(
        key="THINKBOX_API_KEY",
        kind=EnvValueKind.STRING,
        required=False,
        sensitive=True,
        description="Control-plane API key",
    ),
    EnvField(
        key="THINKBOX_LOG_LEVEL",
        kind=EnvValueKind.STRING,
        required=False,
        sensitive=False,
        description="Logging level",
        default="INFO",
    ),
    EnvField(
        key="THINKBOX_KILO_HERMETIC_MODE",
        kind=EnvValueKind.BOOL,
        required=False,
        sensitive=False,
        description="Hermetic mode for CI/unit",
        default="true",
    ),
)
