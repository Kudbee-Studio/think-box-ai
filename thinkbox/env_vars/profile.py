"""Dev / test / CI env profiles (PR #200)."""

from __future__ import annotations

import os
from enum import Enum


class EnvProfile(str, Enum):
    DEV = "dev"
    TEST = "test"
    CI = "ci"
    HERMETIC = "hermetic"


def detect_profile(environ: dict[str, str] | None = None) -> EnvProfile:
    env = environ if environ is not None else os.environ
    if env.get("CI", "").strip().lower() in {"1", "true", "yes"}:
        return EnvProfile.CI
    if env.get("THINKBOX_KILO_HERMETIC_MODE", "").strip().lower() in {"1", "true", "yes"}:
        return EnvProfile.HERMETIC
    if env.get("PYTEST_CURRENT_TEST"):
        return EnvProfile.TEST
    return EnvProfile.DEV
