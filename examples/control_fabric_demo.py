#!/usr/bin/env python3
"""KUDBEE control fabric demo — governance admission in one script.

Run:
    python3 examples/control_fabric_demo.py

Prints whether an agent is admitted to execute, then a denial path.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from thinkbox.governed import GovernedEngine, GovernedEngineConfig
from thinkbox.engine import EngineConfig, ThinkBoxEngine


def main() -> None:
    governed = GovernedEngine(
        GovernedEngineConfig(
            engine=ThinkBoxEngine(EngineConfig()),
            ledger_path=str(Path(":memory:")),
        )
    )

    token = governed.register_agent("alice", ["file:read", "goal:execute"])

    # Denied: valid token but missing capability for this request.
    denied = asyncio.run(
        governed.execute_goal("write to disk", token_value=token, agent_id="alice", capability="file:write")
    )
    print(f"Denied:   governed={denied['governed']}, reason={denied.get('reason')}")

    # Allowed: agent has goal:execute capability and a valid token.
    result = asyncio.run(
        governed.execute_goal("say hello", token_value=token, agent_id="alice", capability="goal:execute")
    )
    print(f"Allowed:  governed={result.get('governed')}")

    entries = governed.ledger.entries()
    print(f"Ledger:   {len(entries)} side-effect records, chain valid={governed.ledger.verify()}")


if __name__ == "__main__":
    main()