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
                 warning,
                 defs,
                 incs,
                 extra_cppflags,
                 extra_linkflags,
                 blade,
                 kwargs):
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)
        extra_cppflags = var_to_list(extra_cppflags)
        extra_linkflags = var_to_list(extra_linkflags)

        CcTarget.__init__(self,
                          name,
                          target_type,
                          srcs,
                          deps,
                          None,
                          warning,
                          defs,
                          incs,
                          [], [],
                          extra_cppflags,
                          extra_linkflags,
                          blade,
                          kwargs)

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

    def _cu_objects_rules(self):
        env_name = self._env_name()
        flags_from_option, incs_list = self._get_cu_flags()
        incs_string = " -I".join(incs_list)
        flags_string = " ".join(flags_from_option)
        objs = []
        for src in self.srcs:
            obj = 'obj_%s' % self._var_name_of(src)
            target_path = os.path.join(
                self.build_path, self.path, '%s.objs' % self.name, src)
            self._write_rule(
                '%s = %s.NvccObject(NVCCFLAGS="-I%s %s", target="%s" + top_env["OBJSUFFIX"]'
                ', source="%s")' % (obj,
                                    env_name,
                                    incs_string,
                                    flags_string,
                                    target_path,
                                    self._target_file_path(src)))
            objs.append(obj)
        self._write_rule('%s = [%s]' % (self._objs_name(), ','.join(objs)))


class CuLibrary(CuTarget):
    """This class is derived from CuTarget and generates the cu_library
    rules according to user options.

    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 warning,
                 defs,
                 incs,
                 extra_cppflags,
                 extra_linkflags,
                 blade,
                 kwargs):
        CuTarget.__init__(self,
                          name,
                          'cu_library',
                          srcs,
                          deps,
                          warning,
                          defs,
                          incs,
                          extra_cppflags,
                          extra_linkflags,
                          blade,
                          kwargs)

    def scons_rules(self):
        """Generate scons rules according to user options. """
        self._prepare_to_generate_rule()
        self._cu_objects_rules()
        self._cc_library()


def cu_library(name,
               srcs=[],
               deps=[],
               warning='yes',
               defs=[],
               incs=[],
               extra_cppflags=[],
               extra_linkflags=[],
               **kwargs):
    target = CuLibrary(name,
                       srcs,
                       deps,
                       warning,
                       defs,
                       incs,
                       extra_cppflags,
                       extra_linkflags,
                       build_manager.instance,
                       kwargs)
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
                 warning,
                 defs,
                 incs,
                 extra_cppflags,
                 extra_linkflags,
                 blade,
                 kwargs):
        CuTarget.__init__(self,
                          name,
                          'cu_binary',
                          srcs,
                          deps,
                          warning,
                          defs,
                          incs,
                          extra_cppflags,
                          extra_linkflags,
                          blade,
                          kwargs)

    def _cc_binary(self):
        env_name = self._env_name()
        var_name = self._var_name()

        (link_all_symbols_lib_list,
         lib_str,
         whole_link_flags) = self._get_static_deps_lib_list()
        if whole_link_flags:
            self._write_rule(
                '%s.Append(LINKFLAGS=[%s])' % (env_name, whole_link_flags))

        if self.data.get('export_dynamic'):
            self._write_rule(
                '%s.Append(LINKFLAGS="-rdynamic")' % env_name)

        self._setup_link_flags()

        self._write_rule('{0}.Replace('
                         'CC={0}["NVCC"], '
                         'CPP={0}["NVCC"], '
                         'CXX={0}["NVCC"], '
                         'LINK={0}["NVCC"])'.format(env_name))

        self._write_rule('%s = %s.Program("%s", %s, %s)' % (
            var_name,
            env_name,
            self._target_file_path(),
            self._objs_name(),
            lib_str))
        self._write_rule('%s.Depends(%s, %s)' % (
            env_name,
            var_name,
            self._objs_name()))

        if link_all_symbols_lib_list:
            self._write_rule('%s.Depends(%s, [%s])' % (
                env_name, var_name, ', '.join(link_all_symbols_lib_list)))

        # self._write_rule('%s.Append(LINKFLAGS=str(version_obj[0]))' % env_name)
        self._write_rule('%s.Requires(%s, version_obj)' % (
            env_name, var_name))

    def scons_rules(self):
        """Generate scons rules according to user options. """
        self._prepare_to_generate_rule()
        self._cu_objects_rules()
        self._cc_binary()


def cu_binary(name,
              srcs=[],
              deps=[],
              warning='yes',
              defs=[],
              incs=[],
              extra_cppflags=[],
              extra_linkflags=[],
              **kwargs):
    target = CuBinary(name,
                      srcs,
                      deps,
                      warning,
                      defs,
                      incs,
                      extra_cppflags,
                      extra_linkflags,
                      build_manager.instance,
                      kwargs)
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
                 warning,
                 defs,
                 incs,
                 extra_cppflags,
                 extra_linkflags,
                 testdata,
                 always_run,
                 exclusive,
                 blade,
                 kwargs):
        # pylint: disable=too-many-locals
        CuBinary.__init__(self,
                          name,
                          srcs,
                          deps,
                          warning,
                          defs,
                          incs,
                          extra_cppflags,
                          extra_linkflags,
                          blade,
                          kwargs)
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


def cu_test(name,
            srcs=[],
            deps=[],
            warning='yes',
            defs=[],
            incs=[],
            extra_cppflags=[],
            extra_linkflags=[],
            testdata=[],
            always_run=False,
            exclusive=False,
            **kwargs):
    target = CuTest(name,
                    srcs,
                    deps,
                    warning,
                    defs,
                    incs,
                    extra_cppflags,
                    extra_linkflags,
                    testdata,
                    always_run,
                    exclusive,
                    build_manager.instance,
                    kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(cu_test)
