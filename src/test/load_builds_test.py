# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the TestLoadBuilds module which tests the loading
 function of blade.

"""


import blade_test


class TestLoadBuilds(blade_test.TargetTest):
    """Test load builds. """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_loadbuilds')

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

if __name__ == '__main__':
    blade_test.run(TestLoadBuilds)
