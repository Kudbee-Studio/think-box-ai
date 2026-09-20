"""Branch-scoped merge policy profiles (stdlib-only)."""

from __future__ import annotations

from thinkbox.pipeline_merge_policy import DEFAULT_PIPELINE_MERGE_POLICY, PipelineMergePolicy


def resolve_merge_policy_for_branch(branch: str) -> PipelineMergePolicy:
    """Hotfix/fix branches may queue merge at lower readiness (local gate still applies)."""
    normalized = (branch or "").strip().lower()
    if normalized.startswith("hotfix/") or normalized.startswith("fix/"):
        return PipelineMergePolicy(
            version="pipeline-merge-policy-hotfix-v1",
            require_readiness_score=80,
            block_when_quarantine=True,
            block_when_chain_broken=True,
        )
    return DEFAULT_PIPELINE_MERGE_POLICY
