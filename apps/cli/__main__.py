"""Allow running the CLI as a module: python -m apps.cli.dashboard"""

from apps.cli.dashboard import main

if __name__ == "__main__":
    raise SystemExit(main())
