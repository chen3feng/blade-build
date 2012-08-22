"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the test module for cc_binary target.

"""


import os
import sys
sys.path.append('..')
import unittest
import subprocess
import blade.blade
import blade.configparse
from blade.blade import Blade
from blade.configparse import BladeConfig
from blade_namespace import Namespace
from html_test_runner import HTMLTestRunner


class TestCcBinary(unittest.TestCase):
    """Test cc_binary """
    def setUp(self):
        """setup method. """
        self.command = 'build'
        self.targets = ['test_cc_binary/...']
        self.target_path = 'test_cc_binary'
        self.cur_dir = os.getcwd()
        os.chdir('./testdata')
        self.blade_path = '../../blade'
        self.working_dir = '.'
        self.current_building_path = 'build64_release'
        self.current_source_dir = '.'
        self.options = Namespace({'m' : '64',
                                  'profile' : 'release',
                                  'generate_dynamic' : True
                                 })
        self.direct_targets = []
        self.all_command_targets = []
        self.related_targets = {}

        # Init global configuration manager
        blade.configparse.blade_config = BladeConfig(self.current_source_dir)
        blade.configparse.blade_config.parse()

        blade.blade.blade = Blade(self.targets,
                                  self.blade_path,
                                  self.working_dir,
                                  self.current_building_path,
                                  self.current_source_dir,
                                  self.options,
                                  blade_command=self.command)
        self.blade = blade.blade.blade
        (self.direct_targets,
         self.all_command_targets) = self.blade.load_targets()

    def tearDown(self):
        """tear down method. """
        os.chdir(self.cur_dir)

    def testLoadBuildsNotNone(self):
        """Test direct targets and all command targets are not none. """
        self.assertEqual(self.direct_targets, [])
        self.assertTrue(self.all_command_targets)

    def testGenerateRules(self):
        """Test that rules are generated correctly. """
        self.all_targets = self.blade.analyze_targets()
        self.rules_buf = self.blade.generate_build_rules()

        cc_library_lower = (self.target_path, 'lowercase')
        cc_library_upper = (self.target_path, 'uppercase')
        cc_library_string = (self.target_path, 'string_main_prog')
        self.command_file = 'cmds.tmp'

        self.assertTrue(cc_library_lower in self.all_targets.keys())
        self.assertTrue(cc_library_upper in self.all_targets.keys())
        self.assertTrue(cc_library_string in self.all_targets.keys())

        p = subprocess.Popen("scons --dry-run > %s" % self.command_file,
                             stdout=subprocess.PIPE,
                             shell=True)
        try:
            p.wait()
            self.assertEqual(p.returncode, 0)
            com_lower_line = ''
            com_upper_line = ''
            com_string_line = ''
            string_main_depends_libs = ''
            for line in open(self.command_file):
                if 'plowercase.cpp.o -c' in line:
                    com_lower_line = line
                if 'puppercase.cpp.o -c' in line:
                    com_upper_line = line
                if 'string_main.cpp.o -c' in line:
                    com_string_line = line
                if 'string_main_prog' in line:
                    string_main_depends_libs = line
        except:
            print sys.exc_info()
            self.fail("Failed while dry running in test case")

        self.assertTrue('-fPIC -Wall -Wextra' in com_lower_line)
        self.assertTrue('-Wframe-larger-than=65536' in com_lower_line)
        self.assertTrue('-Werror=overloaded-virtual' in com_lower_line)

        self.assertTrue('-fPIC -Wall -Wextra' in com_upper_line)
        self.assertTrue('-Wframe-larger-than=65536' in com_upper_line)
        self.assertTrue('-Werror=overloaded-virtual' in com_upper_line)

        self.assertTrue('-fPIC -Wall -Wextra' in com_string_line)
        self.assertTrue('-Wframe-larger-than=65536' in com_string_line)
        self.assertTrue('-Werror=overloaded-virtual' in com_string_line)

        self.assertTrue('-static-libgcc -static-libstdc++' in string_main_depends_libs)
        self.assertTrue('liblowercase.a' in string_main_depends_libs)
        self.assertTrue('libuppercase.a' in string_main_depends_libs)

        os.remove('./SConstruct')
        os.remove(self.command_file)


if __name__ == "__main__":
    suite_test = unittest.TestSuite()
    suite_test.addTests(
            [unittest.defaultTestLoader.loadTestsFromTestCase(TestCcBinary)])
    runner = unittest.TextTestRunner()
    runner.run(suite_test)
