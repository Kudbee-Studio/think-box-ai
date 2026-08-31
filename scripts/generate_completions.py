#!/usr/bin/env python3
"""Generate shell completion scripts for Think Box CLI."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


BASH_COMPLETION = '''
_thinkbox_completion() {
    local cur prev commands
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    commands="job findings config box serve watch"

    case ${COMP_CWORD} in
        1)
            COMPREPLY=($(compgen -W "${commands}" -- ${cur}))
            ;;
        2)
            case ${prev} in
                job)
                    COMPREPLY=($(compgen -W "list show submit queue diff run" -- ${cur}))
                    ;;
                findings)
                    COMPREPLY=($(compgen -W "list show preview" -- ${cur}))
                    ;;
                config)
                    COMPREPLY=($(compgen -W "show set" -- ${cur}))
                    ;;
                box)
                    COMPREPLY=($(compgen -W "status health" -- ${cur}))
                    ;;
            esac
            ;;
    esac
}

complete -F _thinkbox_completion thinkbox
'''

ZSH_COMPLETION = '''
#compdef thinkbox

_thinkbox() {
    local -a commands
    commands=(
        'job:Job management'
        'findings:Findings browser'
        'config:Configuration'
        'box:Upstash box'
        'serve:Start backend'
        'watch:Live monitoring'
    )

    _arguments \
        '1: :->command' \
        '2: :->subcommand'

    case $state in
        command)
            _describe 'commands' commands
            ;;
        subcommand)
            case $words[1] in
                job)
                    _values 'job commands' 'list' 'show' 'submit' 'queue' 'diff' 'run'
                    ;;
                findings)
                    _values 'findings commands' 'list' 'show' 'preview'
                    ;;
                config)
                    _values 'config commands' 'show' 'set'
                    ;;
                box)
                    _values 'box commands' 'status' 'health'
                    ;;
            esac
            ;;
    esac
}

_thinkbox "$@"
'''


def main():
    out_dir = REPO_ROOT / "scripts" / "completions"
    out_dir.mkdir(exist_ok=True)

    (out_dir / "thinkbox.bash").write_text(BASH_COMPLETION)
    (out_dir / "thinkbox.zsh").write_text(ZSH_COMPLETION)

    print(f"Completions written to {out_dir}")
    print("  thinkbox.bash — source in .bashrc")
    print("  thinkbox.zsh — source in .zshrc")


if __name__ == "__main__":
    main()
