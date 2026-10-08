#!/usr/bin/env bash
# kudbEE Agent OS installer for Linux and macOS (WSL works too). Checks node and git, installs dependencies, links the `kudbee` command, creates .env, runs the health check.
# `./install.sh --check` only reports whether this machine is ready and changes nothing.
set -euo pipefail
here="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
web="$here/apps/web"
need_major=22; need_minor=6

ok=1
if command -v node >/dev/null 2>&1; then
  v="$(node --version 2>/dev/null | sed 's/^v//')"
  major="${v%%.*}"; rest="${v#*.}"; minor="${rest%%.*}"
  if [ "${major:-0}" -gt "$need_major" ] || { [ "${major:-0}" -eq "$need_major" ] && [ "${minor:-0}" -ge "$need_minor" ]; }; then echo "node $v: ok"; else echo "node $v: too old, need 22.6 or newer (https://nodejs.org)"; ok=0; fi
else echo "node: not found, need 22.6 or newer (https://nodejs.org)"; ok=0; fi
if command -v git >/dev/null 2>&1; then echo "git $(git --version | awk '{print $3}'): ok"; else echo "git: not found (needed for repository features)"; ok=0; fi
if command -v npm >/dev/null 2>&1; then echo "npm $(npm --version): ok"; else echo "npm: not found"; ok=0; fi

if [ "$ok" -ne 1 ]; then echo "Not ready: fix the lines above and run again."; exit 1; fi
if [ "${1:-}" = "--check" ]; then echo "Ready to install."; exit 0; fi

echo "Installing dependencies..."
(cd "$web" && npm install --no-audit --no-fund)
mkdir -p "$HOME/.local/bin"
ln -sf "$web/bin/kudbee" "$HOME/.local/bin/kudbee"
echo "Linked kudbee into ~/.local/bin (add it to PATH if your shell does not find it)."
"$web/bin/kudbee" init
"$web/bin/kudbee" doctor || true
echo "Start the dashboard:  cd apps/web && npm start   then open http://localhost:3000"
