"""Doginals / DRC-20 domain tools for THINK BOX AI.

Uses only public APIs:
- dogechain.info for Dogecoin transaction data
- Public inscription indexers for Doginals/DRC-20 data
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.tools.registry import tool

_FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures"


@tool(
    name="doge_tx",
    description="Fetch a Dogecoin transaction from dogechain.info. Returns tx details including inputs, outputs, and block info.",
    permission="network",
    input_schema={"type": "object", "properties": {"txid": {"type": "string"}}, "required": ["txid"]},
)
async def doge_tx(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    txid = args.get("txid", "")
    if not txid or not re.match(r'^[0-9a-fA-F]{64}$', txid):
        return {"success": False, "error": "Invalid txid: expected 64 hex characters"}

    url = f"https://dogechain.info/api/v1/transaction/{txid}"

    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(url, headers={"User-Agent": "ThinkBoxAI-Research/0.2"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        return {
            "success": True,
            "txid": txid,
            "data": data,
            "source": "dogechain.info",
        }
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.reason}", "txid": txid, "source": "dogechain.info"}
    except Exception as e:
        return {"success": False, "error": str(e), "txid": txid, "source": "dogechain.info"}


@tool(
    name="doginals_inscription",
    description="Fetch inscription data from a public Doginals indexer. Supports multiple indexers for comparison.",
    permission="network",
    input_schema={"type": "object", "properties": {"inscription_id": {"type": "string"}, "indexer": {"type": "string"}}, "required": ["inscription_id"]},
)
async def doginals_inscription(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    inscription_id = args.get("inscription_id", "")
    indexer = args.get("indexer", "ordinalsdotcom")
    if not inscription_id:
        return {"success": False, "error": "Missing 'inscription_id'"}

    endpoints = {
        "ordinalsdotcom": f"https://api.ordinalswallet.com/inscription/{inscription_id}",
        "ord_api": f"https://ordinals.com/inscription/{inscription_id}",
        "wonky": f"https://wonky-ordinals.fly.dev/inscription/{inscription_id}",
        "doginals_org": f"https://doginals.org/api/inscription/{inscription_id}",
        "unisat": f"https://open-api.unisat.io/v1/indexer/inscription/info/{inscription_id}",
    }

    url = endpoints.get(indexer)
    if not url:
        return {"success": False, "error": f"Unknown indexer '{indexer}'. Available: {list(endpoints.keys())}"}

    try:
        import urllib.request
        import urllib.error

        headers = {"User-Agent": "ThinkBoxAI-Research/0.2", "Accept": "application/json"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read()

        text = body.decode("utf-8", errors="replace")
        if "json" in content_type:
            data = json.loads(text)
        else:
            data = {"raw": text[:5000], "content_type": content_type}

        return {
            "success": True,
            "inscription_id": inscription_id,
            "indexer": indexer,
            "data": data,
            "source_url": url,
        }
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.reason}", "inscription_id": inscription_id, "indexer": indexer, "source_url": url}
    except Exception as e:
        return {"success": False, "error": str(e), "inscription_id": inscription_id, "indexer": indexer, "source_url": url}


@tool(
    name="compare_inscription",
    description="Compare an inscription across multiple indexers. Returns a diff showing what each indexer reports.",
    permission="network",
    input_schema={"type": "object", "properties": {"inscription_id": {"type": "string"}, "indexers": {"type": "array", "items": {"type": "string"}}}, "required": ["inscription_id"]},
)
async def compare_inscription(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    inscription_id = args.get("inscription_id", "")
    indexers = args.get("indexers", ["ordinalsdotcom", "wonky", "doginals_org"])
    if not inscription_id:
        return {"success": False, "error": "Missing 'inscription_id'"}

    results = {}
    for indexer in indexers:
        result = await doginals_inscription({"inscription_id": inscription_id, "indexer": indexer})
        results[indexer] = {
            "success": result.get("success"),
            "error": result.get("error"),
            "data": result.get("data") if result.get("success") else None,
        }

    successes = [k for k, v in results.items() if v["success"]]
    failures = [k for k, v in results.items() if not v["success"]]

    diff = {
        "inscription_id": inscription_id,
        "sources_tested": list(results.keys()),
        "sources_ok": successes,
        "sources_failed": failures,
        "results": results,
        "agreement": len(successes) > 0,
        "disagreement": len(successes) > 1 and len(failures) > 0,
    }

    return {"success": True, "diff": diff}


@tool(
    name="parse_drc20",
    description="Parse DRC-20 JSON from inscription content. Detects deploy, mint, transfer operations.",
    permission="read_only",
    input_schema={"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]},
)
async def parse_drc20(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    content = args.get("content", "")
    if not content:
        return {"success": False, "error": "Missing 'content' argument"}

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {"success": False, "error": "Content is not valid JSON", "is_drc20": False}

    if not isinstance(data, dict):
        return {"success": False, "error": "JSON is not an object", "is_drc20": False}

    protocol = data.get("p", "")
    op = data.get("op", "")
    valid_ops = ("deploy", "mint", "transfer")

    if protocol in ("drc-20", "doginals", "dogi") and op in valid_ops:
        return {
            "success": True,
            "is_drc20": True,
            "protocol": protocol,
            "operation": op,
            "tick": data.get("tick", ""),
            "amount": data.get("amt", data.get("max", "")),
            "max_supply": data.get("max", ""),
            "limit": data.get("lim", ""),
            "raw": data,
        }

    return {
        "success": True,
        "is_drc20": False,
        "protocol": protocol,
        "operation": op,
        "note": "Not a recognized DRC-20 operation",
        "raw": data,
    }


@tool(
    name="load_fixture",
    description="Load a JSON fixture from data/fixtures/. Used to get canonical test data for the proof run.",
    permission="read_only",
    input_schema={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
)
async def load_fixture(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    name = args.get("name", "")
    if not name:
        return {"success": False, "error": "Missing 'name' argument"}
    if "/" in name or ".." in name:
        return {"success": False, "error": "Invalid fixture name"}

    fixture_path = _FIXTURES_DIR / name
    if not fixture_path.exists():
        return {"success": False, "error": f"Fixture not found: {name}"}

    try:
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        return {"success": True, "fixture": name, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}
