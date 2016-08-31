# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: LI Yi <sincereli@tencent.com>
# Created:   September 27, 2013


"""
 This is the cu_target module which is the super class
 of all of the scons cu targets, like cu_library, cu_binary.

"""

import os
import blade
import configparse

import build_rules
from blade_util import var_to_list
from cc_targets import CcTarget


class CuTarget(CcTarget):
    """A scons cu target subclass.

    This class is derived from SconsCcTarget and it is the base class
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
        """Init method.

        Init the cu target.

        """
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
        """_get_cu_flags.

        Return the nvcc flags according to the BUILD file and other configs.

        """
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
        incs = self.data.get('incs', [])
        new_incs_list = [os.path.join(self.path, inc) for inc in incs]
        new_incs_list += self._export_incs_list()
        # Remove duplicate items in incs list and keep the order
        incs_list = []
        for inc in new_incs_list:
            new_inc = os.path.normpath(inc)
            if new_inc not in incs_list:
                incs_list.append(new_inc)

        return (nvcc_flags, incs_list)


    def _cu_objects_rules(self):
        """_cu_library rules. """
        env_name = self._env_name()
        var_name = self._var_name()
        flags_from_option, incs_list = self._get_cu_flags()
        incs_string = " -I".join(incs_list)
        flags_string = " ".join(flags_from_option)
        objs = []
        sources = []
        for src in self.srcs:
            obj = '%s_%s_object' % (var_name,
                                    self._regular_variable_name(src))
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
            self._write_rule('%s.Depends(%s, "%s")' % (
                             env_name,
                             obj,
                             self._target_file_path(src)))
            sources.append(self._target_file_path(src))
            objs.append(obj)
        self._write_rule('%s = [%s]' % (self._objs_name(), ','.join(objs)))
        return sources


class CuLibrary(CuTarget):
    """A scons cu target subclass

    This class is derived from SconsCuTarget and it generates the cu_library
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
        type = 'cu_library'
        CuTarget.__init__(self,
                          name,
                          type,
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
        """scons_rules.

        It outputs the scons rules according to user options.
        """
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
                       blade.blade,
                       kwargs)
    blade.blade.register_target(target)


build_rules.register_function(cu_library)


class CuBinary(CuTarget):
    """A scons cu target subclass

    This class is derived from SconsCuTarget and it generates the cu_binary
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
        type = 'cu_binary'
        CuTarget.__init__(self,
                          name,
                          type,
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
        """_cc_binary rules. """
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

        #self._write_rule('%s.Append(LINKFLAGS=str(version_obj[0]))' % env_name)
        self._write_rule('%s.Requires(%s, version_obj)' % (
                         env_name, var_name))

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.
        """
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
                      blade.blade,
                      kwargs)
    blade.blade.register_target(target)


build_rules.register_function(cu_binary)


class CuTest(CuBinary):
    """A scons cu target subclass

    This class is derived from SconsCuTarget and it generates the cu_test
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

        cc_test_config = configparse.blade_config.get_config('cc_test_config')
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
                    blade.blade,
                    kwargs)
    blade.blade.register_target(target)


build_rules.register_function(cu_test)
