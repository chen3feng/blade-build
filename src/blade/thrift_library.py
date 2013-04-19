"""

 Copyright (c) 2012 iQIYI Inc.
 Copyright (c) 2013 Tencent Inc.
 All rights reserved.

 Author: Jingxu Chen <chenjingxu@qiyi.com>
         Feng Chen <chen3feng@gmail.com>
 Date:   October 13, 2012

 A helper class to get the files generated from thrift IDL files.

"""

import os

import blade
import configparse
import console

from blade_util import var_to_list
from cc_targets import CcTarget
from thrift_helper import ThriftHelper

class ThriftLibrary(CcTarget):
    """A scons thrift library target subclass.

    This class is derived from SconsCcTarget.

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
                          '',
                          [], [], [], optimize, [], [],
                          blade,
                          kwargs)

        thrift_config = configparse.blade_config.get_config('thrift_config')
        thrift_lib = var_to_list(thrift_config['thrift_libs'])

        # Hardcode deps rule to thrift libraries.
        self._add_hardcode_library(thrift_lib)

        # Link all the symbols by default
        self.data['options']['link_all_symbols'] = True
        self.data['options']['deprecated'] = deprecated

        # For each thrift file initialize a ThriftHelper, which will be used
        # to get the source files generated from thrift file.
        self.thrift_helpers = {}
        for src in srcs:
            self.thrift_helpers[src] = ThriftHelper(
                    os.path.join(self.data['path'], src))

    def _check_thrift_srcs_name(self, srcs):
        """_check_thrift_srcs_name.

        Checks whether the thrift file's name ends with 'thrift'.

        """
        err = 0
        for src in srcs:
            base_name = os.path.basename(src)
            pos = base_name.rfind('.')
            if pos == -1:
                err = 1
                break
            file_suffix = base_name[pos + 1:]
            if file_suffix != 'thrift':
                err = 1
                break
        if err == 1:
            console.error_exit("invalid thrift file name %s" % src)

    def _thrift_gen_cpp_files(self, path, src):
        """_thrift_gen_cpp_files.

        Get the c++ files generated from thrift file.

        """

        return [self._target_file_path(path, f)
                for f in self.thrift_helpers[src].get_generated_cpp_files()]

    def _thrift_gen_py_files(self, path, src):
        """_thrift_gen_py_files.

        Get the python files generated from thrift file.

        """

        return [self._target_file_path(path, f)
                for f in self.thrift_helpers[src].get_generated_py_files()]

    def _thrift_gen_java_files(self, path, src):
        """_thrift_gen_java_files.

        Get the java files generated from thrift file.

        """

        return [self._target_file_path(path, f)
                for f in self.thrift_helpers[src].get_generated_java_files()]

    def _thrift_java_rules(self):
        """_thrift_java_rules.

        Generate scons rules for the java files from thrift file.

        """

        java_jar_dep_source_map =self.blade.get_java_jar_dep_source_map()
        self.sources_dependency_map = self.blade.get_sources_explict_dependency_map()
        self.sources_dependency_map[self.key] = []
        for src in self.data['srcs']:
            src_path = os.path.join(self.data['path'], src)
            thrift_java_src_files = self._thrift_gen_java_files(self.data['path'],
                                                                src)

            self._write_rule("%s.ThriftJava(%s, '%s')" % (
                    self._env_name(),
                    str(thrift_java_src_files),
                    src_path))

            java_jar_dep_source_map[self.key] = (
                     os.path.dirname(thrift_java_src_files[0]),
                     os.path.join(self.build_path, self.data['path']),
                     self.data['name'])

            self.sources_dependency_map[self.key].extend(thrift_java_src_files)

    def _thrift_python_rules(self):
        """_thrift_python_rules.

        Generate python files.

        """

        self.blade.python_binary_dep_source_map[self.key] = []
        self.blade.python_binary_dep_source_cmd[self.key] = []
        for src in self.data['srcs']:
            src_path = os.path.join(self.data['path'], src)
            thrift_py_src_files = self._thrift_gen_py_files(self.data['path'], src)
            py_cmd_var = "%s_python" % self._generate_variable_name(
                    self.data['path'], self.data['name'])
            self._write_rule("%s = %s.ThriftPython(%s, '%s')" % (
                    py_cmd_var,
                    self._env_name(),
                    str(thrift_py_src_files),
                    src_path))
            self.blade.python_binary_dep_source_cmd[self.key].append(py_cmd_var)
            self.blade.python_binary_dep_source_map[self.key].extend(
                    thrift_py_src_files)

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        # Build java source according to its option
        env_name = self._env_name()

        self.options = self.blade.get_options()
        self.direct_targets = self.blade.get_direct_targets()

        if (hasattr(self.options, 'generate_java')
                and self.options.generate_java) or (
                       self.data.get('options', {}).get('generate_java', False) or (
                              self.key in self.direct_targets)):
            self._thrift_java_rules()

        if (hasattr(self.options, 'generate_python')
                and self.options.generate_python) or (
                    self.data.get('options', {}).get('generate_python', False) or (
                              self.key in self.direct_targets)):
            self._thrift_python_rules()

        self._setup_cc_flags()

        sources = []
        obj_names = []
        for src in self.data['srcs']:
            thrift_cpp_files = self._thrift_gen_cpp_files(self.data['path'], src)
            thrift_cpp_src_files = [ f for f in thrift_cpp_files if f.endswith('.cpp') ]

            self._write_rule("%s.Thrift(%s, '%s')" % (
                    env_name,
                    str(thrift_cpp_files),
                    os.path.join(self.data['path'], src)))

            for thrift_cpp_src in thrift_cpp_src_files:
                obj_name = "%s_object" % self._generate_variable_name(
                    self.data['path'], thrift_cpp_src)
                obj_names.append(obj_name)
                self._write_rule(
                    "%s = %s.SharedObject(target = '%s' + top_env['OBJSUFFIX'], "
                    "source = '%s')" % (obj_name,
                                        env_name,
                                        thrift_cpp_src,
                                        thrift_cpp_src))
                sources.append(thrift_cpp_src)

        self._write_rule("%s = [%s]" % (self._objs_name(), ','.join(obj_names)))
        self._write_rule("%s.Depends(%s, %s)" % (
                         env_name, self._objs_name(), sources))

        self._cc_library()
        options = self.blade.get_options()
        if (hasattr(options, 'generate_dynamic') and options.generate_dynamic) or (
            self.data.get('options', {}).get('build_dynamic', False)):
            self._dynamic_cc_library()


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
    blade.blade.register_scons_target(thrift_library_target.key,
                                      thrift_library_target)


