"""
This is the test header dependency check for cc target.
"""


import blade_test


class TestHdrDepCheck(blade_test.TargetTest):
    """Test cc_binary."""
    def setUp(self):
        """setup method."""
        self.doSetUp('hdr_dep_check', target='...')

    def testErrorReport(self):
        """Test that rules are generated correctly."""
        self.assertFalse(self.runBlade('build', print_error=False))
        self.assertTrue(self.inBuildOutput('''For "hdr_dep_check/lib1.h", which belongs to ":lib1"'''))
        self.assertTrue(self.inBuildOutput('''"hdr_dep_check/lib1_impl.h" is a private header file of ":lib1"'''))
        self.assertTrue(self.inBuildOutput('''"hdr_dep_check/undeclared.h" is not declared in any cc target'''))


if __name__ == '__main__':
    blade_test.run(TestHdrDepCheck)
