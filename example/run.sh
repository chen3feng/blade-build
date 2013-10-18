#!/bin/bash

# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: CHEN Feng <chen3feng@gmail.com>
# Created:   Feb 22, 2013
#
# Script to run examples

function cleanup()
{
    # Cleanup BLADE_ROOT and BUILDs to avoid ran by 'blade build ...' on upper dirs
    find . -name BUILD | xargs rm
    rm -rf BLADE_ROOT

    # Cleanup generated files
    rm -rf {BLADE_ROOT,blade-bin,build64_release/,.blade.test.stamp,.sconsign.dblite,.sconsign.tmp,blade_tests_detail,.Building.lock} SConstruct
}

cd `dirname $0`

# Cleanup before running
rm -rf blade-bin/ build64_release/

for f in `find . -name BUILD.EXAMPLE`; do
    cp $f ${f%.EXAMPLE}
done
cp BLADE_ROOT.EXAMPLE BLADE_ROOT

../blade test ... --verbose
exit_code=$?

cleanup

exit $exit_code
