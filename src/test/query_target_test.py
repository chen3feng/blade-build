# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
This is the test module to test query function of blade.
"""

import blade_test


class TestQuery(blade_test.TargetTest):
    """Test the query command."""
    def setUp(self):
        """setup method."""
        self.doSetUp('test_query', full_targets=['.:...'])


if __name__ == '__main__':
    blade_test.run(TestQuery)
