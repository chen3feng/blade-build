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

cd `dirname $0`

ROOT="$(cd ../.. && pwd)"
cat > $ROOT/.coveragerc << EOF
[run]
data_file = $ROOT/.coverage
omit = */src/blade/pathlib.py
EOF

rm -f $ROOT/.coverage

export BLADE_PYTHON_INTERPRETER="coverage run -a --source=$ROOT/src/blade --rcfile=$ROOT/.coveragerc"

python -B $@
exit_code=$?

coverage report --rcfile=$ROOT/.coveragerc

exit $exit_code
