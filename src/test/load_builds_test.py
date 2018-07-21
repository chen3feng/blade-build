# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the TestLoadBuilds module which tests the loading
 function of blade.

"""


import blade_test


class TestLoadBuilds(blade_test.TargetTest):
    """Test load builds. """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_loadbuilds')

    def testAllCommandTargets(self):
        """Test that all targets in the test project BUILD files

           are in the all command targets list.

        """


if __name__ == '__main__':
    blade_test.run(TestLoadBuilds)
