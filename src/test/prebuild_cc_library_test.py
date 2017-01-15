# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the test module for prebuild_cc_library target.

"""


import blade_test


class TestPrebuildCcLibrary(blade_test.TargetTest):
    """Test cc_library """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_prebuild_cc_library')

    def testGenerateRules(self):
        """Test that rules are generated correctly.

        Scons can use the rules for dry running.

        """
        self.all_targets = self.blade.analyze_targets()
        self.rules_buf = self.blade.generate_build_rules()

        cc_library_lower = (self.target_path, 'lowercase')
        cc_library_upper = (self.target_path, 'uppercase')

        self.assertIn(cc_library_lower, self.all_targets.keys())
        self.assertIn(cc_library_upper, self.all_targets.keys())

        self.assertTrue(self.dryRun())

        copy_lower_line = ''
        com_upper_line = ''
        upper_depends_libs = ''
        for line in self.scons_output:
            if 'Copy' in line:
                copy_lower_line = line
            if 'puppercase.cpp.o -c' in line:
                com_upper_line = line
            if 'libuppercase.so -m64' in line:
                upper_depends_libs = line

        self.assertIn('test_prebuild_cc_library/liblowercase.so', copy_lower_line)
        self.assertIn('lib64_release/liblowercase.so', copy_lower_line)

        self.assertIn('-Wall -Wextra', com_upper_line)
        self.assertIn('-Wframe-larger-than=69632', com_upper_line)
        self.assertIn('-Werror=overloaded-virtual', com_upper_line)

        self.assertTrue(upper_depends_libs)
        self.assertIn('libuppercase.so -m64', upper_depends_libs)
        self.assertIn('liblowercase.so', upper_depends_libs)


if __name__ == '__main__':
    blade_test.run(TestPrebuildCcLibrary)
