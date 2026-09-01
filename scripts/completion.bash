#!/bin/bash
# Bash completion for Think Box CLI
# Source this file: source scripts/completion.bash

_thinkbox_completion() {
    local cur prev commands
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    commands="job memory cursor inception queue spawn config findings doctor init watch serve"

    case ${COMP_CWORD} in
        1)
            COMPREPLY=($(compgen -W "${commands}" -- ${cur}))
            ;;
        2)
            case ${prev} in
                job)
                    COMPREPLY=($(compgen -W "list show create submit run cancel retry diff" -- ${cur}))
                    ;;
                memory)
                    COMPREPLY=($(compgen -W "remember recall search context list forget" -- ${cur}))
                    ;;
                cursor)
                    COMPREPLY=($(compgen -W "run list logs" -- ${cur}))
                    ;;
                inception)
                    COMPREPLY=($(compgen -W "run models usage" -- ${cur}))
                    ;;
                queue)
                    COMPREPLY=($(compgen -W "status add batch drain" -- ${cur}))
                    ;;
                spawn)
                    COMPREPLY=($(compgen -W "researcher runner" -- ${cur}))
                    ;;
                config)
                    COMPREPLY=($(compgen -W "show set profile" -- ${cur}))
                    ;;
                findings)
                    COMPREPLY=($(compgen -W "list show preview" -- ${cur}))
                    ;;
            esac
            ;;
    esac
}

complete -F _thinkbox_completion thinkbox
