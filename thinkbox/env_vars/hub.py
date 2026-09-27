"""Central env pack evaluation (PR #200)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from thinkbox.env_vars.cloud_execution_keys import CLOUD_EXECUTION_FIELDS
from thinkbox.env_vars.schema import EnvField
from thinkbox.env_vars.documentation import documented_keys, schema_keys_union
from thinkbox.env_vars.governance_keys import GOVERNANCE_FIELDS
from thinkbox.env_vars.loader import load_from_mapping
from thinkbox.env_vars.matrix_bridge import evaluate_kilo_matrix
from thinkbox.env_vars.profile import detect_profile
from thinkbox.env_vars.provider_keys import PROVIDER_FIELDS
from thinkbox.env_vars.receipt import env_receipt_block
from thinkbox.env_vars.snapshot import build_redacted_snapshot
from thinkbox.env_vars.substrate_keys import SUBSTRATE_FIELDS
from thinkbox.env_vars.think_job_keys import THINK_JOB_FIELDS
from thinkbox.env_vars.validate import validate_fields
from thinkbox.env_vars.version import GATE_ID, PR_NUMBER

ALL_FIELDS: tuple[EnvField, ...] = (
    *SUBSTRATE_FIELDS,
    *GOVERNANCE_FIELDS,
    *CLOUD_EXECUTION_FIELDS,
    *PROVIDER_FIELDS,
    *THINK_JOB_FIELDS,
)


def evaluate_env_pack(environ: Mapping[str, str]) -> dict[str, Any]:
    profile = detect_profile(dict(environ))
    validation = validate_fields(ALL_FIELDS, environ)
    matrix = evaluate_kilo_matrix(environ)
    doc_keys = documented_keys()
    schema_keys = schema_keys_union()
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "profile": profile.value,
        "validation": validation.to_dict(),
        "matrix_bridge": matrix,
        "documented_key_count": len(doc_keys),
        "schema_key_count": len(schema_keys),
        "schema_documented_overlap": len(schema_keys & doc_keys),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }


def load_all_parsed(environ: Mapping[str, str]) -> dict[str, object]:
    loaded = load_from_mapping(ALL_FIELDS, environ, profile=detect_profile(dict(environ)).value)
    return loaded.parsed


def operator_summary(environ: Mapping[str, str]) -> dict[str, Any]:
    return {
        "evaluate": evaluate_env_pack(environ),
        "snapshot": build_redacted_snapshot(environ),
        "receipt": env_receipt_block(environ, GATE_ID, PR_NUMBER),
    }
