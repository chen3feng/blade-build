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
        self.assertTrue(self.dryRun())

        com_lower_line = self.findCommand(['plowercase.cpp.o', '-c'])
        com_bison_line = self.findCommand(['bison', '-d', '-o'])
        com_flex_line = self.findCommand(['flex', '-R', '-o'])
        com_ll_static_line = self.findCommand(['line_parser.ll.cc.o', '-c'])
        com_yy_static_line = self.findCommand(['line_parser.yy.cc.o', '-c'])
        lex_yacc_depends_libs = self.findCommand('libparser.so')

        self.assertCxxFlags(com_lower_line)

        self.assertIn('line_parser.yy.cc', com_bison_line)
        self.assertIn('line_parser.ll.cc', com_flex_line)

        self.assertCxxFlags(com_ll_static_line)
        self.assertCxxFlags(com_yy_static_line)

        self.assertIn('liblowercase.so', lex_yacc_depends_libs)
        self.assertIn('line_parser.ll.cc.o', lex_yacc_depends_libs)
        self.assertIn('line_parser.yy.cc.o', lex_yacc_depends_libs)
        self.assertDynamicLinkFlags(lex_yacc_depends_libs)


if __name__ == '__main__':
    blade_test.run(TestLexYacc)
