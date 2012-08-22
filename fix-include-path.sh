#! /bin/bash

# source file types, you may need to change it, using regex
SOURCE_TYPES=".*[.]\(c\|h\|cc\|hh\|cpp\|hpp\)$"

# do not touch this two variables, we will choose proper values
OLD_SRC_ROOT=`pwd`
DST_SRC_ROOT=""

CONVERT_LOG="convert.log"
SKIP_LOG="skip.log"
WARNING_LOG="warning.log"

find_root ()
{
    old_path=`pwd`
    
    cd $1
    path=`pwd`
    while [  ! -f 'BLADE_ROOT' -a $path  != "/" ]; do
        cd ..
        path=`pwd`
    done
    cd $old_path

    echo $path
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

# convert_headers root prefix
# @param root:   the path of source root (original root)
# @param prefix: the prefix we should patch to the include path
convert_headers ()
{
    root=$(absolute_path $1)
    prefix=$2

    echo "root=$root prefix=$prefix"
    srcs=`find $root -regex "$SOURCE_TYPES"`
    for src in $srcs ; do
        src_dir=`dirname $src`
        
        #echo "parse $src"
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

            if [ -f "$root/$hdr" ] ; then
                hdr_path=$(absolute_path "$root/$hdr")
            fi

            if [ -f "$src_dir/$hdr" ] ; then
                hdr_path=$(absolute_path "$src_dir/$hdr")
            fi
            
            # check if header file exists from source root
            if [[ $hdr_path != "" ]] ; then
                new_hdr=$prefix${hdr_path#$root/}
                #echo $new_hdr
                sed_cmd=${sed_cmd}"$lineno {s|$(escape_slash $hdr)|$(escape_slash $new_hdr)|g}"$'\n'
            fi

        done

        if [ -n "$sed_cmd" ]; then
            echo "$sed_cmd"
            echo "converting $src"
            #echo "$sed_cmd"
            sed -i.bak "$sed_cmd" $src
        fi

    done
}

OLD_SRC_ROOT=$(absolute_path $OLD_SRC_ROOT)

if [ -n $DST_SRC_ROOT ] ; then
    DST_SRC_ROOT=$(find_root $OLD_SRC_ROOT)
fi

if [ $OLD_SRC_ROOT == $DST_SRC_ROOT ] ; then
    echo "we are already in the source root"
    exit
fi
echo "fix the source file include path $DST_SRC_ROOT"

ROOT_PREFIX=${OLD_SRC_ROOT#$DST_SRC_ROOT/}/
#echo $ROOT_PREFIX

convert_headers $OLD_SRC_ROOT $ROOT_PREFIX

