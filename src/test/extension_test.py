# Copyright (c) 2021 Tencent Inc.
# All rights reserved.
#
# Author:  CHEN Feng <chen3feng@gmail.com>
# Created: 2021-01-06


"""
 This is the test for extension functionality.
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
