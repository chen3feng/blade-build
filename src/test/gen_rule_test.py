# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the test module for cc_gen_rule target.

"""


import blade_test


class TestGenRule(blade_test.TargetTest):
    """Test gen_rule """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_gen_rule')

    def testGenerateRules(self):
        """Test that rules are generated correctly. """
        self.all_targets = self.blade.analyze_targets()
        self.rules_buf = self.blade.generate_build_rules()

        cc_library_lower = (self.target_path, 'lowercase')
        cc_library_upper = (self.target_path, 'uppercase')
        gen_rule = (self.target_path, 'process_media')
        self.command_file = 'cmds.tmp'

        self.assertIn(cc_library_lower, self.all_targets.keys())
        self.assertIn(cc_library_upper, self.all_targets.keys())
        self.assertIn(gen_rule, self.all_targets.keys())

        self.assertTrue(self.dryRun())

        com_lower_line = ''
        com_upper_line = ''

        lower_so_index = 0
        gen_rule_index = 0
        upper_so_index = 0
        index = 0

        for line in self.scons_output:
            index += 1
            if 'plowercase.cpp.o -c' in line:
                com_lower_line = line
            if 'puppercase.cpp.o -c' in line:
                com_upper_line = line
            if 'echo' in line:
                gen_rule_index = index
            if 'liblowercase.so -m64' in line:
                lower_so_index = index
            if 'libuppercase.so -m64' in line:
                upper_so_index = index

        self.assertCxxFlags(com_lower_line)
        self.assertCxxFlags(com_upper_line)

        self.assertGreater(gen_rule_index, lower_so_index)
        self.assertGreater(upper_so_index, gen_rule_index)


if __name__ == '__main__':
    blade_test.run(TestGenRule)
