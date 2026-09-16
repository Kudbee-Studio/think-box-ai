#!/usr/bin/env bash
# KUDBEE Demo in 10 — Run the full burst→harvest loop in under 10 minutes.
#
# Usage: bash scripts/demo_in_10.sh
#
# Steps:
#   1. Ensure dependencies are installed (pip install -e .)
#   2. Start mock vLLM server on 127.0.0.1:8001 (background)
#   3. Run burst --live --pairs 2 --minutes 1 --max-calls 8 --budget 1.0
#   4. Harvest/replay the burst output
#   5. Print groundedness / bind-failure / reasoning coverage
#   6. Stop mock server
#
# No public bind. No AWS GPU. No secrets.
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

echo "=== KUDBEE Demo in 10 ==="
echo ""

# ── Step 0: Check dependencies ────────────────────────────────────────
echo "--- Step 0: Checking dependencies ---"
if ! python3 -c "import thinkbox.burst" 2>/dev/null; then
    echo "Installing package..."
    pip install -e ".[dev]" -q 2>&1 | tail -3
fi
echo "Dependencies OK"
echo ""

# ── Step 1: Start mock vLLM ──────────────────────────────────────────
echo "--- Step 1: Starting mock vLLM on 127.0.0.1:8001 ---"
python3 thinkbox/mock_vllm.py --host 127.0.0.1 --port 8001 &>/tmp/kudbee-mock.log &
MOCK_PID=$!
sleep 2

if ! curl -s -o /dev/null -w "" http://127.0.0.1:8001/health 2>/dev/null; then
    # curl might not be available; try python
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

# ── Step 2: Run burst --live ──────────────────────────────────────────
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

# ── Step 3: Harvest/replay ──────────────────────────────────────────
echo "--- Step 3: Harvest/replay from data/evals/burst-smoke ---"
echo ""
python3 -m thinkbox.harvest --dir data/evals/burst-smoke
echo ""

# ── Step 4: Summary ──────────────────────────────────────────────────
echo "--- Step 4: Summary ---"
echo ""
python3 -c "
import json
from pathlib import Path

data_dir = Path('data/evals/burst-smoke')
files = sorted(data_dir.glob('*.jsonl'))
total_records = 0
grounded = 0
ungrounded = 0
reasoning = 0
pairs = set()

for f in files:
    for line in f.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        total_records += 1
        pairs.add(r.get('pair_id', ''))
        if r.get('variant') == 'grounded':
            grounded += 1
        elif r.get('variant') == 'ungrounded':
            ungrounded += 1
        meta = r.get('metadata', {})
        if meta.get('reasoning'):
            reasoning += 1

print(f'Files:          {len(files)}')
print(f'Records:        {total_records}')
print(f'Contrast pairs: {len(pairs)}')
print(f'Grounded:       {grounded}')
print(f'Ungrounded:     {ungrounded}')
print(f'Reasoning:      {reasoning}/{total_records} ({reasoning/max(total_records,1)*100:.0f}%)')
print(f'Bind failure:   {ungrounded - sum(1 for f in files for l in f.read_text().splitlines() if l.strip() and json.loads(l).get(\"variant\")==\"ungrounded\" and json.loads(l).get(\"grounded\",False))} incorrect')
" 2>/dev/null || true

echo ""
echo "=== Demo complete ==="
echo "Mock server will be stopped automatically."
