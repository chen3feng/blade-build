# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# This is the test module for proto_library target.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


import os
import sys
import blade_test


class TestProtoLibrary(blade_test.TargetTest):
    """Test proto_library """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_proto_library')

    def testGenerateRules(self):
        """Test that rules are generated correctly. """
        self.all_targets = self.blade.analyze_targets()
        self.rules_buf = self.blade.generate_build_rules()

        cc_library_lower = (self.target_path, 'lowercase')
        proto_library_option = (self.target_path, 'rpc_option_proto')
        proto_library_meta = (self.target_path, 'rpc_option_proto')
        self.command_file = 'cmds.tmp'

        self.assertIn(cc_library_lower, self.all_targets.keys())
        self.assertIn(proto_library_option, self.all_targets.keys())
        self.assertIn(proto_library_meta, self.all_targets.keys())

        self.assertTrue(self.dryRun())

        com_lower_line = ''
        com_proto_cpp_option = ''
        com_proto_java_option = ''
        com_proto_cpp_meta = ''
        com_proto_java_meta = ''

        com_proto_option_cc = ''
        com_proto_meta_cc = ''
        meta_depends_libs = ''
        lower_depends_libs = ''

        for line in self.scons_output:
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

        self.assertCxxFlags(com_lower_line)

        self.assertTrue(com_proto_cpp_option)
        self.assertTrue(com_proto_cpp_meta)
        self.assertTrue(com_proto_java_option)
        self.assertTrue(com_proto_java_meta)

        self.assertNoWarningCxxFlags(com_proto_option_cc)
        self.assertNoWarningCxxFlags(com_proto_meta_cc)

        self.assertTrue(meta_depends_libs)
        self.assertIn('librpc_option_proto.so', meta_depends_libs)

        self.assertIn('liblowercase.so', lower_depends_libs)
        self.assertIn('librpc_meta_info_proto.so', lower_depends_libs)
        self.assertIn('librpc_option_proto.so', lower_depends_libs)


if __name__ == '__main__':
    blade_test.run(TestProtoLibrary)
