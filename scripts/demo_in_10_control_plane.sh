#!/usr/bin/env bash
# KUDBEE Demo in 10 — Control Plane bound
#
# Usage: bash scripts/demo_in_10_control_plane.sh
#
# Steps:
#   1. Start mock vLLM on 127.0.0.1:8001
#   2. Run burst (mock, no GPU)
#   3. Harvest burst output (scores)
#   4. Write demo run record + emit proof bundle
#   5. Verify chain
#   6. Stop mock server
#
# No GPU. No public bind. No AWS. No secrets.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

MOCK_PID=""
CLEANUP_DONE=0

cleanup() {
    if [ "$CLEANUP_DONE" = "1" ]; then return; fi
    CLEANUP_DONE=1
    if [ -n "$MOCK_PID" ] && kill -0 "$MOCK_PID" 2>/dev/null; then
        echo ""
        echo "--- Stopping mock vLLM server (PID $MOCK_PID) ---"
        kill "$MOCK_PID" 2>/dev/null || true
        wait "$MOCK_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

echo "=== KUDBEE Demo in 10 — Control Plane ==="
echo ""

# ── Step 1: Start mock vLLM ──────────────────────────────────
echo "--- Step 1: Starting mock vLLM on 127.0.0.1:8001 ---"
python3 thinkbox/mock_vllm.py --host 127.0.0.1 --port 8001 &>/tmp/kudbee-mock.log &
MOCK_PID=$!
sleep 2

if ! curl -s -o /dev/null -w "" http://127.0.0.1:8001/health 2>/dev/null; then
    python3 -c "
import urllib.request, sys, time
for _ in range(10):
    try:
        urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=2)
        sys.exit(0)
    except Exception:
        time.sleep(0.5)
sys.exit(1)
" || {
        echo "ERROR: Mock vLLM server did not start. Check /tmp/kudbee-mock.log"
        exit 1
    }
fi
echo "Mock vLLM ready"
echo ""

# ── Step 2: Run burst ──────────────────────────────────────
echo "--- Step 2: Running burst --live --pairs 2 --minutes 1 --max-calls 8 --budget 1.0 ---"
echo "    Output: data/evals/burst-smoke"
echo ""
python3 -m thinkbox.burst \
    --live \
    --pairs 2 \
    --minutes 1 \
    --max-calls 8 \
    --budget 1.0 \
    --out data/evals/burst-smoke

BURST_EXIT=$?
echo ""
if [ "$BURST_EXIT" -ne 0 ]; then
    echo "WARNING: burst exited with code $BURST_EXIT"
fi
echo ""

# ── Step 3: Harvest/replay ─────────────────────────────────
echo "--- Step 3: Harvest/replay from data/evals/burst-smoke ---"
echo ""
python3 -m thinkbox.harvest --dir data/evals/burst-smoke
echo ""

# ── Step 4: Proof export ────────────────────────────────────
echo "--- Step 4: Writing demo run record + proof bundle ---"
echo ""
python3 -c "
import json
from pathlib import Path
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.export import export_proof_bundle
from thinkbox.agent.control_plane.verify_chain import verify_chain

store = ActionReceiptStore(':memory:')
from thinkbox.agent.control_plane.kernel_hooks import HookContext, on_admit

# Write demo run record as receipts
for i in range(3):
    on_admit(store, HookContext(
        agent_id='demo',
        action=f'burst-{i}',
        status='allowed',
        reason=f'burst call {i}',
        evidence_label='simulated',
        metadata={'phase': 'demo', 'index': i},
    ))

bundle = export_proof_bundle(store, output_dir='data/proofs/demo-001', prefix='demo')
result = verify_chain(store)

print(f'Run record: {store.count()} receipts')
print(f'Proof bundle: {bundle[\"jsonl\"]}')
print(f'Chain valid: {result.valid}')
print(f'Receipts: {result.receipts}')
" 2>&1 || true
echo ""

# ── Step 5: Verify chain ────────────────────────────────────
echo "--- Step 5: Chain verification ---"
echo ""
python3 -c "
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.verify_chain import verify_chain
import tempfile, os, sqlite3
path = os.path.join(tempfile.mkdtemp(), 'verify.db')
store = ActionReceiptStore(path)
from thinkbox.agent.control_plane.kernel_hooks import HookContext, on_admit
for i in range(2):
    on_admit(store, HookContext(agent_id='verify', action=f'check-{i}'))
result = verify_chain(store)
print(f'Chain valid: {result.valid}')
print(f'Receipts: {result.receipts}')
store.close()
" 2>&1 || true
echo ""

# ── Step 6: Summary ─────────────────────────────────────────
echo "--- Step 6: Summary ---"
echo ""
python3 -c "
import json
from pathlib import Path

burst_dir = Path('data/evals/burst-smoke')
files = sorted(burst_dir.glob('*.jsonl')) if burst_dir.exists() else []
total = 0
grounded = 0
ungrounded = 0
for f in files:
    for line in f.read_text().splitlines():
        if not line.strip(): continue
        r = json.loads(line)
        total += 1
        if r.get('variant') == 'grounded': grounded += 1
        elif r.get('variant') == 'ungrounded': ungrounded += 1

print(f'Burst records: {total}')
print(f'Grounded: {grounded}')
print(f'Ungrounded: {ungrounded}')
print(f'Proof dir: data/proofs/demo-001/')
" 2>/dev/null || true

echo ""
echo "=== Demo complete ==="
echo "Mock server will be stopped automatically."
