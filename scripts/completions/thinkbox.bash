
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
