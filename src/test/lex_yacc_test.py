"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the test module for lex_yacc_library target.

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


class TestLexYacc(unittest.TestCase):
    """Test lex_yacc """
    def setUp(self):
        """setup method. """
        self.command = 'build'
        self.targets = ['test_lex_yacc/...']
        self.target_path = 'test_lex_yacc'
        self.cur_dir = os.getcwd()
        os.chdir('./testdata')
        self.blade_path = '../../blade'
        self.working_dir = '.'
        self.current_building_path = 'build64_release'
        self.current_source_dir = '.'
        self.options = Namespace({'m' : '64',
                                  'profile' : 'release',
                                  'generate_dynamic' : True,
                                  'verbose' : True
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
        lex_yacc_library = (self.target_path, 'parser')
        self.command_file = 'cmds.tmp'

        self.assertTrue(cc_library_lower in self.all_targets.keys())
        self.assertTrue(lex_yacc_library in self.all_targets.keys())

        p = subprocess.Popen("scons --dry-run > %s" % self.command_file,
                             stdout=subprocess.PIPE,
                             shell=True)
        try:
            p.wait()
            self.assertEqual(p.returncode, 0)
            com_lower_line = ''
            com_bison_line = ''
            com_flex_line = ''
            com_ll_static_line = ''
            com_ll_so_line = ''
            com_yy_static_line = ''
            com_yy_so_line = ''
            lex_yacc_depends_libs = ''
            for line in open(self.command_file):
                if 'plowercase.cpp.o -c' in line:
                    com_lower_line = line
                if 'bison -d -o' in line:
                    com_bison_line = line
                if 'flex -R -t' in line:
                    com_flex_line = line
                if 'line_parser.ll.o -c' in line:
                    com_ll_static_line = line
                if 'line_parser.yy.o -c' in line:
                    com_yy_static_line = line
                if 'line_parser.ll.os -c' in line:
                    com_ll_so_line = line
                if 'line_parser.yy.os -c' in line:
                    com_yy_so_line = line
                if 'libparser.so' in line:
                    lex_yacc_depends_libs = line
        except:
            print sys.exc_info()
            self.fail("Failed while dry running in test case")
        self.assertTrue('-fPIC -Wall -Wextra' in com_lower_line)
        self.assertTrue('-Wframe-larger-than=65536' in com_lower_line)
        self.assertTrue('-Werror=overloaded-virtual' in com_lower_line)

        self.assertTrue('line_parser.yy.cc' in com_bison_line)
        self.assertTrue('line_parser.ll.cc' in com_flex_line)

        self.assertTrue('-Woverloaded-virtual' in com_ll_static_line)
        self.assertTrue('-Werror=overloaded-virtual' not in com_ll_static_line)
        self.assertTrue('-fPIC -Wall -Wextra' in com_ll_so_line)
        self.assertTrue('-Wframe-larger-than=65536' in com_ll_so_line)
        self.assertTrue('-Werror=overloaded-virtual' not in com_ll_so_line)

        self.assertTrue('-Woverloaded-virtual' in com_yy_static_line)
        self.assertTrue('-Werror=overloaded-virtual' not in com_yy_static_line)
        self.assertTrue('-fPIC -Wall -Wextra' in com_yy_so_line)
        self.assertTrue('-Wframe-larger-than=65536' in com_yy_so_line)
        self.assertTrue('-Werror=overloaded-virtual' not in com_yy_so_line)

        self.assertTrue('liblowercase.so' in lex_yacc_depends_libs)
        self.assertTrue('line_parser.ll.os' in lex_yacc_depends_libs)
        self.assertTrue('line_parser.yy.os' in lex_yacc_depends_libs)

        os.remove('./SConstruct')
        os.remove(self.command_file)


if __name__ == "__main__":
    suite_test = unittest.TestSuite()
    suite_test.addTests(
            [unittest.defaultTestLoader.loadTestsFromTestCase(TestLexYacc)])
    runner = unittest.TextTestRunner()
    runner.run(suite_test)
