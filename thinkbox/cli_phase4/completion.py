"""Bash completion script generator (PR #196 F14)."""

from __future__ import annotations

PHASE3_SUBCOMMANDS = (
    "status",
    "profile",
    "format-demo",
    "workflow-run",
    "cassette-replay",
    "job",
    "tail",
    "plugins",
    "capabilities",
    "batch",
    "completion",
    "events-filter",
)


def bash_completion_script() -> str:
    subs = " ".join(PHASE3_SUBCOMMANDS)
    return f"""# KUDBEECLI Phase 4 bash completion (hermetic)
_thinkbox_cli3_completions() {{
  local cur prev
  cur="${{COMP_WORDS[COMP_CWORD]}}"
  prev="${{COMP_WORDS[COMP_CWORD-1]}}"
  if [[ ${{COMP_CWORD}} -eq 2 ]]; then
    COMPREPLY=( $(compgen -W "{subs}" -- "$cur") )
  fi
}}
complete -F _thinkbox_cli3_completions thinkbox
"""
