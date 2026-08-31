
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

    _arguments         '1: :->command'         '2: :->subcommand'

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
