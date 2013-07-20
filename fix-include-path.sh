#! /bin/bash

# source file types, you may need to change it, using regex
SOURCE_TYPES=".*[.]\(c\|h\|cc\|hh\|cpp\|hpp\)$"

CONVERT_LOG="convert.log"
SKIP_LOG="skip.log"
WARNING_LOG="warning.log"

function _warning()
{
    if [ -t 2 ]; then
        echo -e "\033[1;33m$@\033[m" >&2
    else
        echo -e "$@" >&2
    fi
}

function _info()
{
    if [ -t 2 ]; then
        echo -e "\033[1;36m$@\033[m" >&2
    else
        echo -e "$@" >&2
    fi
}

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

absolute_path()
{
    dir=`dirname $1`
    base=`basename $1`
    if [[ $base == '.' || $base == '/' ]] ; then
        echo `cd $dir; pwd`
    else
        echo "`cd $dir; pwd`/$base"
    fi
}

escape_slash ()
{
    echo ${1////\\/}
}

# convert_headers root
# @param root:   the path of source root (original root)
convert_headers ()
{
    root="$1"
    srcs=`find . -regex "$SOURCE_TYPES"`
    for src in $srcs ; do
        src_dir=`dirname $src`
        _info "Checking $src"
        lines=`awk '
            /^[[:blank:]]*#[[:blank:]]*include[[:blank:]]*"[[:alnum:].\-_][[:alnum:]/.\-_]*"/ {
                match($0, /"[[:alnum:]/.\-_]*"/, m)
                hdr=gensub(/"([[:alnum:]/.\-_]*)"/, "\\\\1", "", m[0])
                printf "%s,%s\n", NR, hdr
            }' $src`

        sed_cmd=""
        for line in $lines ; do
            lineno=${line%,*}
            hdr=${line#*,}
            hdr_path=""

            # Ignore *.pb.h
            if [[ "$hdr" =~ \.pb\.h$ ]]; then
                continue
            fi

            # Already good
            if [ -f "$root/$hdr" ] ; then
                continue
            fi

            if [ -f "$src_dir/$hdr" ] ; then
                hdr_path=$(absolute_path "$src_dir/$hdr")
            else
                search_dir="`find $root | grep -E "/$hdr$"`"
                if [[ $(echo "$search_dir" | wc -l) -gt 1 ]]; then
                    _warning "Ambiguous file: '$hdr', can't be fixed automatically:\n$search_dir"
                    continue
                fi
                if [ -f "$search_dir" ] ; then
                    hdr_path=${search_dir#$root/}
                fi
            fi

            # check if header file exists from source root
            if [[ $hdr_path != "" ]] ; then
                new_hdr=${hdr_path#$root/}
                if [[ "$hdr" != "$new_hdr" ]] ; then
                    _info "Replace '$hdr' to '$new_hdr'"
                    sed_cmd=${sed_cmd}"$lineno {s|$(escape_slash $hdr)|$(escape_slash $new_hdr)|g}"$'\n'
                fi
            fi
        done

        if [ -n "$sed_cmd" ]; then
            _info "Converting $src, backup file is $src.bak"
            sed -i.bak "$sed_cmd" $src
        fi
    done
}

if [ $# -ne 1 ]; then
    _warning "Fix the source file include path"
    _warning "Usage: $0 <dir>"
    _warning "Example: $0 ."
    exit 1
fi

cd $1 || exit 1

ROOT=$(_find_project_root)
convert_headers $ROOT

