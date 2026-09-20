#!/usr/bin/env bash
# KUDBEE Demo in 10 — Agent control plane (60s path, hermetic subprocess).
#
# Usage: bash scripts/demo_in_10_agent_control_plane.sh
#
# Runs the agent control-plane demo in a fresh Python process so unittest
# discovery is never polluted by import-time grpc/protobuf stubs.
#
# No GPU. No public bind. No AWS. No secrets.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== KUDBEE Demo in 10 — Agent Control Plane (subprocess) ==="
echo ""

python3 -m thinkbox.agent.control_plane.demo

echo ""
echo "=== Subprocess demo complete ==="
