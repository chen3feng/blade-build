"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

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
        self.all_targets = self.blade.analyze_targets()
        self.rules_buf = self.blade.generate_build_rules()

        cc_library_lower = (self.target_path, 'lowercase')
        cc_library_upper = (self.target_path, 'uppercase')
        cc_library_string = (self.target_path, 'string_test_main')
        self.command_file = 'cmds.tmp'

        self.assertTrue(cc_library_lower in self.all_targets.keys())
        self.assertTrue(cc_library_upper in self.all_targets.keys())
        self.assertTrue(cc_library_string in self.all_targets.keys())

        self.assertTrue(self.dryRun())

        com_lower_line = ''
        com_upper_line = ''
        com_string_line = ''
        string_main_depends_libs = ''
        for line in open(self.command_file):
            if 'plowercase.cpp.o -c' in line:
                com_lower_line = line
            if 'puppercase.cpp.o -c' in line:
                com_upper_line = line
            if 'string_test.cpp.o -c' in line:
                com_string_line = line
            if 'string_test_main' in line:
                string_main_depends_libs = line

        self.assertTrue('-fPIC -Wall -Wextra' in com_lower_line)
        self.assertTrue('-Wframe-larger-than=69632' in com_lower_line)
        self.assertTrue('-Werror=overloaded-virtual' in com_lower_line)

        self.assertTrue('-fPIC -Wall -Wextra' in com_upper_line)
        self.assertTrue('-Wframe-larger-than=69632' in com_upper_line)
        self.assertTrue('-Werror=overloaded-virtual' in com_upper_line)

        self.assertTrue('-fPIC -Wall -Wextra' in com_string_line)
        self.assertTrue('-Wframe-larger-than=69632' in com_string_line)
        self.assertTrue('-Werror=overloaded-virtual' in com_string_line)

        self.assertTrue('-static-libgcc -static-libstdc++' in string_main_depends_libs)
        self.assertTrue('liblowercase.a' in string_main_depends_libs)
        self.assertTrue('libuppercase.a' in string_main_depends_libs)


if __name__ == "__main__":
    blade_test.run(TestCcTest)
