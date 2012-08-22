"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the test module for java_jar target.

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


class TestJavaJar(unittest.TestCase):
    """Test java_jar """
    def setUp(self):
        """setup method. """
        self.command = 'build'
        self.targets = ['test_java_jar/java:poppy_java_client']
        self.upper_target_path = 'test_java_jar'
        self.target_path = 'test_java_jar/java'
        self.cur_dir = os.getcwd()
        os.chdir('./testdata')
        self.blade_path = '../../blade'
        self.working_dir = '.'
        self.current_building_path = 'build64_release'
        self.current_source_dir = '.'
        self.options = Namespace({'m' : '64',
                                  'profile' : 'release',
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
        pass

    def testGenerateRules(self):
        """Test that rules are generated correctly. """
        self.all_targets = self.blade.analyze_targets()
        self.rules_buf = self.blade.generate_build_rules()

        swig_library = (self.upper_target_path, 'poppy_client')
        java_client = (self.target_path, 'poppy_java_client')
        proto_library = (self.upper_target_path, 'rpc_option_proto')
        self.command_file = 'cmds.tmp'

        self.assertTrue(swig_library in self.all_targets.keys())
        self.assertTrue(java_client in self.all_targets.keys())
        self.assertTrue(proto_library in self.all_targets.keys())

        p = subprocess.Popen("scons --dry-run > %s" % self.command_file,
                             stdout=subprocess.PIPE,
                             shell=True)
        try:
            p.wait()
            self.assertEqual(p.returncode, 0)

            com_proto_cpp_option = ''
            com_proto_java_option = ''
            com_proto_cpp_meta = ''
            com_proto_java_meta = ''

            com_proto_option_cc = ''
            com_proto_meta_cc = ''

            com_swig_python = ''
            com_swig_java = ''
            com_swig_python_cxx = ''
            com_swig_java_cxx = ''

            swig_python_so = ''
            swig_java_so = ''

            java_com_line = ''
            java_so_line = ''
            jar_line = ''

            java_com_idx = 0
            java_so_idx = 0
            jar_idx = 0
            index = 0

            for line in open(self.command_file):
                index += 1
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
                if 'swig -python' in line:
                    com_swig_python = line
                if 'swig -java' in line:
                    com_swig_java = line
                if 'poppy_client_pywrap.cxx.o -c' in line:
                    com_swig_python_cxx = line
                if 'poppy_client_javawrap.cxx.o -c' in line:
                    com_swig_java_cxx = line
                if 'javac -classpath' in line:
                    java_com_line = line
                    java_com_idx = index
                if 'libpoppy_client_java.so -m64' in line:
                    java_so_line = line
                    java_so_idx = index
                if 'jar cf' in line:
                    jar_line = line
                    jar_idx = index
        except:
            print sys.exc_info()
            self.fail("Failed while dry running in test case")

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

        self.assertTrue('poppy_client_pywrap.cxx' in com_swig_python)
        self.assertTrue('poppy_client_javawrap.cxx' in com_swig_java)

        self.assertTrue('-fno-omit-frame-pointer' in com_swig_python_cxx)
        self.assertTrue('-mcx16 -pipe -g' in com_swig_python_cxx)
        self.assertTrue('-DNDEBUG -D_FILE_OFFSET_BITS' in com_swig_python_cxx)

        self.assertTrue('-fno-omit-frame-pointer' in com_swig_java_cxx)
        self.assertTrue('-mcx16 -pipe -g' in com_swig_java_cxx)
        self.assertTrue('-DNDEBUG -D_FILE_OFFSET_BITS' in com_swig_java_cxx)

        self.assertTrue(java_com_line)
        self.assertTrue(java_so_line)
        self.assertTrue(jar_line)

        self.assertTrue('test_java_jar/java/lib/junit.jar' in java_com_line)
        self.assertTrue('com/soso/poppy/swig/*.java' in java_com_line)
        self.assertTrue('com/soso/poppy/*.java' in java_com_line)

        whole_archive = ("--whole-archive build64_release/test_java_jar/"
                         "librpc_meta_info_proto.a build64_release/test_java_jar/"
                         "librpc_option_proto.a -Wl,--no-whole-archive")
        self.assertTrue(whole_archive in java_so_line)
        self.assertGreater(jar_idx, java_com_idx)
        self.assertGreater(jar_idx, java_so_idx)

        os.remove('./SConstruct')
        os.remove(self.command_file)


if __name__ == "__main__":
    suite_test = unittest.TestSuite()
    suite_test.addTests(
            [unittest.defaultTestLoader.loadTestsFromTestCase(TestJavaJar)])
    runner = unittest.TextTestRunner()
    runner.run(suite_test)
