"""Cloud execution worker env schema (PR #200)."""

from __future__ import annotations

from thinkbox.env_vars.schema import EnvField, EnvValueKind

CLOUD_EXECUTION_FIELDS: tuple[EnvField, ...] = (
    EnvField(
        key="THINKBOX_CLOUD_EXEC_WORKER_ID",
        kind=EnvValueKind.STRING,
        required=False,
        sensitive=False,
        description="Worker identity for cloud execution",
    ),
    EnvField(
        key="THINKBOX_CLOUD_EXEC_MAX_ACTIVE_JOBS",
        kind=EnvValueKind.INT,
        required=False,
        sensitive=False,
        description="Per-worker concurrency cap",
        default="1",
    ),
    EnvField(
        key="THINKBOX_CLOUD_EXEC_HERMETIC",
        kind=EnvValueKind.BOOL,
        required=False,
        sensitive=False,
        description="Force hermetic provider in cloud execution",
        default="true",
    ),
)
