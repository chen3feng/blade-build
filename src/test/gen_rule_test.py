# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the test module for cc_gen_rule target.

"""


import blade_test


class TestGenRule(blade_test.TargetTest):
    """Test gen_rule."""
    def setUp(self):
        """setup method."""
        self.doSetUp('gen_rule')

    def testGenerateRules(self):
        """Test that rules are generated correctly."""
        self.assertTrue(self.runBlade())
        com_lower_line = self.findCommand(['plowercase.cpp.o', '-c'])
        com_use_line = self.findCommand(['use_media.cpp.o', '-c'])

        self.assertCxxFlags(com_lower_line)
        self.assertCxxFlags(com_use_line)

        gen_rule_index = self.findCommandAndLine('echo')
        use_so_index = self.findCommandAndLine('-shared')

        #self.assertGreater(gen_rule_index, lower_so_index)
        #self.assertGreater(upper_so_index, gen_rule_index)


if __name__ == '__main__':
    blade_test.run(TestGenRule)
