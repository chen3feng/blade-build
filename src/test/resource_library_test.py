# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the test module for resource_library target.

"""


import blade_test


class TestResourceLibrary(blade_test.TargetTest):
    """Test resource_library """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_resource_library')

    def testGenerateRules(self):
        """Test that rules are generated correctly. """
        self.assertTrue(self.dryRun())

        com_lower_line = self.findCommand('plowercase.cpp.o -c')
        com_forms_line = self.findCommand('forms_js_c.o -c')
        com_poppy_line = self.findCommand('poppy_html_c.o -c')
        static_so_line = self.findCommand(['-shared', 'libstatic_resource.so'])
        lower_depends_libs = self.findCommand(['-shared', 'liblowercase.so'])
        gen_forms_line = self.findCommand(['generate_resource_file', 'forms.js'])
        gen_poppy_line = self.findCommand(['generate_resource_file', 'poppy.html'])

        self.assertTrue(gen_forms_line)
        self.assertTrue(gen_poppy_line)

        self.assertCxxFlags(com_lower_line)
        self.assertNoWarningCxxFlags(com_forms_line)
        self.assertNoWarningCxxFlags(com_poppy_line)

        self.assertIn('forms_js_c.o', static_so_line)
        self.assertIn('poppy_html_c.o', static_so_line)

        self.assertDynamicLinkFlags(lower_depends_libs)
        self.assertIn('libstatic_resource.so', lower_depends_libs)


if __name__ == '__main__':
    blade_test.run(TestResourceLibrary)
