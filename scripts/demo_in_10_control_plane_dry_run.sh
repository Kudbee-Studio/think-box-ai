#!/usr/bin/env bash
# KUDBEE Demo in 10 — Control plane dry-run (#106–#109 stack, hermetic).
#
# Usage: bash scripts/demo_in_10_control_plane_dry_run.sh
#
# Proves: org-memory receipts → AdmissionGate → signed webhook → pipeline
# dashboard rollups → founder-gated request-merge (never GitHub merge).
#
# No AWS / Upstash / UpCloud / GPU. No secrets in repo. No LIVE_VERIFIED claim.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== KUDBEE Demo in 10 — Control Plane Dry Run ==="
echo ""

python3 -m thinkbox.control_plane_dry_run
