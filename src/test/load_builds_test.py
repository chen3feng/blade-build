"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the TestLoadBuilds module which tests the loading
 function of blade.

"""


import os
import sys
sys.path.append('..')
import unittest
import blade.blade
import blade.configparse
from blade.blade import Blade
from blade.configparse import BladeConfig
from blade_namespace import Namespace
from html_test_runner import HTMLTestRunner


class TestLoadBuilds(unittest.TestCase):
    """Test load builds. """
    def setUp(self):
        """setup method. """
        self.command = 'build'
        self.targets = ['test_loadbuilds/...']
        self.target_path = 'test_loadbuilds'
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

    def testAllCommandTargets(self):
        """Test that all targets in the test project BUILD files

           are in the all command targets list.

        """
        proto_library = (self.target_path, 'rpc_meta_info_proto')
        cc_library = (self.target_path, 'poppy')
        static_resource = (self.target_path, 'static_resource')
        cc_test = (self.target_path, 'rpc_channel_test')
        swig_library = (self.target_path, 'poppy_client')
        lex_yacc_library = (self.target_path, 'parser')
        cc_plugin = (self.target_path, 'meter_business')
        gen_rule = (self.target_path, 'search_service_echo')
        java_jar = (self.target_path, 'poppy_java_client')
        cc_binary = (self.target_path, 'echoserver')

        target_list = []
        l = target_list
        l.append(proto_library)
        l.append(cc_library)
        l.append(static_resource)
        l.append(cc_test)
        l.append(swig_library)
        l.append(lex_yacc_library)
        l.append(cc_plugin)
        l.append(gen_rule)
        l.append(java_jar)
        l.append(cc_binary)

        target_count = 0
        for target in target_list:
            if target in self.all_command_targets:
                target_count += 1
            else:
                self.fail(msg='(%s, %s) not in all command targets, failed' % (
                        target[0], target[1]))
                break

        self.assertEqual(target_count, 10)

if __name__ == "__main__":
    suite_test = unittest.TestSuite()
    suite_test.addTests(
            [unittest.defaultTestLoader.loadTestsFromTestCase(TestLoadBuilds)])
    runner = unittest.TextTestRunner()
    runner.run(suite_test)
