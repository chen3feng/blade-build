#!/bin/bash
# Author: CHEN Feng <chen3feng@gmail.com>
# Make opensource release package

set -e

if [ $# -ne 1 ]; then
    echo "$0 <version>" >&2
    exit 1
fi

version="$1"

blade_dir=$(cd $(dirname $0) && pwd)
blade_dir_name=$(basename "$blade_dir")
cd $blade_dir

./dist_blade

cd ..
output_dir=$(pwd)
echo $output_dir
tar cjvf blade-$version.tbz $blade_dir_name --exclude .git --exclude src --exclude extra --exclude ".*"

echo "$output_dir/blade-$version.tbz was generated"

