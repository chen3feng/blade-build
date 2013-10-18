#!/bin/bash

# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: CHEN Feng <chen3feng@gmail.com>
# Created:   Feb 22, 2013
#
# Script to setup, run and cleanup testing.

if [ $# -lt 1 ]; then
    echo "Usage: $1 <test_file_name>" >&2
    exit 1
fi

function cleanup()
{
    # Cleanup BLADE_ROOT and BUILDs to avoid ran by 'blade build ...' on upper dirs
    find testdata -name BUILD | xargs rm
    rm -rf testdata/BLADE_ROOT

    # Cleanup generated files
    rm -rf testdata/{BLADE_ROOT,blade-bin,build64_release/,.blade.test.stamp,.sconsign.dblite,blade_tests_detail,.Building.lock} SConstruct
    rm -f *.pyc ../blade/*.pyc
}

cd `dirname $0`

# Cleanup before running
rm -rf testdata/blade-bin/ testdata/build64_release/

for f in `find testdata -name BUILD.TEST`; do
    cp $f ${f%.TEST}
done
cp testdata/BLADE_ROOT.TEST testdata/BLADE_ROOT

python -B $@
exit_code=$?

cleanup

exit $exit_code
