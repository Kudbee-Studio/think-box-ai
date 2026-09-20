#!/usr/bin/env bash
# KUDBEE Demo in 10 — Upstash Box + Inception Mercury-2 live experiment.
#
# Usage: bash scripts/demo_in_10_box_mercury.sh
#
# Steps:
#   1. Verify env vars (INCEPTION_API_KEY, UPSTASH_PUBLIC_BOX_URL)
#   2. Detect substrate (must be Upstash Box)
#   3. Run live experiment: box_mercury_live.py
#   4. Print throughput summary + proof hash
#   5. Verify artifact exists
#
# No GPU. No public bind. No SSH. No AWS.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== KUDBEE Demo in 10 — Box + Mercury-2 Live ==="
echo ""

if [ -z "${INCEPTION_API_KEY:-}" ]; then
    echo "ERROR: INCEPTION_API_KEY not set"
    exit 1
fi

if [ -z "${UPSTASH_PUBLIC_BOX_URL:-}" ]; then
    echo "ERROR: UPSTASH_PUBLIC_BOX_URL not set"
    exit 1
fi

echo "--- Substrate Check ---"
SUBSTRATE=$(python3 -c "
from thinkbox.substrate import detect_substrate
print(detect_substrate())
" 2>/dev/null || echo "unknown")

if [ "$SUBSTRATE" = "unknown" ] || [ -z "$SUBSTRATE" ]; then
    echo "WARNING: Could not detect substrate, continuing anyway"
else
    echo "Detected substrate: $SUBSTRATE"
fi

echo ""
echo "--- Running Live Experiment ---"
echo ""

python3 experiments/box_mercury_live.py
BURST_EXIT=$?

echo ""
if [ "$BURST_EXIT" -ne 0 ]; then
    echo "WARNING: experiment exited with code $BURST_EXIT"
fi

echo ""
echo "--- Artifact Check ---"
LATEST=$(ls -t data/thinkboxmd/artifacts/box_mercury_live_*.json 2>/dev/null | head -1)
if [ -n "$LATEST" ]; then
    PROOF=$(python3 -c "
import json
d = json.load(open('$LATEST'))
print(d.get('proof_sha256', 'N/A')[:16])
" 2>/dev/null || echo "N/A")
    CALLS=$(python3 -c "
import json
d = json.load(open('$LATEST'))
print(d.get('global_calls', 0))
" 2>/dev/null || echo "?")
    ERRORS=$(python3 -c "
import json
d = json.load(open('$LATEST'))
agg = d.get('aggregate', {})
print(agg.get('total_errors', 0))
" 2>/dev/null || echo "?")

    echo "Artifact: $LATEST"
    echo "Proof: $PROOF"
    echo "Calls: $CALLS"
    echo "Errors: $ERRORS"
else
    echo "No artifact found"
fi

echo ""
echo "=== Demo complete ==="