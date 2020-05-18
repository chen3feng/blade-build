# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the test module for java_jar target.

"""


import blade_test


class TestJava(blade_test.TargetTest):
    """Test java_jar """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_java/java', generate_php=False)
        self.upper_target_path = 'test_java'

    def testLoadBuildsNotNone(self):
        """Test direct targets and all command targets are not none. """
        pass

    def testGenerateRules(self):
        """Test that rules are generated correctly. """
        self.assertTrue(self.dryRun())

        com_proto_cpp_option = self.findCommand(['protobuf/bin/protoc', 'cpp_out', 'rpc_option.proto'])
        com_proto_cpp_meta = self.findCommand(['protobuf/bin/protoc', 'cpp_out', 'rpc_meta_info.proto'])
        com_proto_java_option = self.findCommand(['protobuf/bin/protoc', 'java_out', 'rpc_option.proto'])
        com_proto_java_meta = self.findCommand(['protobuf/bin/protoc', 'java_out', 'rpc_meta_info.proto'])
        com_proto_option_cc = self.findCommand(['rpc_option.pb.cc.o', '-c'])
        com_proto_meta_cc = self.findCommand(['rpc_meta_info.pb.cc.o', '-c'])
        java_com_line, java_com_idx = self.findCommandAndLine(['javac', '-classpath'])
        jar_line, jar_idx = self.findCommandAndLine('jar cf')

        self.assertTrue(com_proto_cpp_option)
        self.assertTrue(com_proto_cpp_meta)
        self.assertTrue(com_proto_java_option)
        self.assertTrue(com_proto_java_meta)

        self.assertIn('-fPIC', com_proto_option_cc)
        self.assertNotIn('-Wall -Wextra', com_proto_option_cc)
        self.assertNotIn('-Wframe-larger-than=', com_proto_option_cc)
        self.assertNotIn('-Werror=overloaded-virtual', com_proto_option_cc)

        self.assertIn('-fPIC', com_proto_meta_cc)

        # whole_archive = ('--whole-archive build64_release/test_java_jar/'
        #                  'librpc_meta_info_proto.a build64_release/test_java_jar/'
        #                  'librpc_option_proto.a -Wl,--no-whole-archive')
        # self.assertIn(whole_archive, java_so_line)
        # self.assertGreater(jar_idx, java_com_idx)
        # self.assertGreater(jar_idx, java_so_idx)
        # self.assertNotEqual('', java_com_line)
        # self.assertNotEqual('', java_so_line)
        # self.assertNotEqual('', jar_line)
        # self.assertIn('test_java_jar/java/lib/junit.jar', java_com_line)
        # self.assertIn('com/soso/poppy/*.java', java_com_line)


if __name__ == '__main__':
    blade_test.run(TestJava)
