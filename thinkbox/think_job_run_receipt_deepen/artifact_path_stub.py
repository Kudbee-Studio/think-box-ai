"""Artifact directory stub (PR #186 F08)."""
from __future__ import annotations
import os

def artifact_dir() -> str:
    return os.environ.get("THINKBOX_HTTP_RUN_ARTIFACTS", "data/thinkboxmd/artifacts/http_run")
