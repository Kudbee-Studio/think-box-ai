"""Command-line interface for Think Box AI."""

from __future__ import annotations

import argparse

from think_box_ai import __version__, __token_symbol__


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="think-box-ai",
        description="Think Box AI — Think Token CLI",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--info", action="store_true", help="Show token info")
    args = parser.parse_args()

    if args.info:
        print(f"Token symbol : {__token_symbol__}")
        print(f"Version      : {__version__}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
