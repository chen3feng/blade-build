"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the test module for swig_library target.

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


class TestSwigLibrary(unittest.TestCase):
    """Test swig_library """
    def setUp(self):
        """setup method. """
        self.command = 'build'
        self.targets = ['test_swig_library/...']
        self.target_path = 'test_swig_library'
        self.cur_dir = os.getcwd()
        os.chdir('./testdata')
        self.blade_path = '../../blade'
        self.working_dir = '.'
        self.current_building_path = 'build64_release'
        self.current_source_dir = '.'
        self.options = Namespace({'m' : '64',
                                  'profile' : 'release',
                                  'generate_dynamic' : True,
                                  'generate_java' : True,
                                  'generate_php' : False,
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
        poppy_client = (self.target_path, 'poppy_client')
        self.command_file = 'cmds.tmp'

        self.assertTrue(cc_library_lower in self.all_targets.keys())
        self.assertTrue(poppy_client in self.all_targets.keys())

        p = subprocess.Popen("scons --dry-run > %s" % self.command_file,
                             stdout=subprocess.PIPE,
                             shell=True)
        try:
            p.wait()
            self.assertEqual(p.returncode, 0)

            com_lower_line = ''

            com_swig_python = ''
            com_swig_java = ''
            com_swig_python_cxx = ''
            com_swig_java_cxx = ''

            swig_python_so = ''
            swig_java_so = ''

            for line in open(self.command_file):
                if 'plowercase.cpp.o -c' in line:
                    com_lower_line = line
                if 'swig -python' in line:
                    com_swig_python = line
                if 'swig -java' in line:
                    com_swig_java = line
                if 'poppy_client_pywrap.cxx.o -c' in line:
                    com_swig_python_cxx = line
                if 'poppy_client_javawrap.cxx.o -c' in line:
                    com_swig_java_cxx = line
                if '_poppy_client.so -m64' in line:
                    swig_python_so = line
                if 'libpoppy_client_java.so -m64' in line:
                    swig_java_so = line
        except:
            print sys.exc_info()
            self.fail("Failed while dry running in test case")
        self.assertTrue('-fPIC -Wall -Wextra' in com_lower_line)
        self.assertTrue('-Wframe-larger-than=65536' in com_lower_line)
        self.assertTrue('-Werror=overloaded-virtual' in com_lower_line)

        self.assertTrue('poppy_client_pywrap.cxx' in com_swig_python)
        self.assertTrue('poppy_client_javawrap.cxx' in com_swig_java)

        self.assertTrue('-fno-omit-frame-pointer' in com_swig_python_cxx)
        self.assertTrue('-mcx16 -pipe -g' in com_swig_python_cxx)
        self.assertTrue('-DNDEBUG -D_FILE_OFFSET_BITS' in com_swig_python_cxx)

        self.assertTrue('-fno-omit-frame-pointer' in com_swig_java_cxx)
        self.assertTrue('-mcx16 -pipe -g' in com_swig_java_cxx)
        self.assertTrue('-DNDEBUG -D_FILE_OFFSET_BITS' in com_swig_java_cxx)

        self.assertTrue(swig_python_so)
        self.assertTrue(swig_java_so)

        os.remove('./SConstruct')
        os.remove(self.command_file)


if __name__ == "__main__":
    suite_test = unittest.TestSuite()
    suite_test.addTests(
            [unittest.defaultTestLoader.loadTestsFromTestCase(TestSwigLibrary)])
    runner = unittest.TextTestRunner()
    runner.run(suite_test)
