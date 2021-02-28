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
    """Test java targets."""
    def setUp(self):
        """setup method."""
        self.doSetUp('java')
        self.upper_target_path = 'test_java'

    def testLoadBuildsNotNone(self):
        """Test direct targets and all command targets are not none."""

    def testGenerateRules(self):
        """Test that rules are generated correctly."""
        self.assertTrue(self.dryRun())

        com_proto_java_option = self.findCommand(['protobuf/bin/protoc', 'java_out', 'rpc_option.proto'])
        com_proto_java_meta = self.findCommand(['protobuf/bin/protoc', 'java_out', 'rpc_meta_info.proto'])
        java_com_line, java_com_idx = self.findCommandAndLine(['javac', '-classpath'])
        jar_line, jar_idx = self.findCommandAndLine('jar cf')

        self.assertTrue(com_proto_java_option)
        self.assertTrue(com_proto_java_meta)


if __name__ == '__main__':
    blade_test.run(TestJava)
