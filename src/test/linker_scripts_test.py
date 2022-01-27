
# Copyright (c) 2022 Tencent Inc.
# All rights reserved.
#
# Author: CHEN Feng <chen3feng@gmail.com>
# Date:   Jan 24, 2022


"""
 This is the test module for cc_plugin target.

"""


import blade_test


class LinkerScriptsTest(blade_test.TargetTest):
    """Test cc linker scripts."""
    def setUp(self):
        """setup method."""
        self.doSetUp('linker_scripts')

    def testGenerateRules(self):
        """Test that rules are generated correctly."""
        self.assertTrue(self.runBlade())


if __name__ == '__main__':
    blade_test.run(LinkerScriptsTest)
