# Copyright (c) 2016 Tencent Inc.
# All rights reserved.
#
# Author: Li Wenting <wentingli@tencent.com>
# Date:   June 2, 2016

"""

This module defines sh_test target which executes a shell script.

"""

import os

import blade
import build_rules
import console
from blade_util import var_to_list
from blade_util import location_re
from target import Target


class ShellTest(Target):
    """ShellTest is derived from Target and used to execute a shell script.

    Normally by use of testdata you could establish test environment
    with all the necessary data and files placed in the runfiles directory
    and then refer to those files within the shell script directly.

    In addition to the regular files, the user is able to reference
    the output of another target in testdata using location references
    syntax.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 testdata,
                 kwargs):
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)
        testdata = var_to_list(testdata)

        Target.__init__(self,
                        name,
                        'sh_test',
                        srcs,
                        deps,
                        None,
                        blade.blade,
                        kwargs)

        self._process_test_data(testdata)

    def _process_test_data(self, testdata):
        """
        Process test data of which the source could be regular file
        or location reference.
        """
        self.data['testdata'], self.data['locations'] = [], []
        for td in testdata:
            if isinstance(td, tuple):
                src, dst = td
            elif isinstance(td, str):
                src, dst = td, ''
            else:
                console.error_exit('%s: Invalid testdata %s. Test data should '
                                   'be either str or tuple.' % (self.fullname, td))

            m = location_re.search(src)
            if m:
                key, type = self._add_location_reference_target(m)
                self.data['locations'].append((key, type, dst))
            else:
                self.data['testdata'].append(td)

    def _generate_test_data_rules(self):
        env_name = self._env_name()
        var_name = self._var_name('testdata')

        targets = self.blade.get_build_targets()
        sources = []
        for key, type, dst in self.data['locations']:
            target = targets[key]
            target_var = target._get_target_var(type)
            if not target_var:
                console.warning('%s: Location %s %s is missing. Ignored.' %
                                (self.fullname, key, type))
            else:
                sources.append('%s, %s.Value("%s")' % (target_var, env_name, dst))

        if sources:
            self._write_rule('%s = %s.ShellTestData(target = "%s.testdata", '
                             'source = [%s])' % (
                             var_name, env_name,
                             self._target_file_path(),
                             ', '.join(sources)))

    def scons_rules(self):
        self._clone_env()
        env_name = self._env_name()
        var_name = self._var_name()

        srcs = [self._source_file_path(s) for s in self.srcs]
        self._write_rule('%s = %s.ShellTest(target = "%s", source = %s)' % (
                         var_name, env_name,
                         self._target_file_path(), srcs))
        self._generate_test_data_rules()


def sh_test(name,
            srcs,
            deps=[],
            testdata=[],
            **kwargs):
    blade.blade.register_target(ShellTest(name,
                                          srcs,
                                          deps,
                                          testdata,
                                          kwargs))


build_rules.register_function(sh_test)
