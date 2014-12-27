# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the test module for java_jar target.

"""


import blade_test


class TestJavaJar(blade_test.TargetTest):
    """Test java_jar """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_java_jar/java', ':poppy_java_client',
                     generate_php=False)
        self.upper_target_path = 'test_java_jar'

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

        self.assertIn(swig_library, self.all_targets.keys())
        self.assertIn(java_client, self.all_targets.keys())
        self.assertIn(proto_library, self.all_targets.keys())

        self.assertTrue(self.dryRun())

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

        for line in self.scons_output:
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

        self.assertTrue(com_proto_cpp_option)
        self.assertTrue(com_proto_cpp_meta)
        self.assertTrue(com_proto_java_option)
        self.assertTrue(com_proto_java_meta)

        self.assertIn('-fPIC', com_proto_option_cc)
        self.assertNotIn('-Wall -Wextra', com_proto_option_cc)
        self.assertNotIn('-Wframe-larger-than=', com_proto_option_cc)
        self.assertNotIn('-Werror=overloaded-virtual', com_proto_option_cc)

        self.assertIn('-fPIC', com_proto_meta_cc)

        self.assertIn('poppy_client_pywrap.cxx', com_swig_python)
        self.assertIn('poppy_client_javawrap.cxx', com_swig_java)

        self.assertIn('-fno-omit-frame-pointer', com_swig_python_cxx)
        self.assertIn('-mcx16 -pipe -g', com_swig_python_cxx)
        self.assertIn('-DNDEBUG -D_FILE_OFFSET_BITS', com_swig_python_cxx)

        self.assertIn('-fno-omit-frame-pointer', com_swig_java_cxx)
        self.assertIn('-mcx16 -pipe -g', com_swig_java_cxx)
        self.assertIn('-DNDEBUG -D_FILE_OFFSET_BITS', com_swig_java_cxx)

        self.assertTrue(java_com_line)
        self.assertTrue(java_so_line)
        self.assertTrue(jar_line)

        self.assertIn('test_java_jar/java/lib/junit.jar', java_com_line)
        self.assertIn('com/soso/poppy/swig/*.java', java_com_line)
        self.assertIn('com/soso/poppy/*.java', java_com_line)

        whole_archive = ('--whole-archive build64_release/test_java_jar/'
                         'librpc_meta_info_proto.a build64_release/test_java_jar/'
                         'librpc_option_proto.a -Wl,--no-whole-archive')
        self.assertIn(whole_archive, java_so_line)
        self.assertGreater(jar_idx, java_com_idx)
        self.assertGreater(jar_idx, java_so_idx)


if __name__ == '__main__':
    blade_test.run(TestJavaJar)
