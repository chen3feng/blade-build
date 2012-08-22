"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the test module to test query function of blade.

"""


import os
import sys
sys.path.append('..')
import unittest
import subprocess
import blade.blade
from blade.blade import Blade
from blade_namespace import Namespace
from html_test_runner import HTMLTestRunner


class TestQuery(unittest.TestCase):
    """Test cc_library """
    def setUp(self):
        """setup method. """
        self.command = 'query'
        self.targets = ['...']
        self.query_targets = ['test_query:poppy']
        self.target_path = 'test_query'
        self.cur_dir = os.getcwd()
        os.chdir('./testdata')
        self.blade_path = '../../blade'
        self.working_dir = '.'
        self.current_building_path = 'build64_release'
        self.current_source_dir = '.'
        self.options = Namespace({'m' : '64',
                                  'profile' : 'release',
                                  'generate_dynamic' : True
                                 })
        self.direct_targets = []
        self.all_command_targets = []
        self.related_targets = {}
        blade.blade.blade = Blade(self.targets,
                                  self.blade_path,
                                  self.working_dir,
                                  self.current_building_path,
                                  self.current_source_dir,
                                  self.options,
                                  blade_command=self.command)
        self.blade = blade.blade.blade
        (self.direct_targets,
         self.all_command_targets) = self.blade.load_targets()
        self.blade.analyze_targets()
        self.all_targets = self.blade.get_all_targets_expanded()

    def tearDown(self):
        """tear down method. """
        os.chdir(self.cur_dir)

    def testLoadBuildsNotNone(self):
        """Test direct targets and all command targets are not none. """
        self.assertEqual(self.direct_targets, [])
        self.assertTrue(self.all_command_targets)

    def testQueryCorrectly(self):
        """Test query targets dependency relationship correctly. """
        self.assertTrue(self.all_targets)
        result_map = {}
        result_map = self.blade.query_helper(self.query_targets)
        all_targets = self.blade.get_all_targets_expanded()
        query_key = ('test_query', 'poppy')
        self.assertTrue(query_key in result_map.keys())
        deps = result_map.get(query_key, [])[0]
        depended_by = result_map.get(query_key, [])[1]

        self.assertTrue(deps)
        self.assertTrue(depended_by)

        dep_one_key = ('test_query', 'rpc_meta_info_proto')
        dep_second_key = ('test_query', 'static_resource')
        self.assertTrue(dep_one_key in deps)
        self.assertTrue(dep_second_key in deps)

        depended_one_key = ('test_query', 'poppy_client')
        depended_second_key = ('test_query', 'poppy_mock')
        self.assertTrue(depended_one_key in depended_by)
        self.assertTrue(depended_second_key in depended_by)


if __name__ == "__main__":
    suite_test = unittest.TestSuite()
    suite_test.addTests(
            [unittest.defaultTestLoader.loadTestsFromTestCase(TestQuery)])
    runner = unittest.TextTestRunner()
    runner.run(suite_test)
