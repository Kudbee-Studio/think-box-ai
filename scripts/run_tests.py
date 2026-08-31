#!/usr/bin/env python3
"""Test runner that works without pytest. Uses unittest."""

import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def discover_tests() -> unittest.TestSuite:
    """Discover all tests in tests/ directory."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_dir = REPO_ROOT / "tests"
    if not test_dir.exists():
        return suite

    # Add root to path for imports
    sys.path.insert(0, str(REPO_ROOT))

    for test_file in test_dir.rglob("test_*.py"):
        # Convert path to module name
        rel = test_file.relative_to(REPO_ROOT)
        module_name = str(rel).replace("/", ".").replace(".py", "")
        try:
            spec = __import__(module_name, fromlist=[""])
            suite.addTests(loader.loadTestsFromModule(spec))
        except Exception as e:
            print(f"  WARN: Could not load {module_name}: {e}")

    return suite


def main() -> int:
    """Run all tests."""
    print("=" * 60)
    print("Think Box AI — Test Runner")
    print("=" * 60)

    suite = discover_tests()
    if suite.countTestCases() == 0:
        print("No tests found.")
        return 0

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    if result.wasSuccessful():
        print(f"  PASS: {result.testsRun} tests")
        return 0
    else:
        print(f"  FAIL: {len(result.failures)} failures, {len(result.errors)} errors")
        return 1


if __name__ == "__main__":
    sys.exit(main())
