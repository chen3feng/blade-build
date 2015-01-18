#!/bin/bash

# Copyright (c) 2015 Tencent Inc.
# All rights reserved.
#
# Author: CHEN Feng <chen3feng@gmail.com>

for f in `find . -name BUILD.EXAMPLE`; do
    cp $f ${f%.EXAMPLE}
done
cp BLADE_ROOT.EXAMPLE BLADE_ROOT

