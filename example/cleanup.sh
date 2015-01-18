#!/bin/bash

# Copyright (c) 2015 Tencent Inc.
# All rights reserved.
#
# Author: CHEN Feng <chen3feng@gmail.com>

# Cleanup BLADE_ROOT and BUILDs to avoid ran by 'blade build ...' on upper dirs
find . -name BUILD | xargs rm
rm -rf BLADE_ROOT

# Cleanup generated files
rm -rf {BLADE_ROOT,blade-bin,build64_release/,.blade.test.stamp,.sconsign.dblite,.sconsign.tmp,blade_tests_detail,.Building.lock} SConstruct

