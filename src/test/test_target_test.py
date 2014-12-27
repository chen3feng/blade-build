# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the test module to test TestRunner function of blade.

"""


import os
import blade_test


class TestTestRunner(blade_test.TargetTest):
    """Test cc_library """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_test_runner', ':string_test_main',
                     fulltest=False, args='', test_jobs=1, show_details=True)

    def testLoadBuildsNotNone(self):
        """Test direct targets and all command targets are not none. """
        self.assertTrue(self.direct_targets)
        self.assertTrue(self.all_command_targets)

    def testTestRunnerCorrectly(self):
        """Test query targets dependency relationship correctly. """
        self.assertTrue(self.all_targets)
        self.rules_buf = self.blade.generate_build_rules()
        test_env_dir = './build%s_%s/test_test_runner' % (
                self.options.m, self.options.profile)
        if not os.path.exists(test_env_dir):
            os.mkdir(test_env_dir)

        cc_library_lower = (self.target_path, 'lowercase')
        cc_library_upper = (self.target_path, 'uppercase')
        cc_library_string = (self.target_path, 'string_test_main')

        self.assertIn(cc_library_lower, self.all_targets.keys())
        self.assertIn(cc_library_upper, self.all_targets.keys())
        self.assertIn(cc_library_string, self.all_targets.keys())

        self.assertTrue(self.dryRun())

        com_lower_line = ''
        com_upper_line = ''
        com_string_line = ''
        string_main_depends_libs = ''
        for line in self.scons_output:
            if 'plowercase.cpp.o -c' in line:
                com_lower_line = line
            if 'puppercase.cpp.o -c' in line:
                com_upper_line = line
            if 'string_test.cpp.o -c' in line:
                com_string_line = line
            if 'string_test_main' in line:
                string_main_depends_libs = line

        self.assertCxxFlags(com_lower_line)
        self.assertCxxFlags(com_upper_line)
        self.assertCxxFlags(com_string_line)

        self.assertLinkFlags(string_main_depends_libs)
        self.assertIn('liblowercase.a', string_main_depends_libs)
        ret_code = self.blade.test()
        self.assertEqual(ret_code, 1)


if __name__ == '__main__':
    blade_test.run(TestTestRunner)
