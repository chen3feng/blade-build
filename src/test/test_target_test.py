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
        self.doSetUp('test_test_runner', 'string_test_main',
                     full_test=False, args='', test_jobs=1, show_details=True)

    def testTestRunnerCorrectly(self):
        """Test query targets dependency relationship correctly. """
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


if __name__ == '__main__':
    blade_test.run(TestTestRunner)
