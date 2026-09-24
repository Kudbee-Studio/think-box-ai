"""Bridge to kilo_env_matrix (PR #200)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from thinkbox.kilo_env_matrix import EnvMatrixMode, evaluate_env_matrix


def evaluate_kilo_matrix(
    environ: Mapping[str, str],
    mode: EnvMatrixMode = EnvMatrixMode.HERMETIC_UNIT,
) -> dict[str, Any]:
    result = evaluate_env_matrix(mode=mode, environ=environ)
    return {
        "mode": result.mode.value,
        "ok": result.ok,
        "violation_count": len(result.violations),
        "gate_id": "env-matrix",
        "bridged_from": "thinkbox.env_vars.matrix_bridge",
    }
