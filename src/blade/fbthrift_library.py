# Copyright (c) 2012 iQIYI Inc.
# Copyright (c) 2013 Tencent Inc.
# Copyright (c) 2014 Huahang Liu
#
# All rights reserved.
#
# Author: Jingxu Chen <chenjingxu@qiyi.com>
#         Feng Chen <chen3feng@gmail.com>
#         Huahang Liu <liuhuahang@zerus.co>
#
# Date:   June 28, 2014


"""
 A helper class to get the files generated from thrift IDL files.

 This works with the new thrift compiler and library from Facebook's
 own branch https://github.com/facebook/fbthrift

"""


import os

import blade
import configparse
import console

import build_rules
import java_jar_target
import py_targets

from blade_util import var_to_list
from cc_targets import CcTarget
from fbthrift_helper import FBThriftHelper


class FBThriftLibrary(CcTarget):
    """A scons thrift library target subclass.

    This class is derived from CcTarget.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 optimize,
                 deprecated,
                 blade,
                 kwargs):
        """Init method.

        Init the thrift target.

        """
        srcs = var_to_list(srcs)
        self._check_thrift_srcs_name(srcs)
        CcTarget.__init__(self,
                          name,
                          'fbthrift_library',
                          srcs,
                          deps,
                          '',
                          [], [], [], optimize, [], [],
                          blade,
                          kwargs)

        fbthrift_config = configparse.blade_config.get_config('fbthrift_config')
        fbthrift_libs = var_to_list(fbthrift_config['fbthrift_libs'])
        fbthrift1_bin = fbthrift_config['fbthrift1']
        fbthrift2_bin = fbthrift_config['fbthrift2']


        # Hardcode deps rule to thrift libraries.
        self._add_hardcode_library(fbthrift_libs)

        # Link all the symbols by default
        self.data['link_all_symbols'] = True

        # For each thrift file initialize a FBThriftHelper, which will be used
        # to get the source files generated from thrift file.
        self.fbthrift_helpers = {}
        for src in srcs:
            self.fbthrift_helpers[src] = FBThriftHelper(
                    os.path.join(self.path, src))

    def _check_thrift_srcs_name(self, srcs):
        """_check_thrift_srcs_name.

        Checks whether the thrift file's name ends with 'thrift'.

        """
        error = 0
        for src in srcs:
            base_name = os.path.basename(src)
            pos = base_name.rfind('.')
            if pos == -1:
                console.error('invalid thrift file name %s' % src)
                error += 1
            file_suffix = base_name[pos + 1:]
            if file_suffix != 'thrift':
                console.error('invalid thrift file name %s' % src)
                error += 1
        if error > 0:
            console.error_exit('invalid thrift file names found.')

    def _generate_header_files(self):
        """Whether this target generates header files during building."""
        return True

    def _thrift_gen_cpp_files(self, path, src):
        """_thrift_gen_cpp_files.

        Get the c++ files generated from thrift file.

        """
        return [self._target_file_path(path, f)
                for f in self.fbthrift_helpers[src].get_generated_cpp_files()]

    def _thrift_gen_cpp2_files(self, path, src):
        """_thrift_gen_cpp2_files.

        Get the c++ files generated from thrift file.

        """
        return [self._target_file_path(path, f)
                for f in self.fbthrift_helpers[src].get_generated_cpp2_files()]

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        # Build java source according to its option
        env_name = self._env_name()

        self.options = self.blade.get_options()
        self.direct_targets = self.blade.get_direct_targets()

        self._setup_cc_flags()

        sources = []
        obj_names = []
        for src in self.srcs:
            thrift_cpp_files = self._thrift_gen_cpp_files(self.path, src)
            thrift_cpp_src_files = [f for f in thrift_cpp_files if f.endswith('.cpp')]

            thrift_cpp2_files = self._thrift_gen_cpp2_files(self.path, src)
            thrift_cpp2_src_files = [f for f in thrift_cpp2_files if f.endswith('.cpp')]

            self._write_rule('%s.FBThrift1(%s, "%s")' % (
                    env_name,
                    str(thrift_cpp_files),
                    os.path.join(self.path, src)))

            self._write_rule('%s.FBThrift2(%s, "%s")' % (
                    env_name,
                    str(thrift_cpp2_files),
                    os.path.join(self.path, src)))

            for thrift_cpp_src in thrift_cpp_src_files:
                obj_name = '%s_object' % self._generate_variable_name(
                    self.path, thrift_cpp_src)
                obj_names.append(obj_name)
                self._write_rule(
                    '%s = %s.SharedObject(target="%s" + top_env["OBJSUFFIX"], '
                    'source="%s")' % (obj_name,
                                      env_name,
                                      thrift_cpp_src,
                                      thrift_cpp_src))
                sources.append(thrift_cpp_src)

            for thrift_cpp_src in thrift_cpp2_src_files:
                obj_name = '%s_object' % self._generate_variable_name(
                    self.path, thrift_cpp_src)
                obj_names.append(obj_name)
                self._write_rule(
                    '%s = %s.SharedObject(target="%s" + top_env["OBJSUFFIX"], '
                    'source="%s")' % (obj_name,
                                      env_name,
                                      thrift_cpp_src,
                                      thrift_cpp_src))
                sources.append(thrift_cpp_src)

        self._write_rule('%s = [%s]' % (self._objs_name(), ','.join(obj_names)))
        self._write_rule('%s.Depends(%s, %s)' % (
                         env_name, self._objs_name(), sources))

        self._cc_library()
        options = self.blade.get_options()
        if (getattr(options, 'generate_dynamic', False) or
            self.data.get('build_dynamic')):
            self._dynamic_cc_library()


def fbthrift_library(name,
                     srcs=[],
                     deps=[],
                     optimize=[],
                     deprecated=False,
                     **kwargs):
    """fbthrift_library target. """
    fbthrift_library_target = FBThriftLibrary(name,
                                              srcs,
                                              deps,
                                              optimize,
                                              deprecated,
                                              blade.blade,
                                              kwargs)
    blade.blade.register_target(fbthrift_library_target)


build_rules.register_function(fbthrift_library)
