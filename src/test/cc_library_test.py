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
        self.all_targets = self.blade.analyze_targets()
        self.rules_buf = self.blade.generate_build_rules()

        cc_library_lower = (self.target_path, 'lowercase')
        cc_library_upper = (self.target_path, 'uppercase')
        cc_library_string = (self.target_path, 'blade_string')

        self.assertIn(cc_library_lower, self.all_targets.keys())
        self.assertIn(cc_library_upper, self.all_targets.keys())
        self.assertIn(cc_library_string, self.all_targets.keys())

        self.assertTrue(self.dryRun())

        com_lower_line = ''
        com_upper_line = ''
        com_string_line = ''
        string_depends_libs = ''
        for line in self.scons_output:
            if 'plowercase.cpp.o -c' in line:
                com_lower_line = line
            if 'puppercase.cpp.o -c' in line:
                com_upper_line = line
            if 'blade_string.cpp.o -c' in line:
                com_string_line = line
            if 'libblade_string.so' in line:
                string_depends_libs = line

        self.assertCxxFlags(com_lower_line)
        self.assertCxxFlags(com_upper_line)
        self.assertNoWarningCxxFlags(com_string_line)
        self.assertIn('-DNDEBUG -D_FILE_OFFSET_BITS=64', com_string_line)
        self.assertIn('-DBLADE_STR_DEF -O2', com_string_line)
        self.assertIn('-w', com_string_line)
        self.assertIn('-m64', com_string_line)

        self.assertDynamicLinkFlags(string_depends_libs)

        self.assertIn('liblowercase.so', string_depends_libs)
        self.assertIn('libuppercase.so', string_depends_libs)


if __name__ == '__main__':
    blade_test.run(TestCcLibrary)
