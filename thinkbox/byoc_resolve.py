"""DEMO_MODE=mock|byoc dual path — fail-closed."""

from __future__ import annotations

import logging
from typing import Any

from thinkbox.byoc_config import ByocConfig

logger = logging.getLogger(__name__)


def resolve_mercury_byoc(config: ByocConfig | None = None) -> dict[str, Any]:
    """Resolve BYOC path based on DEMO_MODE.

    Returns dict with:
      - mode: "mock" | "byoc"
      - usable: bool (can we make real calls?)
      - client: MercuryClient | None
      - config_redacted: safe config snapshot

    Fail-closed: if mode=byoc but config incomplete, usable=False.
    """
    cfg = config or ByocConfig.load()
    mode = cfg.demo_mode

    if mode == "mock":
        logger.info("DEMO_MODE=mock: using synthetic path")
        return {
            "mode": "mock",
            "usable": True,
            "client": None,
            "config_redacted": cfg.redacted(),
            "note": "mock mode — synthetic responses only",
        }

    if mode == "byoc":
        if cfg.is_live:
            logger.info("DEMO_MODE=byoc: using live Mercury-2 + Upstash")
            from thinkbox.byoc_client import MercuryClient

            client = MercuryClient(cfg)
            return {
                "mode": "byoc",
                "usable": True,
                "client": client,
                "config_redacted": cfg.redacted(),
                "note": "live mode — real Mercury-2 + Upstash",
            }
        logger.warning("DEMO_MODE=byoc but credentials missing — fail-closed")
        return {
            "mode": "byoc",
            "usable": False,
            "client": None,
            "config_redacted": cfg.redacted(),
            "error": "INCEPTION_API_KEY + UPSTASH_VECTOR_REST_URL + UPSTASH_VECTOR_REST_TOKEN required",
        }

    logger.warning("Unknown DEMO_MODE: %s — defaulting to mock", mode)
    return {
        "mode": "mock",
        "usable": True,
        "client": None,
        "config_redacted": cfg.redacted(),
        "note": f"unknown mode {mode} — defaulted to mock",
    }