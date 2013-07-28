#!/bin/bash

# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: CHEN Feng <chen3feng@gmail.com>
# Created:   Feb 22, 2013
#
# Script to setup, run and cleanup testing.

exec `dirname $0`/runtest.sh blade_main_test.py $@
