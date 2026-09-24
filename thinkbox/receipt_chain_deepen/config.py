"""Fail-closed env config for deepen demos (PR #182 F04)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from thinkbox.receipt_chain_deepen.errors import ReceiptChainDeepenError

__all__ = ("DeepenConfig", "load_config_from_env")


@dataclass(frozen=True)
class DeepenConfig:
    dry_run: bool
    export_redact: bool
    max_chain_entries: int


def load_config_from_env(environ: Mapping[str, str] | None = None) -> DeepenConfig:
    env = dict(os.environ if environ is None else environ)
    dry_raw = (env.get("RECEIPT_CHAIN_DEEPEN_DRY_RUN") or "true").lower()
    if dry_raw not in ("true", "1", "yes"):
        raise ReceiptChainDeepenError("dry_run_required", "hermetic deepen requires dry_run=true")
    max_entries = int(env.get("RECEIPT_CHAIN_DEEPEN_MAX_ENTRIES") or "256")
    if max_entries < 1 or max_entries > 4096:
        raise ReceiptChainDeepenError("max_entries", "max_entries out of range")
    redact = (env.get("RECEIPT_CHAIN_DEEPEN_REDACT") or "true").lower() in ("true", "1", "yes")
    return DeepenConfig(dry_run=True, export_redact=redact, max_chain_entries=max_entries)
