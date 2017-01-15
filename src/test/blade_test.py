# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: CHEN Feng <phongchen@tencent.com>
# Date:   October 20, 2011

"""
 This is the main test module for all targets.
"""

import os
import subprocess
import sys
import unittest

sys.path.append('..')
import blade.blade
import blade.configparse
from blade.blade import Blade
from blade.configparse import BladeConfig
from blade.argparse import Namespace


class TargetTest(unittest.TestCase):
    """base class Test """
    def doSetUp(self, path, target='...', full_targets=None,
                command='build', generate_php=True, **kwargs):
        """setup method. """
        self.command = 'build'
        if full_targets:
            self.targets = full_targets
        else:
            self.targets = ['%s/%s' % (path, target)]
        self.target_path = path
        self.cur_dir = os.getcwd()
        os.chdir('./testdata')
        self.blade_path = '../../blade'
        self.working_dir = '.'
        self.current_building_path = 'build64_release'
        self.current_source_dir = '.'
        options = {
                'm': '64',
                'profile': 'release',
                'generate_dynamic': True,
                'generate_java': True,
                'generate_php': generate_php,
                'verbose': True
                }
        options.update(kwargs)
        self.options = Namespace(**options)
        self.direct_targets = []
        self.all_command_targets = []
        self.related_targets = {}

        # Init global configuration manager
        blade.configparse.blade_config = BladeConfig(self.current_source_dir)
        blade.configparse.blade_config.parse()

        blade.blade.blade = Blade(self.targets,
                                  self.blade_path,
                                  self.working_dir,
                                  self.current_building_path,
                                  self.current_source_dir,
                                  self.options,
                                  self.command)
        self.blade = blade.blade.blade
        (self.direct_targets,
         self.all_command_targets) = self.blade.load_targets()
        self.blade.analyze_targets()
        self.all_targets = self.blade.get_build_targets()
        self.scons_output_file = 'scons_output.txt'

    def tearDown(self):
        """tear down method. """
        try:
            os.remove('./SConstruct')
            os.remove(self.scons_output_file)
        except OSError:
            pass

        os.chdir(self.cur_dir)

    def testLoadBuildsNotNone(self):
        """Test direct targets and all command targets are not none. """
        self.assertEqual(self.direct_targets, [])
        self.assertTrue(self.all_command_targets)

    def dryRun(self):
        # We can use pipe to capture stdout, but keep the output file make it
        # easy debugging.
        p = subprocess.Popen('scons --dry-run > %s' % self.scons_output_file,
                             shell=True)
        try:
            p.wait()
            self.scons_output = open(self.scons_output_file)
            return p.returncode == 0
        except:
            print >>sys.stderr, 'Failed while dry running:\n%s' % sys.exc_info()
        return False

    if getattr(unittest.TestCase, 'assertIn', None) is None:
        # New asserts since 2.7, add for old version
        def _format_message(self, msg):
            if msg:
                return ', %s' % msg
            else:
                return ''

        def assertIn(self, a, b, msg=None):
            msg = self._format_message(msg)
            self.assertTrue(a in b, '"%s" in "%s"%s' % (a, b, msg))

        def assertNotIn(self, a, b, msg=None):
            msg = self._format_message(msg)
            self.assertTrue(a not in b, '"%s" not in "%s"%s' % (a, b, msg))

        def assertGreater(self, a, b, msg=None):
            msg = self._format_message(msg)
            self.assertTrue(a > b, '"%s" > "%s"%s' % (a, b, msg))

    def _assertCxxCommonFlags(self, cmdline):
        self.assertIn('-g', cmdline)
        self.assertIn('-fPIC', cmdline)

    def _assertCxxWarningFlags(self, cmdline):
        self.assertIn('-Wall -Wextra', cmdline)
        self.assertIn('-Wframe-larger-than=69632', cmdline)
        self.assertIn('-Werror=overloaded-virtual', cmdline)

    def _assertCxxNoWarningFlags(self, cmdline):
        self.assertNotIn('-Wall -Wextra', cmdline)
        self.assertNotIn('-Wframe-larger-than=69632', cmdline)
        self.assertNotIn('-Werror=overloaded-virtual', cmdline)

    def assertCxxFlags(self, cmdline):
        self._assertCxxCommonFlags(cmdline)
        self._assertCxxWarningFlags(cmdline)

    def assertNoWarningCxxFlags(self, cmdline):
        self._assertCxxCommonFlags(cmdline)
        self._assertCxxNoWarningFlags(cmdline)

    def assertLinkFlags(self, cmdline):
        self.assertIn('-static-libgcc -static-libstdc++', cmdline)

    def assertStaticLinkFlags(self, cmdline):
        self.assertNotIn('-shared', cmdline)

    def assertDynamicLinkFlags(self, cmdline):
        self.assertIn('-shared', cmdline)


def run(class_name):
    suite_test = unittest.TestSuite()
    suite_test.addTests(
            [unittest.defaultTestLoader.loadTestsFromTestCase(class_name)])
    runner = unittest.TextTestRunner()
    runner.run(suite_test)
