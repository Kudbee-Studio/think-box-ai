#!/usr/bin/env python3
"""
Verify UpCloud CLI (upctl) is installed and configured correctly.

Usage:
  python3 scripts/verify_upcloud_cli.py [--install]

Options:
  --install    Provide installation instructions if upctl is missing

Returns:
  0 - upctl installed and configured
  1 - upctl not installed or misconfigured
  2 - upctl installed but no valid credentials

Environment:
  THINKBOX_UPCLOUD_API_TOKEN - UpCloud API token (optional; upctl can load from ~/.upcloud/config)

References:
  Official CLI: https://upcloudltd.github.io/upcloud-cli/latest/
  Installation: https://upcloudltd.github.io/upcloud-cli/latest/install/
"""

import sys
import os
import subprocess
import json
from pathlib import Path


def check_upctl_installed():
    """Check if upctl is installed and accessible."""
    try:
        result = subprocess.run(
            ["upctl", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip().split('\n')[0]
            print(f"✅ upctl installed: {version}")
            return True
        else:
            print(f"❌ upctl not working (exit code {result.returncode})")
            return False
    except FileNotFoundError:
        print("❌ upctl not found in PATH")
        return False
    except subprocess.TimeoutExpired:
        print("❌ upctl command timed out")
        return False
    except Exception as e:
        print(f"❌ Error checking upctl: {e}")
        return False


def check_upctl_config():
    """Check if upctl has valid configuration."""
    config_path = Path.home() / ".upcloud" / "config"

    if not config_path.exists():
        print(f"⚠️  No UpCloud config found at {config_path}")
        print("   Run: upctl account show  (will create config)")
        return False

    print(f"✅ Config exists: {config_path}")

    # Try to run a simple read-only command
    try:
        result = subprocess.run(
            ["upctl", "account", "show"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            print("✅ upctl authenticated and responsive")
            # Parse output for account info (safe to log)
            for line in result.stdout.split('\n'):
                if 'username' in line.lower() or 'credits' in line.lower():
                    print(f"   {line.strip()}")
            return True
        else:
            print(f"❌ upctl command failed: {result.stderr[:100]}")
            return False

    except subprocess.TimeoutExpired:
        print("❌ upctl account show timed out (network issue?)")
        return False
    except Exception as e:
        print(f"❌ Error testing upctl: {e}")
        return False


def print_install_instructions():
    """Print installation instructions for upctl."""
    print("\n" + "="*60)
    print("UpCloud CLI (upctl) Installation")
    print("="*60 + "\n")

    print("Option 1: Using pip (Recommended)")
    print("-" * 40)
    print("""
  python3 -m pip install upcloud-cli

  Then authenticate:
  upctl account show

  This will prompt for API username/password and save to ~/.upcloud/config
    """)

    print("\nOption 2: Using system package manager")
    print("-" * 40)
    print("""
  macOS:
    brew install upcloud-cli

  Linux (Debian/Ubuntu):
    sudo apt-get install upcloud-cli

  See: https://upcloudltd.github.io/upcloud-cli/latest/install/
    """)

    print("\nOption 3: From source")
    print("-" * 40)
    print("""
  git clone https://github.com/UpCloudLtd/upcloud-cli.git
  cd upcloud-cli
  python3 -m pip install -e .
    """)

    print("\nAfter installation:")
    print("-" * 40)
    print("""
  1. Authenticate:
     upctl account show

  2. Test credentials:
     python3 scripts/verify_upcloud_cli.py

  3. Common commands:
     upctl server list          # List all servers
     upctl server show <uuid>   # Show server details
     upctl price list           # Show current pricing
    """)

    print("="*60 + "\n")


def verify_upctl():
    """Full verification of upctl setup."""

    print("\n" + "="*60)
    print("UpCloud CLI (upctl) Verification")
    print("="*60 + "\n")

    # Step 1: Check if upctl is installed
    if not check_upctl_installed():
        print("\nℹ️  upctl not installed. Run: pip install upcloud-cli")
        return 1

    print()

    # Step 2: Check configuration
    if not check_upctl_config():
        print("\nℹ️  Run: upctl account show  (to create config)")
        return 2

    print("\n" + "="*60)
    print("✅ UpCloud CLI is ready for use")
    print("="*60 + "\n")

    print("Next steps:")
    print("  upctl server list      # List all servers")
    print("  upctl server show <id> # Get server details")
    print("  upctl price list       # Show pricing")
    print("\n")

    return 0


def main():
    """Run verification."""
    show_install = "--install" in sys.argv

    exit_code = verify_upctl()

    if exit_code != 0 and show_install:
        print_install_instructions()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
