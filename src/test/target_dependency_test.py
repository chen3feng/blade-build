# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the Target dependency analyzing test module
 which tests the dependency analyzing module of blade.

"""


import os
import blade_test


class TestDepsAnalyzing(blade_test.TargetTest):
    """Test dependency analyzing. """
    def setUp(self):
        """setup method. """
        # self.doSetUp('test_dependency')
        pass

    def testExpandedTargets(self):
        """Test that all targets dependency relationship are populated correctly.
        """
        pass

if __name__ == '__main__':
    blade_test.run(TestDepsAnalyzing)
