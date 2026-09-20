"""Staging/production checks for founder merge proof configuration."""

from __future__ import annotations

import os

from thinkbox.pipeline_dashboard import DEFAULT_FOUNDER_PROOF_KEY


def resolve_founder_proof_key() -> str:
    """Return founder proof key; fail closed in staging/production without a real secret."""
    assert_founder_proof_key_configured()
    key = os.getenv("THINKBOX_FOUNDER_MERGE_PROOF_KEY", "").strip()
    return key or DEFAULT_FOUNDER_PROOF_KEY


def assert_founder_proof_key_configured() -> None:
    """Require THINKBOX_FOUNDER_MERGE_PROOF_KEY when deployment env is staging or production."""
    deploy = os.getenv("THINKBOX_PIPELINE_DEPLOYMENT_ENV", "").strip().lower()
    if deploy not in ("staging", "production"):
        return
    key = os.getenv("THINKBOX_FOUNDER_MERGE_PROOF_KEY", "").strip()
    if not key or key == DEFAULT_FOUNDER_PROOF_KEY:
        raise RuntimeError(
            "THINKBOX_FOUNDER_MERGE_PROOF_KEY must be set to a non-default value "
            f"when THINKBOX_PIPELINE_DEPLOYMENT_ENV={deploy}"
        )
