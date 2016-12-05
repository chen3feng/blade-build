# Copyright (c) 2012 iQIYI Inc.
# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Jingxu Chen <chenjingxu@qiyi.com>
#         Feng Chen <chen3feng@gmail.com>
# Date:   October 13, 2012


"""
The module defines thrift_library target to generate code in
different languages from .thrift file.

"""


import os

import blade
import configparse
import console

import build_rules

from blade_util import var_to_list
from cc_targets import CcTarget
from thrift_helper import ThriftHelper


class ThriftLibrary(CcTarget):
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
                          'thrift_library',
                          srcs,
                          deps,
                          None,
                          '',
                          [], [], [], optimize, [], [],
                          blade,
                          kwargs)
        self.data['python_vars'] = []
        self.data['python_sources'] = []

        thrift_config = configparse.blade_config.get_config('thrift_config')
        thrift_lib = var_to_list(thrift_config['thrift_libs'])
        # Hardcode deps rule to thrift libraries.
        self._add_hardcode_library(thrift_lib)

        # Link all the symbols by default
        self.data['link_all_symbols'] = True
        self.data['deprecated'] = deprecated
        self.data['java_sources_explict_dependency'] = []

        # For each thrift file initialize a ThriftHelper, which will be used
        # to get the source files generated from thrift file.
        self.thrift_helpers = {}
        for src in srcs:
            self.thrift_helpers[src] = ThriftHelper(self.path, src)

    def _check_thrift_srcs_name(self, srcs):
        """Check whether the thrift file's name ends with .thrift. """
        for src in srcs:
            if not src.endswith('.thrift'):
                console.error_exit('%s: Invalid thrift file %s' % (
                                   self.fullname, src))

    def _generate_header_files(self):
        """Whether this target generates header files during building."""
        return True

    def _thrift_gen_cpp_files(self, src):
        """_thrift_gen_cpp_files.

        Get the c++ files generated from thrift file.

        """
        files = []
        for f in self.thrift_helpers[src].get_generated_cpp_files():
            files.append(self._target_file_path(f))
        return files

    def _thrift_gen_py_files(self, src):
        """_thrift_gen_py_files.

        Get the python files generated from thrift file.

        """
        files = []
        for f in self.thrift_helpers[src].get_generated_py_files():
            files.append(self._target_file_path(f))
        return files

    def _thrift_gen_java_files(self, src):
        """_thrift_gen_java_files.

        Get the java files generated from thrift file.

        """
        files = []
        for f in self.thrift_helpers[src].get_generated_java_files():
            files.append(self._target_file_path(f))
        return files

    def _thrift_java_rules(self):
        """_thrift_java_rules.

        Generate scons rules for the java files from thrift file.

        """
        for src in self.srcs:
            thrift_java_src_files = self._thrift_gen_java_files(src)
            self._write_rule('%s.ThriftJava(%s, "%s")' % (
                    self._env_name(),
                    thrift_java_src_files,
                    os.path.join(self.path, src)))

            self.data['java_sources'] = (
                     os.path.dirname(thrift_java_src_files[0]),
                     os.path.join(self.build_path, self.path),
                     self.name)
            self.data['java_sources_explict_dependency'] += thrift_java_src_files

    def _thrift_python_rules(self):
        """_thrift_python_rules.

        Generate python files.

        """
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            thrift_py_src_files = self._thrift_gen_py_files(src)
            py_cmd_var = self._var_name('python')
            self._write_rule('%s = %s.ThriftPython(%s, "%s")' % (
                    py_cmd_var,
                    self._env_name(),
                    str(thrift_py_src_files),
                    src_path))
            self.data['python_vars'].append(py_cmd_var)
            self.data['python_sources'] += thrift_py_src_files

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()
        env_name = self._env_name()

        options = self.blade.get_options()
        direct_targets = self.blade.get_direct_targets()

        if (getattr(options, 'generate_java', False) or
            self.data.get('generate_java') or
            self.key in direct_targets):
            self._thrift_java_rules()

        if (getattr(options, 'generate_python', False) or
            self.data.get('generate_python') or
            self.key in direct_targets):
            self._thrift_python_rules()

        self._setup_cc_flags()

        sources = []
        obj_names = []
        for src in self.srcs:
            thrift_cpp_files = self._thrift_gen_cpp_files(src)
            thrift_cpp_src_files = [f for f in thrift_cpp_files if f.endswith('.cpp')]

            self._write_rule('%s.Thrift(%s, "%s")' % (
                             env_name,
                             thrift_cpp_files,
                             os.path.join(self.path, src)))

            for thrift_cpp_src in thrift_cpp_src_files:
                obj_name = '%s_object' % self._var_name_of(thrift_cpp_src)
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


def thrift_library(name,
                   srcs=[],
                   deps=[],
                   optimize=[],
                   deprecated=False,
                   **kwargs):
    """thrift_library target. """
    thrift_library_target = ThriftLibrary(name,
                                          srcs,
                                          deps,
                                          optimize,
                                          deprecated,
                                          blade.blade,
                                          kwargs)
    blade.blade.register_target(thrift_library_target)


build_rules.register_function(thrift_library)
