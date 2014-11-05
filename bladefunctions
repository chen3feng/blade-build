#!/bin/bash
# some useful blade shell functions
# usage:
# source this file in your ~/.bashrc, for example:
# test -s ~/bin/bladefunctions && . ~/bin/bladefunctions || true

_find_project_root ()
{
    local dir
    dir=$PWD;
    while [ "$dir" != "/" ]; do
        if [ -f "$dir/BLADE_ROOT" ]; then
            echo "$dir"
            return 0
        fi;
        dir=`dirname "$dir"`
    done
    return 1
}

_BUILD_DIR_PATTERN="blade-bin|(build(32|64)_(debug|release))"

# cd to build directory
function cddst()
{
    local root
    local relpath
    if root=`_find_project_root`; then
        if ! [[ "$PWD" =~ $_BUILD_DIR_PATTERN ]]; then
            if relpath=$(pwd | sed "s|^$root||"); then
                cd `readlink $root/blade-bin`/$relpath
                return $?
            fi
        fi
    fi
    return 1
}

# cd to source directory
function cdsrc()
{
    local root
    local relpath
    local sed_r_option

    if [[ "$OSTYPE" == "linux"* ]]; then
        sed_r_option='-r'
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        sed_r_option='-E'
    fi
    if root=`_find_project_root`; then
        if [[ "$PWD" =~ $_BUILD_DIR_PATTERN ]]; then
            if relpath=$(pwd | sed $sed_r_option -e "s%^$root/($_BUILD_DIR_PATTERN)%%"); then
                cd $root/$relpath
                return $?
            fi
        fi
    fi
    return 1
}

function alt()
{
    if ! cdsrc; then cddst; fi
}

alias a=alt


# @() pattern match require this
shopt -s extglob progcomp

_blade()
{
    local cur cmds cmdOpts optsParam opt
    local optBase i

    COMPREPLY=()
    cur=${COMP_WORDS[COMP_CWORD]}

    # Possible expansions, without unambiguous abbreviations such as "up".
    cmds='build test clean run query'

    if [[ $COMP_CWORD -eq 1 ]] ; then
        COMPREPLY=( $( compgen -W "$cmds" -- $cur ) )
        return 0
    fi

    commonOpts="--color --profile --generate-dynamic --no-test --help -pdebug \
                -prelease -m32 -m64 --verbose"
    buildOpts="$commonOpts --gcov --gprof --generate-java --generate-php"

    # possible options for the command
    cmdOpts=
    case ${COMP_WORDS[1]} in
    build)
        cmdOpts="$commonOpts"
        ;;
    test)
        cmdOpts="$commonOpts --full-test --test-jobs -t"
        ;;
    clean)
        cmdOpts="$commonOpts"
        ;;
    query)
        cmdOpts="$commonOpts --deps --dependeds"
        ;;
    *)
        ;;
    esac

    # take out options already given
    for ((i=2; i<=$COMP_CWORD-1; ++i)) ; do
        opt=${COMP_WORDS[$i]}

        case $opt in
        --*)    optBase=${opt/=*/} ;;
        -*)     optBase=${opt:0:2} ;;
        esac

        cmdOpts=" $cmdOpts "
        cmdOpts=${cmdOpts/ ${optBase} / }

        # skip next option if this one requires a parameter
        if [[ $opt == @($optsParam) ]] ; then
            ((++i))
        fi
    done

    COMPREPLY=($(compgen -d -W "$cmdOpts" -- $cur | grep -v '.svn'))

    return 0
}

complete -F _blade -o default blade

