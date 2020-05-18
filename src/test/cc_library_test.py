# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the test module for cc_library target.

"""


import blade_test


class TestCcLibrary(blade_test.TargetTest):
    """Test cc_library """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_cc_library')

    def testGenerateRules(self):
        """Test that rules are generated correctly.

        Scons can use the rules for dry running.

        """
        self.assertTrue(self.dryRun())

        com_lower_line = self.findCommand(['-c', 'plowercase.cpp.o'])
        com_upper_line = self.findCommand(['-c', 'puppercase.cpp.o'])
        com_string_line = self.findCommand(['-c', 'blade_string.cpp.o'])
        string_depends_libs = self.findCommand('libblade_string.so')
        self.assertCxxFlags(com_lower_line)
        self.assertCxxFlags(com_upper_line)
        self.assertNoWarningCxxFlags(com_string_line)
        self.assertIn('-DNDEBUG -D_FILE_OFFSET_BITS=64', com_string_line)
        self.assertIn('-DBLADE_STR_DEF -O2', com_string_line)
        self.assertIn('-w', com_string_line)
        self.assertIn('-o', com_string_line)

        self.assertDynamicLinkFlags(string_depends_libs)

        self.assertIn('liblowercase.so', string_depends_libs)
        self.assertIn('libuppercase.so', string_depends_libs)


if __name__ == '__main__':
    blade_test.run(TestCcLibrary)
