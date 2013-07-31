# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the test module for lex_yacc_library target.

"""


import blade_test


class TestLexYacc(blade_test.TargetTest):
    """Test lex_yacc """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_lex_yacc')

    def testGenerateRules(self):
        """Test that rules are generated correctly. """
        self.all_targets = self.blade.analyze_targets()
        self.rules_buf = self.blade.generate_build_rules()

        cc_library_lower = (self.target_path, 'lowercase')
        lex_yacc_library = (self.target_path, 'parser')
        self.command_file = 'cmds.tmp'

        self.assertTrue(cc_library_lower in self.all_targets.keys())
        self.assertTrue(lex_yacc_library in self.all_targets.keys())

        self.assertTrue(self.dryRun())

        com_lower_line = ''
        com_bison_line = ''
        com_flex_line = ''
        com_ll_static_line = ''
        com_yy_static_line = ''
        lex_yacc_depends_libs = ''
        for line in self.scons_output:
            if 'plowercase.cpp.o -c' in line:
                com_lower_line = line
            if 'bison -d -o' in line:
                com_bison_line = line
            if 'flex -R -t' in line:
                com_flex_line = line
            if 'line_parser.ll.cc.o -c' in line:
                com_ll_static_line = line
            if 'line_parser.yy.cc.o -c' in line:
                com_yy_static_line = line
            if 'libparser.so' in line:
                lex_yacc_depends_libs = line

        self.assertCxxFlags(com_lower_line)

        self.assertTrue('line_parser.yy.cc' in com_bison_line)
        self.assertTrue('line_parser.ll.cc' in com_flex_line)

        self.assertCxxFlags(com_ll_static_line)
        self.assertCxxFlags(com_yy_static_line)

        self.assertTrue('liblowercase.so' in lex_yacc_depends_libs)
        self.assertTrue('line_parser.ll.cc.o' in lex_yacc_depends_libs)
        self.assertTrue('line_parser.yy.cc.o' in lex_yacc_depends_libs)
        self.assertDynamicLinkFlags(lex_yacc_depends_libs)


if __name__ == '__main__':
    blade_test.run(TestLexYacc)
