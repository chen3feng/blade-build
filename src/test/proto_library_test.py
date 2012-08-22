"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 This is the test module for proto_library target.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

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


class TestProtoLibrary(unittest.TestCase):
    """Test proto_library """
    def setUp(self):
        """setup method. """
        self.command = 'build'
        self.targets = ['test_proto_library/...']
        self.target_path = 'test_proto_library'
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
                                  'generate_php' : True,
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
        proto_library_option = (self.target_path, 'rpc_option_proto')
        proto_library_meta = (self.target_path, 'rpc_option_proto')
        self.command_file = 'cmds.tmp'

        self.assertTrue(cc_library_lower in self.all_targets.keys())
        self.assertTrue(proto_library_option in self.all_targets.keys())
        self.assertTrue(proto_library_meta in self.all_targets.keys())

        p = subprocess.Popen("scons --dry-run > %s" % self.command_file,
                             stdout=subprocess.PIPE,
                             shell=True)
        try:
            p.wait()
            self.assertEqual(p.returncode, 0)
            com_lower_line = ''

            com_proto_cpp_option = ''
            com_proto_java_option = ''
            com_proto_cpp_meta = ''
            com_proto_java_meta = ''

            com_proto_option_cc = ''
            com_proto_meta_cc = ''
            meta_depends_libs = ''
            lower_depends_libs = ''

            for line in open(self.command_file):
                if 'plowercase.cpp.o -c' in line:
                    com_lower_line = line
                if 'protobuf/bin/protoc' in line:
                    if 'cpp_out' in line:
                        if 'rpc_option.proto' in line:
                            com_proto_cpp_option = line
                        elif 'rpc_meta_info.proto' in line:
                            com_proto_cpp_meta = line
                    if 'java_out' in line:
                        if 'rpc_option.proto' in line:
                            com_proto_java_option = line
                        elif 'rpc_meta_info.proto' in line:
                            com_proto_java_meta = line

                if 'rpc_option.pb.cc.o -c' in line:
                    com_proto_option_cc = line
                if 'rpc_meta_info.pb.cc.o -c' in line:
                    com_proto_meta_cc = line
                if 'librpc_meta_info_proto.so -m64' in line:
                    meta_depends_libs = line
                if 'liblowercase.so -m64' in line:
                    lower_depends_libs = line
        except:
            print sys.exc_info()
            self.fail("Failed while dry running in test case")
        self.assertTrue('-fPIC -Wall -Wextra' in com_lower_line)
        self.assertTrue('-Wframe-larger-than=65536' in com_lower_line)
        self.assertTrue('-Werror=overloaded-virtual' in com_lower_line)

        self.assertTrue(com_proto_cpp_option)
        self.assertTrue(com_proto_cpp_meta)
        self.assertTrue(com_proto_java_option)
        self.assertTrue(com_proto_java_meta)

        self.assertTrue('-fPIC -Wall -Wextra' in com_proto_option_cc)
        self.assertTrue('-Wframe-larger-than=' in com_proto_option_cc)
        self.assertTrue('-Werror=overloaded-virtual' not in com_proto_option_cc)

        self.assertTrue('-fPIC -Wall -Wextra' in com_proto_meta_cc)
        self.assertTrue('-Wframe-larger-than=' in com_proto_meta_cc)
        self.assertTrue('-Werror=overloaded-virtual' not in com_proto_meta_cc)

        self.assertTrue(meta_depends_libs)
        self.assertTrue('librpc_option_proto.so' in meta_depends_libs)

        self.assertTrue('liblowercase.so' in lower_depends_libs)
        self.assertTrue('librpc_meta_info_proto.so' in lower_depends_libs)
        self.assertTrue('librpc_option_proto.so' in lower_depends_libs)

        os.remove('./SConstruct')
        os.remove(self.command_file)


if __name__ == "__main__":
    suite_test = unittest.TestSuite()
    suite_test.addTests(
            [unittest.defaultTestLoader.loadTestsFromTestCase(TestProtoLibrary)])
    runner = unittest.TextTestRunner()
    runner.run(suite_test)
