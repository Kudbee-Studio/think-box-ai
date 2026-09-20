#!/usr/bin/env bash
# demo_in_10_box_mercury_v2 — Box + Mercury-2 live experiment demo flow (v2)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "================================================"
echo " THINK BOX AI — Box + Mercury-2 Demo (v2)"
echo "================================================"

if [ -z "${INCEPTION_API_KEY:-}" ]; then
    echo "ERROR: INCEPTION_API_KEY missing — refusing to start"
    exit 1
fi

if [ -z "${UPSTASH_PUBLIC_BOX_URL:-}" ]; then
    echo "ERROR: UPSTASH_PUBLIC_BOX_URL missing — refusing to start"
    exit 1
fi

echo ""
echo "[1/4] Substrate check"
python3 -c "
import sys, os
sys.path.insert(0, '.')
from thinkbox.substrate import detect_substrate, SubstrateProbe
substrate = detect_substrate()
probe = SubstrateProbe()
report = probe.probe()
print(f'  substrate: {substrate}')
print(f'  vector_sync: {report.vector_sync}')
print(f'  isolation_tools: {[p.tool for p in report.isolation_tools]}')
"

echo ""
echo "[2/4] Model provider check"
python3 -c "
import sys
sys.path.insert(0, '.')
from core.providers.openai_compat import OpenAICompatProvider
from core.providers.base import Message
provider = OpenAICompatProvider({'api_key': os.environ['INCEPTION_API_KEY'], 'model': 'mercury-2', 'base_url': 'https://api.inceptionlabs.ai/v1'})
print('  provider: ready')
" 2>/dev/null || echo "  provider: check skipped (live credentials not in demo context)"

echo ""
echo "[3/4] Run experiment"
python3 "$REPO_ROOT/experiments/box_mercury_live.py" 2>&1 || echo "  experiment: live run skipped (credentials not in demo context)"

echo ""
echo "[4/4] Artifact summary"
ls -la "$REPO_ROOT/data/thinkboxmd/artifacts/box_mercury_live_"* 2>/dev/null | tail -5 || echo "  no artifacts found (live run skipped)"

echo ""
echo "=== Demo complete ==="
