# Copyright (c) 2021 Tencent Inc.
# All rights reserved.
#
# Author: chen3feng <chen3feng@gmail.com>
# Date:   Feb 12, 2012


"""
This is the test module to test dump function of blade.
"""

import json
import os
import blade_test


class TestDump(blade_test.TargetTest):
    def setUp(self):
        self.doSetUp('cc', target='...')

    def doTearDown(self):
        self.removeFile('dump.config')
        self.removeFile('compdb.json')
        self.removeFile('targets.json')

    def testDumpConfig(self):
        self.assertTrue(self.runBlade('dump', '--config'))
        self.assertTrue(self.runBlade('dump', '--config --to-file=dump.config'))
        self.assertTrue(os.path.isfile('dump.config'))


    def testDumpCompdb(self):
        self.assertTrue(self.runBlade('dump', '--compdb'))
        self.assertTrue(self.runBlade('dump', '--compdb --to-file=compdb.json'))
        json.load(open('compdb.json'))

    def testDumpTargets(self):
        self.assertTrue(self.runBlade('dump', '--targets'))
        self.assertTrue(self.runBlade('dump', '--targets  --to-file=targets.json'))
        json.load(open('targets.json'))

if __name__ == '__main__':
    blade_test.run(TestDump)
