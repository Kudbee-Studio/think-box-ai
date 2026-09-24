#!/usr/bin/env python3
"""Hermetic quickstart for PR #200 environmental variables pack."""

from __future__ import annotations

import json

from thinkbox.env_vars.cassette import cassette_environ
from thinkbox.env_vars.hub import evaluate_env_pack, load_all_parsed


def main() -> None:
    environ = cassette_environ("valid_minimal.json")
    print(json.dumps(evaluate_env_pack(environ), indent=2, sort_keys=True))
    parsed = load_all_parsed(environ)
    print("parsed_keys:", sorted(parsed.keys()))


if __name__ == "__main__":
    main()
