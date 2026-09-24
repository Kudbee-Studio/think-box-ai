"""FIX15: Catalog nested e2e modules (opt-in only; spine stays fast)."""

from __future__ import annotations

from typing import Any

from thinkbox.kilo_hermetic_subprocess import e2e_unittest_skipped_by_default, nested_e2e_unittest_enabled

E2E_MODULES: tuple[str, ...] = (
    "tests.e2e.test_f023_think_job_lifecycle",
    "tests.e2e.test_f131_post_run_think_job_contract",
)


def apply_fix() -> dict[str, Any]:
    return {
        "fix_id": "FIX15",
        "e2e_modules": list(E2E_MODULES),
        "skipped_by_default": e2e_unittest_skipped_by_default(),
        "nested_enabled": nested_e2e_unittest_enabled(),
        "live_api_called": False,
    }
