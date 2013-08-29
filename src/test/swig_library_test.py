# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the test module for swig_library target.

"""


import blade_test


class TestSwigLibrary(blade_test.TargetTest):
    """Test swig_library """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_swig_library', generate_php=False)

    def testGenerateRules(self):
        """Test that rules are generated correctly. """
        self.all_targets = self.blade.analyze_targets()
        self.rules_buf = self.blade.generate_build_rules()

        cc_library_lower = (self.target_path, 'lowercase')
        poppy_client = (self.target_path, 'poppy_client')
        self.command_file = 'cmds.tmp'

        self.assertTrue(cc_library_lower in self.all_targets.keys())
        self.assertTrue(poppy_client in self.all_targets.keys())

        self.assertTrue(self.dryRun())

        com_lower_line = ''

        com_swig_python = ''
        com_swig_java = ''
        com_swig_python_cxx = ''
        com_swig_java_cxx = ''

        swig_python_so = ''
        swig_java_so = ''

        for line in self.scons_output:
            if 'plowercase.cpp.o -c' in line:
                com_lower_line = line
            if 'swig -python' in line:
                com_swig_python = line
            if 'swig -java' in line:
                com_swig_java = line
            if 'poppy_client_pywrap.cxx.o -c' in line:
                com_swig_python_cxx = line
            if 'poppy_client_javawrap.cxx.o -c' in line:
                com_swig_java_cxx = line
            if '_poppy_client.so -m64' in line:
                swig_python_so = line
            if 'libpoppy_client_java.so -m64' in line:
                swig_java_so = line

        self.assertCxxFlags(com_lower_line)

        self.assertTrue('poppy_client_pywrap.cxx' in com_swig_python)
        self.assertTrue('poppy_client_javawrap.cxx' in com_swig_java)

        self.assertCxxFlags(com_swig_python_cxx)
        self.assertCxxFlags(com_swig_java_cxx)

        self.assertDynamicLinkFlags(swig_python_so)
        self.assertDynamicLinkFlags(swig_java_so)


if __name__ == '__main__':
    blade_test.run(TestSwigLibrary)
