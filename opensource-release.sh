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
cd $blade_dir

./dist_blade

cd ..
mv blade/blade.conf blade.conf.org
cp blade/opensource.conf blade/blade.conf
tar cjvf blade-$version.tbz blade

# Restore blade.conf
mv blade.conf.org blade/blade.conf

echo 'Done'

