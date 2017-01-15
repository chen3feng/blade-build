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
        self.all_targets = self.blade.analyze_targets()
        self.rules_buf = self.blade.generate_build_rules()

        cc_library_lower = (self.target_path, 'lowercase')
        resource_library = (self.target_path, 'static_resource')
        self.command_file = 'cmds.tmp'

        self.assertIn(cc_library_lower, self.all_targets.keys())
        self.assertIn(resource_library, self.all_targets.keys())

        self.assertTrue(self.dryRun())

        com_lower_line = ''
        com_forms_line = ''
        com_poppy_line = ''
        static_so_line = ''
        lower_depends_libs = ''
        gen_forms_line = ''
        gen_poppy_line = ''
        for line in self.scons_output:
            if 'plowercase.cpp.o -c' in line:
                com_lower_line = line
            if 'forms_js_c.o -c' in line:
                com_forms_line = line
            if 'poppy_html_c.o -c' in line:
                com_poppy_line = line
            if 'libstatic_resource.so -m64' in line:
                static_so_line = line
            if 'liblowercase.so -m64' in line:
                lower_depends_libs = line
            if 'generate_resource_file' in line:
                if 'forms.js' in line:
                    gen_forms_line = line
                elif 'poppy.html' in line:
                    gen_poppy_line = line

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
