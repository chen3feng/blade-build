# Copyright (c) 2021 Tencent Inc.
# All rights reserved.
#
# Author: chen3feng <chen3feng@gmail.com>
# Date:   Feb 29, 2012

"""
This is the test module to test target tags functions.
"""

import unittest

import blade_test
from blade import target_tags

class TagsTest(unittest.TestCase):
    def setUp(self):
        pass

    def testIsValid(self):
        self.assertTrue(target_tags.is_valid('test:test'))
        self.assertFalse(target_tags.is_valid('test'))

    def testCompile(self):
        self.assertTrue(target_tags.compile_filter('test:test')[0])
        self.assertTrue(target_tags.compile_filter('test:test,test2')[0])
        self.assertTrue(target_tags.compile_filter('test:test,test2 and test:test')[0])
        self.assertTrue(target_tags.compile_filter('test:test,test2 or test:test')[0])
        self.assertTrue(target_tags.compile_filter('test:test,test2 and not test:test')[0])
        self.assertTrue(target_tags.compile_filter('(test:test1,test2 and test:test)')[0])

        self.assertFalse(target_tags.compile_filter('test:test,test2 test')[0])
        self.assertFalse(target_tags.compile_filter('(test:test,test2')[0])
        self.assertFalse(target_tags.compile_filter('test:test,test2)')[0])


if __name__ == '__main__':
    blade_test.run(TagsTest)
