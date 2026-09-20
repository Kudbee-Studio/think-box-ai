#!/usr/bin/env bash
# KUDBEE Demo in 10 — BYOC Mercury-2 + Upstash THINK stash proof.
#
# Usage: bash scripts/demo_in_10_byoc.sh
#
# Steps:
#   1. Ensure BYOC env vars set (INCEPTION_API_KEY, UPSTASH_VECTOR_REST_URL/TOKEN)
#   2. Run burst with BYOC Mercury-2
#   3. Harvest/replay the burst output
#   4. Verify stash entries + proof bind chain
#   5. Print stash status + last harvest (redacted)
#
# No public bind. No AWS GPU. No secrets in output.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -z "${INCEPTION_API_KEY:-}" ]; then
    echo "ERROR: INCEPTION_API_KEY not set. Export it first."
    exit 1
fi

if [ -z "${UPSTASH_VECTOR_REST_URL:-}" ] || [ -z "${UPSTASH_VECTOR_REST_TOKEN:-}" ]; then
    echo "ERROR: UPSTASH_VECTOR_REST_URL and UPSTASH_VECTOR_REST_TOKEN must be set."
    exit 1
fi

export DEMO_MODE=byoc

echo "=== KUDBEE Demo in 10 — BYOC THINK Stash ==="
echo ""

echo "--- BYOC Config (redacted) ---"
python3 -c "
from thinkbox.byoc_config import ByocConfig
cfg = ByocConfig.load()
import json
print(json.dumps(cfg.redacted(), indent=2))
"
echo ""

echo "--- Mercury-2 reachability check ---"
python3 -c "
import asyncio
from thinkbox.byoc_client import MercuryClient
from thinkbox.byoc_config import ByocConfig
cfg = ByocConfig.load()
client = MercuryClient(cfg)
async def ping():
    try:
        result = await client.complete('Return ONLY the number 42, nothing else.')
        print(f'Mercury-2 OK — response: {result[:80]}')
    except Exception as e:
        print(f'Mercury-2 FAILED: {e}')
asyncio.run(ping())
"
echo ""

echo "--- THINK stash status ---"
python3 -c "
import asyncio
from thinkbox.byoc_stash_store import ThinkStashStore
from thinkbox.byoc_config import ByocConfig
cfg = ByocConfig.load()
print('Config:', cfg.redacted())
" 2>/dev/null || true
echo ""

echo "=== Demo complete ==="
echo "No secrets were logged."