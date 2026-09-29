#!/usr/bin/env python3
"""
Verify the official UpCloud CLI (upctl) is installed and can authenticate.

Usage:
  python3 scripts/verify_upcloud_cli.py [--install]

Options:
  --install    Print official installation instructions if upctl is missing

Returns:
  0 - upctl installed and authenticated
  1 - upctl not installed (or not runnable)
  2 - upctl installed but not authenticated

Credentials (per the official upctl docs, any one of):
  UPCLOUD_TOKEN                       - API token (recommended)
  `upctl account login --with-token`  - saves the token to the system keyring
  ~/.config/upctl.yaml                - `token: ...` (or --config /path/to/upctl.yaml)
  UPCLOUD_USERNAME / UPCLOUD_PASSWORD - legacy username/password

  If UPCLOUD_TOKEN is unset but this repo's THINKBOX_UPCLOUD_API_TOKEN is set,
  it is passed to upctl as UPCLOUD_TOKEN for this check only. The value is never
  printed.

upctl is a Go binary. It is NOT on PyPI: `pip install upcloud-cli` fails, because
PyPI returns 404 for that project.

References:
  Source + releases: https://github.com/UpCloudLtd/upcloud-cli
  Docs:              https://upcloudltd.github.io/upcloud-cli/
"""

from __future__ import annotations

import os
import subprocess
import sys

REPO_TOKEN_VAR = "THINKBOX_UPCLOUD_API_TOKEN"

INSTALL_INSTRUCTIONS = """\
UpCloud CLI (upctl) installation -- official methods
(source: https://github.com/UpCloudLtd/upcloud-cli, docs/index.md)

upctl is a Go binary. There is no PyPI package, so do not use pip.

Ubuntu / Debian (.deb from GitHub releases):
  VER=<latest, see https://github.com/UpCloudLtd/upcloud-cli/releases>
  curl -Lo upcloud-cli_${VER}_amd64.deb \\
    https://github.com/UpCloudLtd/upcloud-cli/releases/download/v${VER}/upcloud-cli_${VER}_amd64.deb
  # verify against checksums.txt from the same release before installing
  sudo apt install ./upcloud-cli_${VER}_amd64.deb

No root: download upcloud-cli_${VER}_linux_x86_64.tar.gz from the same release,
  verify it against checksums.txt, extract, and put `upctl` on your PATH.

macOS (Homebrew tap):
  brew tap UpCloudLtd/tap
  brew install upcloud-cli

From source:
  go install github.com/UpCloudLtd/upcloud-cli/v3/...@latest

Verify the install:   upctl version

Authenticate (pick one):
  export UPCLOUD_TOKEN=...             # or rely on THINKBOX_UPCLOUD_API_TOKEN (see above)
  upctl account login --with-token     # saves to the system keyring

Verify API access:    upctl account show
"""


def upctl_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    """Environment for upctl subprocesses: map the repo token to UPCLOUD_TOKEN if needed."""
    env = dict(os.environ if environ is None else environ)
    if not env.get("UPCLOUD_TOKEN") and env.get(REPO_TOKEN_VAR):
        env["UPCLOUD_TOKEN"] = env[REPO_TOKEN_VAR]
    return env


def check_upctl_installed() -> bool:
    try:
        result = subprocess.run(["upctl", "version"], capture_output=True, text=True, timeout=10, check=False)
    except FileNotFoundError:
        print("❌ upctl not found in PATH")
        return False
    except subprocess.TimeoutExpired:
        print("❌ `upctl version` timed out")
        return False
    if result.returncode != 0:
        print(f"❌ `upctl version` exited {result.returncode}")
        return False
    first = (result.stdout.strip().splitlines() or ["(no output)"])[0]
    print(f"✅ upctl installed: {first}")
    return True


def check_upctl_authenticated(environ: dict[str, str] | None = None) -> bool:
    """Authentication is proven only by a successful `upctl account show`.

    No config-file check: upctl may authenticate from UPCLOUD_TOKEN, the system
    keyring, or ~/.config/upctl.yaml, and any of them is valid.
    """
    env = upctl_env(environ)
    source = (
        "UPCLOUD_TOKEN"
        if (environ if environ is not None else os.environ).get("UPCLOUD_TOKEN")
        else (f"{REPO_TOKEN_VAR} (mapped to UPCLOUD_TOKEN)" if env.get("UPCLOUD_TOKEN") else "upctl config/keyring")
    )
    try:
        result = subprocess.run(
            ["upctl", "account", "show"], capture_output=True, text=True, timeout=20, env=env, check=False
        )
    except subprocess.TimeoutExpired:
        print("❌ `upctl account show` timed out (network?)")
        return False
    if result.returncode != 0:
        print(f"❌ `upctl account show` failed (credential source: {source})")
        print(f"   {result.stderr.strip()[:160]}")
        return False
    print(f"✅ upctl authenticated (credential source: {source})")
    for line in result.stdout.splitlines():
        if line.strip().lower().startswith(("username", "credits")):
            print(f"   {line.strip()}")
    return True


def verify_upctl(environ: dict[str, str] | None = None) -> int:
    if not check_upctl_installed():
        print("ℹ️  Run with --install for official installation instructions (upctl is not a pip package)")
        return 1
    if not check_upctl_authenticated(environ):
        print("ℹ️  Set UPCLOUD_TOKEN (or THINKBOX_UPCLOUD_API_TOKEN), or run: upctl account login --with-token")
        return 2
    print("✅ UpCloud CLI is ready")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    code = verify_upctl()
    if code != 0 and "--install" in args:
        print()
        print(INSTALL_INSTRUCTIONS)
    return code


if __name__ == "__main__":
    sys.exit(main())
