"""KUDBEECLI Phase 2 — local REPL (hermetic inspect commands; live gated)."""

from __future__ import annotations

import shlex
import sys
from typing import Any, Callable

from thinkbox.cli_inspect import CLI_EXIT_FAIL, CLI_EXIT_OK, CLI_EXIT_USAGE

_LIVE_COMMANDS = frozenset({"live", "swarm-live", "run-live"})


class CliShell:
    """Minimal readline-free REPL for inspection subcommands."""

    def __init__(
        self,
        execute_line: Callable[[list[str]], int],
        *,
        input_stream: Any = None,
        output_stream: Any = None,
    ) -> None:
        self._execute = execute_line
        self._in = input_stream or sys.stdin
        self._out = output_stream or sys.stdout

    def run(self, max_lines: int = 0) -> int:
        """Run until EOF, ``exit``, or ``max_lines`` reached."""
        self._out.write("thinkbox shell (local inspect; type 'help')\n")
        lines = 0
        while True:
            if max_lines and lines >= max_lines:
                return CLI_EXIT_OK
            try:
                self._out.write("thinkbox> ")
                self._out.flush()
                raw = self._in.readline()
            except (EOFError, KeyboardInterrupt):
                self._out.write("\n")
                return CLI_EXIT_OK
            if raw == "":
                return CLI_EXIT_OK
            line = raw.strip()
            if not line:
                continue
            lines += 1
            code = self.handle_line(line)
            if code == CLI_EXIT_OK and line.split()[0].lower() in ("exit", "quit"):
                return CLI_EXIT_OK
            if code == CLI_EXIT_USAGE and line.split()[0].lower() == "exit":
                return CLI_EXIT_OK

    def handle_line(self, line: str) -> int:
        parts = shlex.split(line)
        if not parts:
            return CLI_EXIT_OK
        cmd = parts[0].lower()
        if cmd in ("exit", "quit"):
            return CLI_EXIT_OK
        if cmd == "help":
            self._out.write(
                "Commands: help, exit, env status, ledger verify, proof check PATH,\n"
                "  swarm agents|status, swarm live (gate only), dashboard status,\n"
                "  identity list, trace list, persist status\n"
            )
            return CLI_EXIT_OK
        if cmd in _LIVE_COMMANDS or (cmd == "swarm" and len(parts) > 1 and parts[1].lower() == "live"):
            return self._execute(parts if cmd != "swarm" else parts)
        return self._execute(parts)
