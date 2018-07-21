# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the test module for cc_binary target.

"""


import blade_test


class TestCcBinary(blade_test.TargetTest):
    """Test cc_binary """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_cc_binary')

    def testGenerateRules(self):
        """Test that rules are generated correctly. """
        com_lower_line = ''
        com_upper_line = ''
        com_string_line = ''
        string_main_depends_libs = ''
        for line in self.scons_output:
            if 'plowercase.cpp.o -c' in line:
                com_lower_line = line
            if 'puppercase.cpp.o -c' in line:
                com_upper_line = line
            if 'string_main.cpp.o -c' in line:
                com_string_line = line
            if 'string_main_prog' in line:
                string_main_depends_libs = line

        self.assertCxxFlags(com_lower_line)
        self.assertCxxFlags(com_upper_line)
        self.assertCxxFlags(com_string_line)

        self.assertLinkFlags(string_main_depends_libs)
        self.assertIn('liblowercase.a', string_main_depends_libs)
        self.assertIn('libuppercase.a', string_main_depends_libs)


if __name__ == '__main__':
    blade_test.run(TestCcBinary)
