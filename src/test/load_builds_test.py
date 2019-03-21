# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the TestLoadBuilds module which tests the loading
 function of blade.

"""

import unittest
import blade_test


class TestLoadBuilds(blade_test.TargetTest):
    """Test load builds. """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_loadbuilds')

    @unittest.skip('TODO: query loaded targets')
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


if __name__ == '__main__':
    blade_test.run(TestLoadBuilds)
