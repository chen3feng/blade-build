#!/bin/bash

# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: CHEN Feng <chen3feng@gmail.com>
# Created:   Feb 22, 2013
#
# Script to run examples

cd `dirname $0`

# Cleanup before running
rm -rf blade-bin build{32,64}_{debug,release}/

. setup.sh

../blade $@
exit_code=$?

. cleanup.sh

exit $exit_code
