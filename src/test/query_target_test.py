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
    """Test cc_library """
    def setUp(self):
        """setup method. """
        self.doSetUp('test_query', full_targets=['...'], command='query')
        self.query_targets = ['test_query:poppy']
        self.all_targets = self.blade.get_build_targets()

    def testQueryCorrectly(self):
        """Test query targets dependency relationship correctly. """
        self.assertTrue(self.all_targets)
        result_map = {}
        result_map = self.blade.query_helper(self.query_targets)
        all_targets = self.blade.get_build_targets()
        query_key = ('test_query', 'poppy')
        self.assertIn(query_key, result_map.keys())
        deps = result_map.get(query_key, [])[0]
        depended_by = result_map.get(query_key, [])[1]

        self.assertTrue(deps)
        self.assertTrue(depended_by)

        dep_one_key = ('test_query', 'rpc_meta_info_proto')
        dep_second_key = ('test_query', 'static_resource')
        self.assertIn(dep_one_key, deps)
        self.assertIn(dep_second_key, deps)

        depended_one_key = ('test_query', 'poppy_client')
        depended_second_key = ('test_query', 'poppy_mock')
        self.assertIn(depended_one_key, depended_by)
        self.assertIn(depended_second_key, depended_by)


if __name__ == '__main__':
    blade_test.run(TestQuery)
