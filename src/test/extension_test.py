# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the test module for cc_binary target.

"""


import blade_test


class TestExtension(blade_test.TargetTest):
    """Test cc_binary """
    def testGood(self):
        """Test that rules are generated correctly. """
        self.doSetUp('test_extension/good', command='build')
        self.assertTrue(self.runBlade())

    def testNonExisted(self):
        self.doSetUp('test_extension/non-existed', command='build')
        self.assertFalse(self.runBlade())


if __name__ == '__main__':
    blade_test.run(TestExtension)
