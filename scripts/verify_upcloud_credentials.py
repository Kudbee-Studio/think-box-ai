#!/usr/bin/env python3
"""
Verify UpCloud API credentials are valid (read-only test).

Usage:
  python3 scripts/verify_upcloud_credentials.py

Returns:
  0 - Credentials valid and API responsive
  1 - Credentials missing or invalid
  2 - API unreachable or other error

Environment:
  THINKBOX_UPCLOUD_API_TOKEN - Required (Bearer token for UpCloud API)
  UPCLOUD_API - Alternative (deprecated, falls back to THINKBOX_UPCLOUD_API_TOKEN)

Security:
  - No credentials printed to stdout
  - No .env file read (env vars only)
  - Read-only API call (GET /account)
  - Exit code only indicates success/failure
  - Errors logged but sanitized (no token values)
"""

import sys
import os
import json
from pathlib import Path


def verify_upcloud_credentials():
    """Test UpCloud API credentials with safe read-only call."""

    # Load token from environment (never from .env directly)
    token = os.environ.get('THINKBOX_UPCLOUD_API_TOKEN') or os.environ.get('UPCLOUD_API')

    if not token:
        print("❌ UPCLOUD_API_TOKEN not found in environment")
        print("   Set THINKBOX_UPCLOUD_API_TOKEN or UPCLOUD_API")
        return 1

    # No part of the token is printed, not even a prefix or suffix (AGENTS.md 0.4).
    print(f"🔐 Token loaded ({len(token)} characters)")

    # Attempt safe read-only API call
    try:
        import urllib.request
        import urllib.error

        url = "https://api.upcloud.com/1.3/account"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        print(f"📡 Testing API connectivity to {url}")

        request = urllib.request.Request(url, headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=10)
            data = json.loads(response.read().decode())

            # Extract account info (safe to log)
            account_info = data.get('account', {})
            username = account_info.get('username', 'unknown')
            credits = account_info.get('credits', 'unknown')

            print(f"✅ UpCloud API connection successful")
            print(f"   Account: {username}")
            print(f"   Credits: {credits} USD")
            print(f"   Status: ACTIVE")
            return 0

        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(f"❌ Authentication failed (HTTP 401)")
                print(f"   Token is invalid or expired")
                return 1
            elif e.code == 403:
                print(f"❌ Authorization failed (HTTP 403)")
                print(f"   Token lacks required permissions")
                return 1
            else:
                print(f"❌ API error (HTTP {e.code})")
                print(f"   Response: {e.reason}")
                return 2

        except urllib.error.URLError as e:
            print(f"❌ Network error: {e.reason}")
            print(f"   Check internet connection or firewall rules")
            return 2

    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}")
        print(f"   {str(e)[:80]}")  # Truncate error for safety
        return 2


def main():
    """Run verification."""
    print("\n" + "="*60)
    print("UpCloud API Credential Verification")
    print("="*60 + "\n")

    exit_code = verify_upcloud_credentials()

    print("\n" + "="*60)
    if exit_code == 0:
        print("✅ Credentials valid. Ready for UpCloud operations.")
    elif exit_code == 1:
        print("❌ Credentials invalid. Check environment variables.")
    else:
        print("❌ API unreachable. Check network and firewall.")
    print("="*60 + "\n")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
