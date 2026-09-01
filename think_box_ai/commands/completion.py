"""Shell completion command."""

from __future__ import annotations

from ..ui.colors import bold, cyan, dim, green, yellow
from ..utils.output import is_json_mode, output_json


COMPLETION_SCRIPTS = {
    "bash": """# thinkbox bash completion
_thinkbox_completions() {
    local cur prev commands
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    commands="job memory config findings queue spawn doctor init serve watch search export import logs history completion status repl cursor inception"
    
    case "${COMP_CWORD}" in
        1)
            COMPREPLY=($(compgen -W "${commands}" -- "${cur}"))
            ;;
        2)
            case "${prev}" in
                job) COMPREPLY=($(compgen -W "list show create submit run cancel retry diff" -- "${cur}"));;
                memory) COMPREPLY=($(compgen -W "remember recall search context list forget" -- "${cur}"));;
                config) COMPREPLY=($(compgen -W "show set profile" -- "${cur}"));;
                findings) COMPREPLY=($(compgen -W "list show preview" -- "${cur}"));;
                queue) COMPREPLY=($(compgen -W "status add batch drain" -- "${cur}"));;
                spawn) COMPREPLY=($(compgen -W "researcher runner" -- "${cur}"));;
                cursor) COMPREPLY=($(compgen -W "run list logs" -- "${cur}"));;
                inception) COMPREPLY=($(compgen -W "run models usage" -- "${cur}"));;
            esac
            ;;
    esac
}

complete -F _thinkbox_completions thinkbox
""",
    "zsh": """#compdef thinkbox
# thinkbox zsh completion

_thinkbox() {
    local curcontext="$curcontext" state line
    typeset -A opt_args

    _arguments -C \
        '1: :->command' \
        '2: :->subcommand' \
        '*: :->args'

    case "$state" in
        command)
            _values 'commands' \
                'job[Job management]' \
                'memory[Project memory]' \
                'config[Configuration]' \
                'findings[Findings browser]' \
                'queue[GPU queue]' \
                'spawn[Spawn agents]' \
                'doctor[System diagnostics]' \
                'init[Initialize project]' \
                'serve[Start server]' \
                'watch[Watch files]' \
                'search[Full-text search]' \
                'export[Export data]' \
                'import[Import data]' \
                'logs[View logs]' \
                'history[Command history]' \
                'completion[Shell completion]' \
                'status[System status]' \
                'repl[Interactive REPL]' \
                'cursor[Cursor SDK]' \
                'inception[Inception API]'
            ;;
        subcommand)
            case "$line[1]" in
                job) _values 'subcommands' 'list' 'show' 'create' 'submit' 'run' 'cancel' 'retry' 'diff';;
                memory) _values 'subcommands' 'remember' 'recall' 'search' 'context' 'list' 'forget';;
                config) _values 'subcommands' 'show' 'set' 'profile';;
                findings) _values 'subcommands' 'list' 'show' 'preview';;
                queue) _values 'subcommands' 'status' 'add' 'batch' 'drain';;
                spawn) _values 'subcommands' 'researcher' 'runner';;
                cursor) _values 'subcommands' 'run' 'list' 'logs';;
                inception) _values 'subcommands' 'run' 'models' 'usage';;
            esac
            ;;
    esac
}

_thinkbox "$@"
""",
    "fish": """# thinkbox fish completion
complete -c thinkbox -f

# Main commands
complete -c thinkbox -n '__fish_use_subcommand' -a 'job' -d 'Job management'
complete -c thinkbox -n '__fish_use_subcommand' -a 'memory' -d 'Project memory'
complete -c thinkbox -n '__fish_use_subcommand' -a 'config' -d 'Configuration'
complete -c thinkbox -n '__fish_use_subcommand' -a 'findings' -d 'Findings browser'
complete -c thinkbox -n '__fish_use_subcommand' -a 'queue' -d 'GPU queue'
complete -c thinkbox -n '__fish_use_subcommand' -a 'spawn' -d 'Spawn agents'
complete -c thinkbox -n '__fish_use_subcommand' -a 'doctor' -d 'System diagnostics'
complete -c thinkbox -n '__fish_use_subcommand' -a 'init' -d 'Initialize project'
complete -c thinkbox -n '__fish_use_subcommand' -a 'serve' -d 'Start server'
complete -c thinkbox -n '__fish_use_subcommand' -a 'watch' -d 'Watch files'
complete -c thinkbox -n '__fish_use_subcommand' -a 'search' -d 'Full-text search'
complete -c thinkbox -n '__fish_use_subcommand' -a 'export' -d 'Export data'
complete -c thinkbox -n '__fish_use_subcommand' -a 'import' -d 'Import data'
complete -c thinkbox -n '__fish_use_subcommand' -a 'logs' -d 'View logs'
complete -c thinkbox -n '__fish_use_subcommand' -a 'history' -d 'Command history'
complete -c thinkbox -n '__fish_use_subcommand' -a 'completion' -d 'Shell completion'
complete -c thinkbox -n '__fish_use_subcommand' -a 'status' -d 'System status'
complete -c thinkbox -n '__fish_use_subcommand' -a 'repl' -d 'Interactive REPL'
complete -c thinkbox -n '__fish_use_subcommand' -a 'cursor' -d 'Cursor SDK'
complete -c thinkbox -n '__fish_use_subcommand' -a 'inception' -d 'Inception API'

# Job subcommands
complete -c thinkbox -n '__fish_seen_subcommand_from job; and not __fish_seen_subcommand_from list show create submit run cancel retry diff' \\
    -a 'list show create submit run cancel retry diff'

# Memory subcommands
complete -c thinkbox -n '__fish_seen_subcommand_from memory; and not __fish_seen_subcommand_from remember recall search context list forget' \\
    -a 'remember recall search context list forget'
""",
}


def handle_completion(args) -> None:
    shell = args.shell

    if shell not in COMPLETION_SCRIPTS:
        print(yellow(f"  Unsupported shell: {shell}"))
        return

    script = COMPLETION_SCRIPTS[shell]

    if is_json_mode():
        output_json({"shell": shell, "script": script})
        return

    print(bold(f"\n  {shell.title()} Completion Script:"))
    print(dim("  " + "─" * 50))
    print(f"\n{script}")
    print(dim(f"  Save to your shell's completion directory or source directly."))
