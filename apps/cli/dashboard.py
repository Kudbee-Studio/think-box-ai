"""KUDBEE Advanced CLI — Multi-panel terminal interface.

A professional terminal UI for managing AI agents, cloud infrastructure,
and the Think Token economy. Built with zero external dependencies.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from typing import Any


CLEAR_SCREEN = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
UNDERLINE = "\033[4m"

BLACK = "\033[30m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

BG_BLACK = "\033[40m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_MAGENTA = "\033[45m"
BG_CYAN = "\033[46m"

BORDER_COLOR = CYAN
TITLE_COLOR = YELLOW
SUCCESS_COLOR = GREEN
WARNING_COLOR = YELLOW
ERROR_COLOR = RED
INFO_COLOR = BLUE
ACCENT_COLOR = MAGENTA


@dataclass
class ServerInfo:
    """Simplified server info for display."""

    hostname: str
    plan: str
    state: str
    zone: str
    public_ips: list[str] = field(default_factory=list)
    has_gpu: bool = False
    gpu_info: str = ""

    @property
    def status_color(self) -> str:
        if self.state == "started":
            return SUCCESS_COLOR
        elif self.state == "maintenance":
            return WARNING_COLOR
        else:
            return ERROR_COLOR

    @property
    def primary_ip(self) -> str:
        return self.public_ips[0] if self.public_ips else "N/A"


@dataclass
class AgentInfo:
    """Agent status information."""

    name: str
    model: str
    status: str = "idle"
    tools: int = 0
    skills: int = 0
    tasks_completed: int = 0

    @property
    def status_color(self) -> str:
        if self.status == "active":
            return SUCCESS_COLOR
        elif self.status == "working":
            return WARNING_COLOR
        return DIM


@dataclass
class TokenInfo:
    """Think Token display info."""

    total_minted: int = 0
    avg_score: float = 0.0
    challenge_count: int = 0
    top_claim: str = ""


class TerminalUI:
    """Multi-panel terminal UI renderer."""

    def __init__(self) -> None:
        self._term_width = 80
        self._term_height = 24
        self._update_terminal_size()

    def _update_terminal_size(self) -> None:
        try:
            size = shutil.get_terminal_size((80, 24))
            self._term_width = size.columns
            self._term_height = size.lines
        except Exception:
            pass

    @property
    def width(self) -> int:
        return self._term_width

    @property
    def height(self) -> int:
        return self._term_height

    def clear(self) -> str:
        return CLEAR_SCREEN

    def _colorize(self, text: str, *codes: str) -> str:
        return "".join(codes) + text + RESET

    def _pad(self, text: str, width: int, align: str = "left") -> str:
        visible_len = len(self._strip_ansi(text))
        if visible_len >= width:
            return text[:width]
        padding = " " * (width - visible_len)
        if align == "right":
            return padding + text
        elif align == "center":
            left = (width - visible_len) // 2
            return " " * left + text + " " * (width - visible_len - left)
        return text + padding

    def _strip_ansi(self, text: str) -> str:
        import re
        return re.sub(r"\033\[[0-9;]*m", "", text)

    def _border_line(self, width: int, left: str = "│", right: str = "│") -> str:
        return self._colorize(left + "─" * (width - 2) + right, BORDER_COLOR)

    def _title_line(self, title: str, width: int) -> str:
        title_text = f" {title} "
        title_len = len(title_text)
        side = (width - 2 - title_len) // 2
        line = "─" * side + title_text + "─" * (width - 2 - side - title_len)
        return self._colorize("│" + line + "│", BORDER_COLOR)

    def render_header(self) -> str:
        lines = []
        w = self.width

        top = "┌" + "─" * (w - 2) + "┐"
        lines.append(self._colorize(top, BORDER_COLOR))

        title = "🐝 KUDBEE — Agent Execution Platform"
        subtitle = "Think Token Economy • Multi-Agent Orchestration • Cloud Infrastructure"

        lines.append(self._colorize("│", BORDER_COLOR) +
                     self._pad(self._colorize(title, BOLD, TITLE_COLOR), w - 2, "center") +
                     self._colorize("│", BORDER_COLOR))
        lines.append(self._colorize("│", BORDER_COLOR) +
                     self._pad(self._colorize(subtitle, DIM), w - 2, "center") +
                     self._colorize("│", BORDER_COLOR))

        bottom = "├" + "─" * (w - 2) + "┤"
        lines.append(self._colorize(bottom, BORDER_COLOR))

        return "\n".join(lines)

    def render_server_panel(self, servers: list[ServerInfo], width: int) -> str:
        lines = []
        inner_width = width - 2

        header = self._colorize("│", BORDER_COLOR) + \
                 self._colorize(" 🖥  SERVERS  ", BOLD, TITLE_COLOR) + \
                 self._pad("", inner_width - 14) + \
                 self._colorize("│", BORDER_COLOR)
        lines.append(header)

        sep = "├" + "─" * (width - 2) + "┤"
        lines.append(self._colorize(sep, BORDER_COLOR))

        if not servers:
            lines.append(self._colorize("│", BORDER_COLOR) +
                         self._pad(" No servers found", inner_width) +
                         self._colorize("│", BORDER_COLOR))
        else:
            for server in servers:
                status_dot = "●" if server.state == "started" else "○"
                line = f" {status_dot} {server.hostname:<25} {server.plan:<20} {server.zone:<8} {server.primary_ip}"
                colored_line = self._colorize(f" {status_dot} ", server.status_color) + \
                              f"{server.hostname:<25} {self._colorize(server.plan, DIM):<20} {server.zone:<8} {server.primary_ip}"
                lines.append(self._colorize("│", BORDER_COLOR) +
                             self._pad(colored_line, inner_width) +
                             self._colorize("│", BORDER_COLOR))
                if server.has_gpu:
                    gpu_line = f"   └─ GPU: {server.gpu_info}"
                    lines.append(self._colorize("│", BORDER_COLOR) +
                                 self._pad(self._colorize(gpu_line, ACCENT_COLOR), inner_width) +
                                 self._colorize("│", BORDER_COLOR))

        return "\n".join(lines)

    def render_agent_panel(self, agents: list[AgentInfo], width: int) -> str:
        lines = []
        inner_width = width - 2

        header = self._colorize("│", BORDER_COLOR) + \
                 self._colorize(" 🤖 AGENTS  ", BOLD, TITLE_COLOR) + \
                 self._pad("", inner_width - 12) + \
                 self._colorize("│", BORDER_COLOR)
        lines.append(header)

        sep = "├" + "─" * (width - 2) + "┤"
        lines.append(self._colorize(sep, BORDER_COLOR))

        if not agents:
            lines.append(self._colorize("│", BORDER_COLOR) +
                         self._pad(" No agents configured", inner_width) +
                         self._colorize("│", BORDER_COLOR))
        else:
            for agent in agents:
                status_dot = "●" if agent.status == "active" else "○"
                line = f" {status_dot} {agent.name:<15} {agent.model:<20} tools:{agent.tools} skills:{agent.skills}"
                colored_line = self._colorize(f" {status_dot} ", agent.status_color) + \
                              f"{agent.name:<15} {self._colorize(agent.model, DIM):<20} tools:{agent.tools} skills:{agent.skills}"
                lines.append(self._colorize("│", BORDER_COLOR) +
                             self._pad(colored_line, inner_width) +
                             self._colorize("│", BORDER_COLOR))

        return "\n".join(lines)

    def render_token_panel(self, tokens: TokenInfo, width: int) -> str:
        lines = []
        inner_width = width - 2

        header = self._colorize("│", BORDER_COLOR) + \
                 self._colorize(" 💰 THINK TOKENS  ", BOLD, TITLE_COLOR) + \
                 self._pad("", inner_width - 18) + \
                 self._colorize("│", BORDER_COLOR)
        lines.append(header)

        sep = "├" + "─" * (width - 2) + "┤"
        lines.append(self._colorize(sep, BORDER_COLOR))

        stats = f" Minted: {tokens.total_minted} │ Avg Score: {tokens.avg_score:.2f} │ Challenges: {tokens.challenge_count}"
        lines.append(self._colorize("│", BORDER_COLOR) +
                     self._pad(self._colorize(stats, SUCCESS_COLOR), inner_width) +
                     self._colorize("│", BORDER_COLOR))

        if tokens.top_claim:
            top = f" Top: {tokens.top_claim[:50]}"
            lines.append(self._colorize("│", BORDER_COLOR) +
                         self._pad(self._colorize(top, DIM), inner_width) +
                         self._colorize("│", BORDER_COLOR))

        return "\n".join(lines)

    def render_footer(self) -> str:
        w = self.width
        bottom = "└" + "─" * (w - 2) + "┘"
        return self._colorize(bottom, BORDER_COLOR)

    def render_status_bar(self, message: str = "") -> str:
        w = self.width
        timestamp = time.strftime("%H:%M:%S")
        status = f" {timestamp} │ {message or 'Ready'} "
        return self._colorize(self._pad(status, w, "left"), BG_BLUE, WHITE)

    def render_full(
        self,
        servers: list[ServerInfo],
        agents: list[AgentInfo],
        tokens: TokenInfo,
        status: str = "",
    ) -> str:
        self._update_terminal_size()
        w = self.width

        half_w = (w - 1) // 2

        lines = []
        lines.append(self.clear())
        lines.append(self.render_header())

        server_lines = self.render_server_panel(servers, half_w).split("\n")
        agent_lines = self.render_agent_panel(agents, w - half_w).split("\n")

        max_lines = max(len(server_lines), len(agent_lines))
        for i in range(max_lines):
            left = server_lines[i] if i < len(server_lines) else " " * half_w
            right = agent_lines[i] if i < len(agent_lines) else ""
            lines.append(left + right[len("│"):] if right else left)

        token_section = self.render_token_panel(tokens, w)
        lines.extend(token_section.split("\n"))

        lines.append(self.render_footer())
        lines.append(self.render_status_bar(status))

        return "\n".join(lines)


def get_sample_servers() -> list[ServerInfo]:
    """Get server list from UpCloud or return sample data."""
    try:
        from core.infrastructure import UpCloudClient
        client = UpCloudClient()
        raw_servers = client.list_servers()
        servers = []
        for s in raw_servers:
            has_gpu = "GPU" in s.plan
            gpu_info = ""
            if has_gpu:
                gpu_info = "2x NVIDIA L40S (48GB each)"
            servers.append(ServerInfo(
                hostname=s.hostname,
                plan=s.plan,
                state=s.state,
                zone=s.zone,
                public_ips=s.public_ips,
                has_gpu=has_gpu,
                gpu_info=gpu_info,
            ))
        return servers
    except Exception:
        return [
            ServerInfo("kudbee-host-v1", "4xCPU-8GB", "started", "fi-hel2", ["212.147.250.183"]),
            ServerInfo("firecracker-host", "8xCPU-128GB", "started", "us-chi1", ["152.44.35.44"]),
            ServerInfo("gpu-inference", "12xCPU-128GB-2xL40S", "started", "fi-hel2", ["87.58.149.32"], True, "2x L40S 48GB"),
        ]


def get_sample_agents() -> list[AgentInfo]:
    """Get sample agent data."""
    return [
        AgentInfo("kudbee-agent", "mercury-2", "active", 5, 3, 42),
        AgentInfo("researcher", "longcat-2.0", "idle", 8, 5, 0),
        AgentInfo("builder", "mercury-2", "working", 12, 7, 15),
    ]


def get_sample_tokens() -> TokenInfo:
    """Get sample token data."""
    return TokenInfo(
        total_minted=47,
        avg_score=1.85,
        challenge_count=142,
        top_claim="Firecracker VSOCK async execution boundary proven on cloudchamber",
    )


def main() -> int:
    """Run the KUDBEE CLI dashboard."""
    ui = TerminalUI()

    servers = get_sample_servers()
    agents = get_sample_agents()
    tokens = get_sample_tokens()

    try:
        output = ui.render_full(servers, agents, tokens, "Dashboard active — press Ctrl+C to exit")
        print(output, end="", flush=True)

        while True:
            time.sleep(1)
            servers = get_sample_servers()
            output = ui.render_full(servers, agents, tokens, "Dashboard active — press Ctrl+C to exit")
            print(output, end="", flush=True)

    except KeyboardInterrupt:
        print(SHOW_CURSOR + "\nGoodbye! 🐝")
        return 0


if __name__ == "__main__":
    sys.exit(main())
