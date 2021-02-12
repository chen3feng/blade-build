# Copyright (c) 2021 Tencent Inc.
# All rights reserved.
#
# Author: chen3feng <chen3feng@gmail.com>
# Date:   Feb 12, 2012


"""
This is the test module to test dump function of blade.
"""

import unittest
import blade_test


class TestDump(blade_test.TargetTest):
    def setUp(self):
        self.doSetUp('cc', target='...')

    def testDumpCompdb(self):
        self.assertTrue(self.runBlade('dump', '--compdb'))

if __name__ == '__main__':
    blade_test.run(TestDump)
