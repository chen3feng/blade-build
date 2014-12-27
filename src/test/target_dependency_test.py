# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the Target dependency analyzing test module
 which tests the dependency analyzing module of blade.

"""


import os
import blade_test


class TestDepsAnalyzing(blade_test.TargetTest):
    """Test dependency analyzing. """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_dependency')

    def testExpandedTargets(self):
        """Test that all targets dependency relationship are

        populated correctly.

        """
        self.assertTrue(self.blade.is_expanded())
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

        self.assertIn(cc_library_poppy, self.all_targets.keys())

        poppy_deps = self.all_targets[cc_library_poppy].expanded_deps
        poppy_mock_deps = self.all_targets[cc_lib_poppy_mock].expanded_deps
        self.assertTrue(poppy_deps)
        self.assertTrue(poppy_mock_deps)

        self.assertIn(proto_lib_option, poppy_deps)
        self.assertIn(proto_lib_meta, poppy_deps)
        self.assertIn(static_resource, poppy_deps)
        self.assertIn(system_lib, poppy_deps)
        self.assertIn(cc_library_poppy, poppy_mock_deps)
        self.assertIn(proto_lib_meta, poppy_mock_deps)

        poppy_client_deps = self.all_targets[swig_library].expanded_deps
        self.assertTrue(poppy_client_deps)
        self.assertIn(cc_library_poppy, poppy_client_deps)
        self.assertIn(cc_lib_prebuild , poppy_client_deps)

        self.assertIn(java_jar, self.all_targets)
        java_jar_deps = self.all_targets[java_jar].expanded_deps
        self.assertTrue(java_jar_deps)

        self.assertIn(proto_lib_option, java_jar_deps)
        self.assertIn(proto_lib_meta, java_jar_deps)
        self.assertIn(java_jar_prebuild, java_jar_deps)
        self.assertNotIn(cc_library_poppy, java_jar_deps)


if __name__ == '__main__':
    blade_test.run(TestDepsAnalyzing)
