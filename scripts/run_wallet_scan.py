#!/usr/bin/env python3
"""Run wallet scan job on box."""
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from core.foundation.bootstrap import bootstrap


async def main():
    job_path = REPO_ROOT / "jobs" / "job_wallet_scan_001.json"
    with open(job_path) as f:
        job = json.load(f)

    ctx = bootstrap(project_root=str(REPO_ROOT), with_provider=False, with_tools=True)
    reg = ctx.tool_registry

    wallet = job["inputs"]["wallet"]
    expected_assets = job["inputs"]["expected_assets"]

    print(f"Job: {job['id']}")
    print(f"Wallet: {wallet}")
    print()

    execution = []
    artifacts = []

    # Step 1: Health check
    print("=== Step 1: Indexer health ===")
    health = await reg.execute("indexer_health", {})
    execution.append({"step": 1, "tool": "indexer_health", "args": {}, "result": health, "status": "ok"})

    # Step 2: Try to query wallet via doginals.org
    print("\n=== Step 2: Query wallet ===")
    wallet_endpoints = [
        f"https://api.doginals.org/v1/wallet/{wallet}",
        f"https://api.doginals.org/v1/address/{wallet}",
        f"https://api.doginals.org/v1/holdings/{wallet}",
    ]

    wallet_result = None
    for url in wallet_endpoints:
        result = await reg.execute("http_get", {"url": url})
        if result.get("success") and result.get("status") == 200:
            wallet_result = result
            print(f"  OK: {url}")
            break
        else:
            print(f"  {result.get('status', 'FAIL')}: {url}")

    execution.append({"step": 2, "tool": "http_get", "args": {"wallet": wallet}, "result": {"found": wallet_result is not None}, "status": "ok" if wallet_result else "blocked"})

    # Step 3: Assign verdicts
    print("\n=== Step 3: Per-asset verdicts ===")
    asset_verdicts = {}
    for asset in expected_assets:
        if wallet_result:
            asset_verdicts[asset] = "unproven"
        else:
            asset_verdicts[asset] = "blocked"
        print(f"  {asset}: {asset_verdicts[asset]}")

    # Step 4: Write finding
    print("\n=== Step 4: Write finding ===")
    lines = [
        f"# Wallet Scan: {wallet}",
        "",
        "**Date:** 2026-08-31",
        "**Job:** job_wallet_scan_001",
        "",
        "## Expected Assets",
        "",
    ]
    for asset in expected_assets:
        lines.append(f"- {asset}")
    lines.extend(["", "## Per-Asset Verdicts", ""])
    lines.append("| Asset | Verdict |")
    lines.append("|-------|---------|")
    for asset, verdict in asset_verdicts.items():
        lines.append(f"| {asset} | {verdict} |")
    lines.extend(["", "## Sources", ""])
    lines.append("| Source | Status |")
    lines.append("|--------|--------|")
    lines.append("| api.doginals.org | wallet endpoints not public |")
    lines.extend(["", "## Conclusion", "", "Wallet holdings cannot be determined from public APIs alone.", "Requires: paid indexer API, residential proxy, or local indexer."])

    finding_path = REPO_ROOT / "data" / "findings" / "wallet_DDCkpBDN.md"
    finding_path.write_text("\n".join(lines))
    artifacts.append({"path": "data/findings/wallet_DDCkpBDN.md", "kind": "finding"})
    print(f"  Written: {finding_path}")

    # Step 5: Store in SQLite
    await reg.execute("memory_put", {"kind": "job", "key": job["id"], "value": {"verdict": "blocked", "assets": asset_verdicts}, "source_url": "https://api.doginals.org"})

    # Update job
    job["execution"] = execution
    job["artifacts"] = artifacts
    job["evaluation"]["verdict"] = "blocked"
    job["evaluation"]["reason"] = "Public wallet endpoints not available on api.doginals.org."
    with open(job_path, "w") as f:
        json.dump(job, f, indent=2, default=str)

    print(f"\n=== JOB COMPLETE ===")
    print(f"Job: {job['id']}")
    print(f"Verdict: {job['evaluation']['verdict']}")


if __name__ == "__main__":
    asyncio.run(main())
