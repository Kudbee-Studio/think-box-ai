#!/usr/bin/env bash
# Run PR #185 Think Job lifecycle fix pack locally (hermetic; no live Mercury).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONUNBUFFERED=1
python3 -m thinkbox.think_job_lifecycle_fixes.local "$@"
