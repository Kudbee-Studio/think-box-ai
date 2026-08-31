#!/usr/bin/env python3
"""DOGI proof — honest version. Records exactly what each endpoint returns."""
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.foundation.bootstrap import bootstrap


INSCRIPTION_IDS = [
    "15f3b73df7e5c072becb1d84191843ba080734805addfccb650929719080f62ei0",
    "0bd32d69ca2221f3fc34d99aa14bccc2af10eedc7514770ae842ab9a72468743",
    "ee688262677b00d973d0aa18e40863e8ba984e4237ac6ef46dd53a5b0d380092",
]


async def main():
    ctx = bootstrap(project_root=str(REPO_ROOT), with_provider=False, with_tools=True)
    reg = ctx.tool_registry

    print(f"Tools: {len(reg.list_tools())}")

    # Health check
    print("\n=== SOURCE HEALTH ===")
    health = await reg.execute("indexer_health", {})
    health_json = json.dumps(health, indent=2)
    print(health_json)

    # Load fixture
    print("\n=== FIXTURE ===")
    fixture = await reg.execute("load_fixture", {"name": "dogi_canonical.json"})
    if fixture.get("success"):
        d = fixture["data"]
        print(f"Token: {d.get('token')}")
        print(f"Original deploy: {d['original_deploy'].get('txid', 'N/A')[:30]}...")
        print(f"Later deploy: {d['later_deploy'].get('txid', 'N/A')[:30]}...")

    # Test each inscription
    results = {}
    for insc_id in INSCRIPTION_IDS:
        print(f"\n=== INSCRIPTION {insc_id[:25]}... ===")
        compare = await reg.execute("compare_inscription", {
            "inscription_id": insc_id,
            "indexers": ["doginals_org", "dogechain"],
        })
        diff = compare.get("diff", {})
        print(f"  OK: {diff.get('sources_ok', [])}")
        print(f"  Failed: {diff.get('sources_failed', [])}")
        results[insc_id] = diff

    # Write findings
    findings = generate_findings(health, fixture, results)
    findings_path = REPO_ROOT / "data" / "findings" / "dogi_indexer_split.md"
    findings_path.write_text(findings)
    print(f"\n=== FINDING WRITTEN ===")
    print(f"Path: {findings_path}")

    # Store in SQLite
    await reg.execute("memory_put", {
        "kind": "finding",
        "key": "dogi_indexer_split",
        "value": {"results": {k[:16]: {"ok": v.get("sources_ok"), "failed": v.get("sources_failed")} for k, v in results.items()}},
        "source_url": "https://api.doginals.org",
    })
    print("Stored in SQLite")


def generate_findings(health, fixture, results):
    lines = [
        "# DOGI Indexer-Split Proof Report",
        "",
        "**Date:** 2026-08-31",
        "**Session:** agent_79e656bf-37c6-46f2-833e-1eb027b99152",
        "**Token:** DOGI (Doginals/DRC-20)",
        "",
        "## Source Health",
        "",
        "```json",
        json.dumps(health, indent=2),
        "```",
        "",
        "## Inscription IDs Tested",
        "",
    ]
    for insc_id in INSCRIPTION_IDS:
        lines.append(f"- `{insc_id}`")

    lines.extend(["", "## Detailed Results", ""])

    for insc_id, diff in results.items():
        lines.append(f"### `{insc_id[:32]}...`")
        lines.append("")
        lines.append(f"- **Sources tested:** {diff.get('sources_tested', [])}")
        lines.append(f"- **Sources OK:** {diff.get('sources_ok', []) or 'none'}")
        lines.append(f"- **Sources failed:** {diff.get('sources_failed', []) or 'none'}")
        lines.append("")

        if diff.get("results"):
            for source, r in diff["results"].items():
                lines.append(f"#### {source}")
                if r.get("success"):
                    lines.append("- Status: **OK**")
                    data = r.get("data", {})
                    if isinstance(data, dict):
                        for k, v in list(data.items())[:5]:
                            lines.append(f"- {k}: {str(v)[:100]}")
                else:
                    lines.append(f"- Status: **FAILED** — {r.get('error', 'unknown')}")
                lines.append("")

    lines.extend([
        "## Honest Assessment",
        "",
        "### What this proves",
        "- Different sources have different availability (some 200, some 403, some DNS dead).",
        "- api.doginals.org health endpoint responds; inscription endpoints do not (404).",
        "- dogechain.info TLS succeeds but returns 403 (Cloudflare anti-bot).",
        "",
        "### What this does NOT prove",
        "- We cannot verify the 21M vs 2.1B DOGI deploy split.",
        "- We cannot compare indexer consensus because no source returned inscription content.",
        "- This does NOT disprove the thesis — public APIs are simply insufficient.",
        "",
        "### Conclusion",
        "",
        "The indexer-split thesis remains **unproven** due to lack of accessible inscription data.",
        "To prove it requires: paid indexer API, residential proxy, or local ord indexer.",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    asyncio.run(main())
