# Copyright (c) 2021 Tencent Inc.
# All rights reserved.
#
# Author: CHEN Feng <chen3feng@gmail.com>
# Date:   Jan 27, 2021

import blade_test

from blade import target_pattern


class TargetPatternTest(blade_test.TargetTest):
    def setUp(self):
        self.doSetUp('cc')

    def testNormalize(self):
        self.assertEqual('foo:*', target_pattern.normalize('//foo', '.'))
        self.assertEqual('foo:...', target_pattern.normalize('foo...', '.'))
        self.assertEqual('foo:*', target_pattern.normalize('foo', '.'))

    def testNormalizeList(self):
        self.assertEqual(['foo:...', 'foo:*'],
                         target_pattern.normalize_list(['foo...', 'foo'], '.'))

    def testIsValidInBuild(self):
        self.assertTrue(target_pattern.is_valid_in_build('//abc'))
        self.assertTrue(target_pattern.is_valid_in_build(':abc'))
        self.assertFalse(target_pattern.is_valid_in_build('abc'))

    def testMatch(self):
        self.assertTrue(target_pattern.match('abc:a', 'abc:a'))
        self.assertTrue(target_pattern.match('abc:a', 'abc:*'))
        self.assertTrue(target_pattern.match('abc/def:a', 'abc:...'))


if __name__ == '__main__':
    blade_test.run(TargetPatternTest)
