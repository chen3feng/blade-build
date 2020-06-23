# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: LI Yi <sincereli@tencent.com>
# Created:   September 27, 2013


"""
This module defines cu_library, cu_binary and cu_test rules
for cuda development.

"""

from __future__ import absolute_import

import os

from blade import build_manager
from blade import build_rules
from blade import config
from blade.blade_util import var_to_list
from blade.cc_targets import CcTarget


class CuTarget(CcTarget):
    """This class is derived from CcTarget and is the base class
    of cu_library, cu_binary etc.

    """

    def __init__(self,
                 name,
                 target_type,
                 srcs,
                 deps,
                 visibility,
                 warning,
                 defs,
                 incs,
                 extra_cppflags,
                 extra_linkflags,
                 kwargs):
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)
        extra_cppflags = var_to_list(extra_cppflags)
        extra_linkflags = var_to_list(extra_linkflags)

        super(CuTarget, self).__init__(
                name=name,
                type=type,
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                warning=warning,
                defs=defs,
                incs=incs,
                export_incs=[],
                options=[],
                extra_cppflags=extra_cppflags,
                extra_linkflags=extra_linkflags,
                kwargs=kwargs)

    def _get_cu_flags(self):
        """Return the nvcc flags according to the BUILD file and other configs. """
        nvcc_flags = []

        # Warnings
        if self.data.get('warning', '') == 'no':
            nvcc_flags.append('-w')

        # Defs
        defs = self.data.get('defs', [])
        nvcc_flags += [('-D' + macro) for macro in defs]

        # Optimize flags
        if (self.blade.get_options().profile == 'release' or
                self.data.get('always_optimize')):
            nvcc_flags += self._get_optimize_flags()

        # Incs
        incs = self._get_incs_list()

        return nvcc_flags, incs


class CuLibrary(CuTarget):
    """This class is derived from CuTarget and generates the cu_library
    rules according to user options.

    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 warning,
                 defs,
                 incs,
                 extra_cppflags,
                 extra_linkflags,
                 kwargs):
        super(CuLibrary, self).__init__(
                name=name,
                type='cu_library',
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                warning=warning,
                defs=defs,
                incs=incs,
                extra_cppflags=extra_cppflags,
                extra_linkflags=extra_linkflags,
                kwargs=kwargs)

    def ninja_rule(self):
        self.error('To be implemented')


def cu_library(name,
               srcs=[],
               deps=[],
               visibility=None,
               warning='yes',
               defs=[],
               incs=[],
               extra_cppflags=[],
               extra_linkflags=[],
               **kwargs):
    target = CuLibrary(
            name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            warning=warning,
            defs=defs,
            incs=incs,
            extra_cppflags=extra_cppflags,
            extra_linkflags=extra_linkflags,
            kwargs=kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(cu_library)


class CuBinary(CuTarget):
    """This class is derived from CuTarget and generates the cu_binary
    rules according to user options.

    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 warning,
                 defs,
                 incs,
                 extra_cppflags,
                 extra_linkflags,
                 kwargs):
        super(CuBinary, self).__init__(
                name=name,
                type='cu_binary',
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                warning=warning,
                defs=defs,
                incs=incs,
                extra_cppflags=extra_cppflags,
                extra_linkflags=extra_linkflags,
                kwargs=kwargs)

    def ninja_rule(self):
        self.error('To be implemented')


def cu_binary(name,
              srcs=[],
              deps=[],
              visibility=None,
              warning='yes',
              defs=[],
              incs=[],
              extra_cppflags=[],
              extra_linkflags=[],
              **kwargs):
    target = CuBinary(
            name=name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            warning=warning,
            defs=defs,
            incs=incs,
            extra_cppflags=extra_cppflags,
            extra_linkflags=extra_linkflags,
            kwargs=kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(cu_binary)


class CuTest(CuBinary):
    """This class is derived from CuBinary and generates the cu_test
    rules according to user options.

    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 warning,
                 defs,
                 incs,
                 extra_cppflags,
                 extra_linkflags,
                 testdata,
                 always_run,
                 exclusive,
                 kwargs):
        # pylint: disable=too-many-locals
        super(CuTest, self).__init__(
                name=name,
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                warning=warning,
                defs=defs,
                incs=incs,
                extra_cppflags=extra_cppflags,
                extra_linkflags=extra_linkflags,
                kwargs=kwargs)
        self.type = 'cu_test'
        self.data['testdata'] = var_to_list(testdata)
        self.data['always_run'] = always_run
        self.data['exclusive'] = exclusive

        cc_test_config = config.get_section('cc_test_config')
        gtest_lib = var_to_list(cc_test_config['gtest_libs'])
        gtest_main_lib = var_to_list(cc_test_config['gtest_main_libs'])

        # Hardcode deps rule to thirdparty gtest main lib.
        self._add_hardcode_library(gtest_lib)
        self._add_hardcode_library(gtest_main_lib)


def cu_test(
        name,
        srcs=[],
        deps=[],
        visibility=None,
        warning='yes',
        defs=[],
        incs=[],
        extra_cppflags=[],
        extra_linkflags=[],
        testdata=[],
        always_run=False,
        exclusive=False,
        **kwargs):
    target = CuTest(
            name=name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            warning=warning,
            defs=defs,
            incs=incs,
            extra_cppflags=extra_cppflags,
            extra_linkflags=extra_linkflags,
            testdata=testdata,
            always_run=always_run,
            exclusive=exclusive,
            kwargs=kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(cu_test)
