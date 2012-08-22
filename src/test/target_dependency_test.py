"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the Target dependency analyzing test module
 which tests the dependency analyzing module of blade.

"""


import os
import sys
sys.path.append('..')
import unittest
import traceback
import blade.blade
import blade.configparse
from blade.blade import Blade
from blade.configparse import BladeConfig
from blade_namespace import Namespace
from html_test_runner import HTMLTestRunner


class TestDepsAnalyzing(unittest.TestCase):
    """Test dependency analyzing. """
    def setUp(self):
        """setup method. """
        self.command = 'build'
        self.targets = ['test_dependency/...']
        self.target_path = 'test_dependency'
        self.cur_dir = os.getcwd()
        os.chdir('./testdata')
        self.blade_path = '.'
        self.working_dir = '.'
        self.current_building_path = '.'
        self.current_source_dir = '.'
        self.options = Namespace({'m' : '64', 'profile' : 'release'})
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

    def testExpandedTargets(self):
        """Test that all targets dependency relationship are

        populated correctly.

        """
        self.all_targets = self.blade.analyze_targets()

        sys.stdout.flush()
        sys.stderr.flush()

        self.assertTrue(self.blade.get_expanded())
        self.assertTrue(self.all_targets)

        system_lib = ('#', 'pthread')
        proto_lib_option = (self.target_path, 'rpc_option_proto')
        proto_lib_meta = (self.target_path, 'rpc_meta_info_proto')
        cc_library_poppy = (self.target_path, 'poppy')
        cc_lib_poppy_mock = (self.target_path, 'poppy_mock')
        static_resource = (self.target_path, 'static_resource')
        cc_test = (self.target_path, 'rpc_channel_test')
        swig_library = (self.target_path, 'poppy_client')
        lex_yacc_library = (self.target_path, 'parser')
        cc_plugin = (self.target_path, 'meter_business')
        gen_rule = (self.target_path, 'search_service_echo')
        java_jar = (os.path.join(self.target_path, 'java'),
                    'poppy_java_client')
        cc_binary = (self.target_path, 'echoserver')
        cc_lib_prebuild = (self.target_path, 'poppy_swig_wrap')
        java_jar_prebuild = (os.path.join(self.target_path, 'java', 'lib'),
                             'protobuf-java')

        self.assertTrue(cc_library_poppy in self.all_targets.keys())

        poppy_deps = self.all_targets.get(cc_library_poppy, {}).get('deps', [])
        poppy_mock_deps = self.all_targets.get(cc_lib_poppy_mock, {}).get('deps', [])
        self.assertTrue(poppy_deps)
        self.assertTrue(poppy_mock_deps)

        self.assertTrue(proto_lib_option in poppy_deps)
        self.assertTrue(proto_lib_meta in poppy_deps)
        self.assertTrue(static_resource in poppy_deps)
        self.assertTrue(system_lib in poppy_deps)
        self.assertTrue(cc_library_poppy in poppy_mock_deps)
        self.assertTrue(proto_lib_meta in poppy_mock_deps)

        poppy_client_deps  = self.all_targets.get(swig_library, {}).get('deps', [])
        self.assertTrue(poppy_client_deps)
        self.assertTrue(cc_library_poppy in poppy_client_deps)
        self.assertTrue(cc_lib_prebuild  in poppy_client_deps)

        self.assertTrue(java_jar in self.all_targets.keys())
        java_jar_deps = self.all_targets.get(java_jar, {}).get('deps', [])
        self.assertTrue(java_jar_deps)

        self.assertTrue(proto_lib_option in java_jar_deps)
        self.assertTrue(proto_lib_meta in java_jar_deps)
        self.assertTrue(java_jar_prebuild in java_jar_deps)
        self.assertTrue(cc_library_poppy not in java_jar_deps)


if __name__ == "__main__":
    suite_test = unittest.TestSuite()
    suite_test.addTests(
            [unittest.defaultTestLoader.loadTestsFromTestCase(TestDepsAnalyzing)])
    runner = unittest.TextTestRunner()
    runner.run(suite_test)
