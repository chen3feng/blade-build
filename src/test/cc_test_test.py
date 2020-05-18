# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the test module for cc_test target.

"""


import blade_test


class TestCcTest(blade_test.TargetTest):
    """Test cc_test """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_cc_test')

    def testGenerateRules(self):
        """Test that rules are generated correctly. """
        self.assertTrue(self.dryRun())

        com_lower_line = self.findCommand(['plowercase.cpp.o', '-c'])
        com_upper_line = self.findCommand(['puppercase.cpp.o', '-c'])
        com_string_line = self.findCommand(['string_test.cpp.o', '-c'])
        string_main_depends_libs = self.findCommand('string_test_main ')

        self.assertCxxFlags(com_lower_line)
        self.assertCxxFlags(com_upper_line)
        self.assertCxxFlags(com_string_line)

        self.assertLinkFlags(string_main_depends_libs)
        self.assertIn('liblowercase.a', string_main_depends_libs)
        self.assertIn('libuppercase.a', string_main_depends_libs)


if __name__ == '__main__':
    blade_test.run(TestCcTest)
