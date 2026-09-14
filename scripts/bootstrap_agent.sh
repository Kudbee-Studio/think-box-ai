#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/workspace/bcdfac4f-1903-4a17-8abf-0b10fd495578/sessions/agent_0c8313fa-a5aa-428f-929c-95a1f71a6876"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python3"

echo "=== KUDBEE Agent Bootstrap ==="
echo "Project: $PROJECT_ROOT"
echo "Interpreter: $VENV_PYTHON"

# 1. Verify runtime
if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: Virtual environment not found at $VENV_PYTHON"
    exit 1
fi

# 2. Verify dependencies
"$VENV_PYTHON" -c "
import fastapi, uvicorn, pytest, aiohttp, websockets
import thinkbox, core
print('✓ All dependencies verified')
" || { echo "ERROR: Missing dependencies"; exit 1; }

# 3. Verify MCP connectivity (best-effort)
echo "MCP Servers: GitHub, Context7 (configured via Kilo config)"

# 4. Verify environment variables (presence only)
for var in THINKBOX_DEFAULT_PROVIDER UPSTASH_VECTOR_REST_URL UPSTASH_PUBLIC_BOX_URL; do
    if [[ -n "${!var:-}" ]]; then
        echo "✓ $var available"
    else
        echo "⚠ $var not set"
    fi
done

# 5. Run regression test
"$VENV_PYTHON" -m pytest tests/unit/test_runtime_contract.py -v

echo "=== Bootstrap Complete ==="
echo "Ready to run experiment with: $VENV_PYTHON experiments/kudbee_orchestrator.py"
