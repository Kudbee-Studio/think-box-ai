#!/usr/bin/env python3
"""Presence-only Cursor Box env binding check (PR #201).

Never prints secret values. Reports process presence and whether official
adapter secret names appear in ``CLOUD_AGENT_ALL_SECRET_NAMES``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.upstash_box_access import (  # noqa: E402
    ADAPTER_REQUIRED_KEYS,
    assert_no_secret_material,
    cursor_secret_catalog_listed,
    parse_cursor_secret_catalog,
    presence_inventory,
)


def main() -> int:
    presence = presence_inventory()
    catalog_listed = cursor_secret_catalog_listed()
    catalog = parse_cursor_secret_catalog()
    payload = {
        "presence": presence,
        "cursor_secret_catalog_available": bool(catalog),
        "cursor_secret_catalog_listed": catalog_listed,
        "cursor_secret_catalog_count": len(catalog),
        "adapter_required_keys": list(ADAPTER_REQUIRED_KEYS),
    }
    assert_no_secret_material(payload, __import__("os").environ)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if all(presence[k] for k in ADAPTER_REQUIRED_KEYS):
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
