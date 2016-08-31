# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""Define swig_library target
"""


import os
import blade

import console
import build_rules
from cc_targets import CcTarget


class SwigLibrary(CcTarget):
    """A scons cc target subclass.

    This class is derived from SconsCCTarget.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 warning,
                 java_package,
                 java_lib_packed,
                 optimize,
                 extra_swigflags,
                 blade,
                 kwargs):
        """Init method.

        Init the cc target.

        """
        CcTarget.__init__(self,
                          name,
                          'swig_library',
                          srcs,
                          deps,
                          None,
                          warning,
                          [], [], [], optimize, extra_swigflags, [],
                          blade,
                          kwargs)
        self.data['cpperraswarn'] = warning
        self.data['java_package'] = java_package
        self.data['java_lib_packed'] = java_lib_packed
        self.data['java_dep_var'] = []
        self.data['java_sources_explict_dependency'] = []
        self.data['python_vars'] = []
        self.data['python_sources'] = []

        scons_platform = self.blade.get_scons_platform()
        self.php_inc_list = scons_platform.get_php_include()
        self.options = self.blade.get_options()

    def _pyswig_gen_python_file(self, path, src):
        """Generate swig python file for python. """
        swig_name = src[:-2]
        return os.path.join(self.build_path, path, '%s.py' % swig_name)

    def _pyswig_gen_file(self, path, src):
        """Generate swig cxx files for python. """
        swig_name = src[:-2]
        return os.path.join(self.build_path, path, '%s_pywrap.cxx' % swig_name)

    def _javaswig_gen_file(self, path, src):
        """Generate swig cxx files for java. """
        swig_name = src[:-2]
        return os.path.join(self.build_path, path, '%s_javawrap.cxx' % swig_name)

    def _phpswig_gen_file(self, path, src):
        """Generate swig cxx files for php. """
        swig_name = src[:-2]
        return os.path.join(self.build_path, path, '%s_phpwrap.cxx' % swig_name)

    def _swig_extract_dependency_files(self, src):
        dep = []
        for line in open(src):
            if line.startswith('#include') or line.startswith('%include'):
                line = line.split(' ')[1].strip("""'"\r\n""")
                if not ('<' in line or line in dep):
                    dep.append(line)
        return [i for i in dep if os.path.exists(i)]

    def _swig_library_rules_py(self):
        """_swig_library_rules_py.
        """
        env_name = self._env_name()
        var_name = self._var_name('dynamic_py')

        obj_names_py = []
        flag_list = []
        warning = self.data.get('cpperraswarn', '')
        flag_list.append(('cpperraswarn', warning))
        pyswig_flags = ''
        for flag in flag_list:
            if flag[0] == 'cpperraswarn':
                if flag[1] == 'yes':
                    pyswig_flags += ' -cpperraswarn'

        self._write_rule('%s.Append(SWIGPYTHONFLAGS="%s")' % (env_name, pyswig_flags))
        self._setup_cc_flags()

        dep_files = []
        dep_files_map = {}
        for src in self.srcs:
            pyswig_src = self._pyswig_gen_file(self.path, src)
            self._write_rule('%s.SwigPython(["%s"], "%s")' % (
                    env_name,
                    pyswig_src,
                    os.path.join(self.path, src)))
            self.data['python_sources'].append(
                    self._pyswig_gen_python_file(self.path, src))
            obj_name_py = '%s_object' % self._var_name_of(src, 'python')
            obj_names_py.append(obj_name_py)

            self._write_rule(
                '%s = %s.SharedObject(target="%s" + top_env["OBJSUFFIX"], '
                'source="%s")' % (obj_name_py,
                                  env_name,
                                  pyswig_src,
                                  pyswig_src))
            self.data['python_vars'].append(obj_name_py)
            dep_files = self._swig_extract_dependency_files(
                                os.path.join(self.path, src))
            self._write_rule('%s.Depends("%s", %s)' % (
                             env_name,
                             pyswig_src,
                             dep_files))
            dep_files_map[os.path.join(self.path, src)] = dep_files

        objs_name = self._objs_name()
        objs_name_py = '%s_py' % objs_name
        self._write_rule('%s = [%s]' % (objs_name_py, ','.join(obj_names_py)))

        target_path = self._target_file_path()
        target_lib = os.path.basename(target_path)
        if not target_lib.startswith('_'):
            target_lib = '_%s' % target_lib
        target_path_py = os.path.join(os.path.dirname(target_path), target_lib)

        (link_all_symbols_lib_list,
         lib_str,
         whole_link_flags) = self._get_static_deps_lib_list()
        if whole_link_flags:
            self._write_rule(
                    '%s.Append(LINKFLAGS=[%s])' % (env_name, whole_link_flags))

        if self.srcs or self.expanded_deps:
            self._write_rule('%s = %s.SharedLibrary("%s", %s, %s, SHLIBPREFIX = "")'
                    % (var_name,
                       env_name,
                       target_path_py,
                       objs_name_py,
                       lib_str))
            self.data['python_sources'].append('%s.so' % target_path_py)
            self.data['python_vars'].append(var_name)

        if link_all_symbols_lib_list:
            self._write_rule('%s.Depends(%s, [%s])' % (
                env_name, var_name, ', '.join(link_all_symbols_lib_list)))

        return dep_files_map

    def _swig_library_rules_java(self, dep_files_map):
        """_swig_library_rules_java. """
        env_name = self._env_name()
        var_name = self._var_name('dynamic_java')

        # Append -fno-strict-aliasing flag to cxxflags and cppflags
        self._write_rule('%s.Append(CPPFLAGS = ["-fno-strict-aliasing"])' % env_name)
        build_jar = self.data.get('generate_java')

        flag_list = []
        flag_list.append(('cpperraswarn', self.data.get('cpperraswarn', '')))
        flag_list.append(('package', self.data.get('java_package', '')))
        java_lib_packed = self.data.get('java_lib_packed', False)
        flag_list.append(('java_lib_packed', java_lib_packed))
        javaswig_flags = ''
        depend_outdir = False
        out_dir = os.path.join(self.build_path, self.path)
        for flag in flag_list:
            if flag[0] == 'cpperraswarn':
                if flag[1] == 'yes':
                    javaswig_flags += ' -cpperraswarn'
            if flag[0] == 'java_lib_packed':
                if flag[1]:
                    java_lib_packed = True
            if flag[0] == 'package':
                if flag[1]:
                    javaswig_flags += ' -package %s' % flag[1]
                    package_dir = flag[1].replace('.', '/')
                    out_dir = os.path.join(self.build_path,
                                           self.path, package_dir)
                    out_dir_dummy = os.path.join(out_dir, 'dummy_file')
                    javaswig_flags += ' -outdir %s' % out_dir
                    swig_outdir_cmd = '%s_swig_out_cmd_var' % var_name
                    if not os.path.exists(out_dir):
                        depend_outdir = True
                        self._write_rule('%s = %s.Command("%s", "", [Mkdir("%s")])' % (
                                swig_outdir_cmd,
                                env_name,
                                out_dir_dummy,
                                out_dir))
                        self.data['java_dep_var'].append(swig_outdir_cmd)
                    if build_jar:
                        self.data['java_sources'] = (
                                out_dir,
                                os.path.join(self.build_path, self.path),
                                self.name)

        self._write_rule('%s.Append(SWIGJAVAFLAGS="%s")' % (env_name, javaswig_flags))
        self._swig_library_rules_java_helper(depend_outdir, build_jar,
                                             java_lib_packed, out_dir,
                                             dep_files_map)

    def _swig_library_rules_java_helper(self,
                                        dep_outdir,
                                        java_build_jar,
                                        lib_packed,
                                        out_dir,
                                        dep_files_map):
        env_name = self._env_name()
        var_name = self._var_name('dynamic_java')
        depend_outdir = dep_outdir
        build_jar = java_build_jar
        java_lib_packed = lib_packed
        env_name = self._env_name()
        out_dir_dummy = os.path.join(out_dir, 'dummy_file')
        obj_names_java = []

        scons_platform = self.blade.get_scons_platform()
        java_includes = scons_platform.get_java_include()
        if java_includes:
            self._write_rule('%s.Append(CPPPATH=%s)' % (env_name, java_includes))

        dep_files = []
        for src in self.srcs:
            javaswig_src = self._javaswig_gen_file(self.path, src)
            src_basename = os.path.basename(src)
            javaswig_var = '%s_%s' % (
                    var_name, self._regular_variable_name(src_basename))
            self._write_rule('%s = %s.SwigJava(["%s"], "%s")' % (
                    javaswig_var,
                    env_name,
                    javaswig_src,
                    os.path.join(self.path, src)))
            self.data['java_sources_explict_dependency'].append(javaswig_src)
            if depend_outdir:
                self._write_rule('%s.Depends(%s, "%s")' % (
                        env_name,
                        javaswig_var,
                        out_dir_dummy))
            self.data['java_dep_var'].append(javaswig_var)

            obj_name_java = '%s_object' % self._var_name_of(src, 'dynamic_java')
            obj_names_java.append(obj_name_java)

            self._write_rule(
                    '%s = %s.SharedObject(target="%s" + top_env["OBJSUFFIX"], '
                    'source="%s")' % (
                            obj_name_java,
                            env_name,
                            javaswig_src,
                            javaswig_src))

            dep_key = os.path.join(self.path, src)
            if dep_key in dep_files_map:
                dep_files = dep_files_map[dep_key]
            else:
                dep_files = self._swig_extract_dependency_files(dep_key)
            self._write_rule('%s.Depends("%s", %s)' % (
                             env_name,
                             javaswig_src,
                             dep_files))

        objs_name = self._objs_name()
        objs_name_java = '%s_dynamic_java' % objs_name
        self._write_rule('%s = [%s]' % (objs_name_java,
                                        ','.join(obj_names_java)))

        target_path_java = '%s_java' % self._target_file_path()

        (link_all_symbols_lib_list,
         lib_str,
         whole_link_flags) = self._get_static_deps_lib_list()

        if self.srcs or self.expanded_deps:
            self._write_rule('%s = %s.SharedLibrary("%s", %s, %s)' % (
                    var_name,
                    env_name,
                    target_path_java,
                    objs_name_java,
                    lib_str))

        if link_all_symbols_lib_list:
            self._write_rule('%s.Depends(%s, [%s])' % (
                env_name, var_name, ', '.join(link_all_symbols_lib_list)))

        if build_jar and java_lib_packed:
            lib_dir = os.path.dirname(target_path_java)
            lib_name = os.path.basename(target_path_java)
            lib_name = 'lib%s.so' % lib_name
            self.data['jar_packing_file'] = (
                    os.path.join(lib_dir, lib_name), self.name)

    def _swig_library_rules_php(self, dep_files_map):
        env_name = self._env_name()
        var_name = self._var_name()
        obj_names_php = []

        flag_list = []
        warning = self.data.get('cpperraswarn', '')
        flag_list.append(('cpperraswarn', warning))
        phpswig_flags = ''
        for flag in flag_list:
            if flag[0] == 'cpperraswarn':
                if flag[1] == 'yes':
                    phpswig_flags += ' -cpperraswarn'

        self._write_rule('%s.Append(SWIGPHPFLAGS="%s")' % (env_name, phpswig_flags))
        if self.php_inc_list:
            self._write_rule('%s.Append(CPPPATH=%s)' % (env_name, self.php_inc_list))

        dep_files = []
        dep_files_map = {}
        for src in self.srcs:
            phpswig_src = self._phpswig_gen_file(self.path, src)
            self._write_rule('%s.SwigPhp(["%s"], "%s")' % (
                    env_name,
                    phpswig_src,
                    os.path.join(self.path, src)))
            obj_name_php = '%s_object' % self._var_name_of(src, 'php')
            obj_names_php.append(obj_name_php)

            self._write_rule(
                '%s = %s.SharedObject(target="%s" + top_env["OBJSUFFIX"], '
                'source="%s")' % (obj_name_php,
                                  env_name,
                                  phpswig_src,
                                  phpswig_src))

            dep_key = os.path.join(self.path, src)
            if dep_key in dep_files_map:
                dep_files = dep_files_map[dep_key]
            else:
                dep_files = self._swig_extract_dependency_files(dep_key)
            self._write_rule('%s.Depends("%s", %s)' % (
                             env_name,
                             phpswig_src,
                             dep_files))

        objs_name = self._objs_name()
        objs_name_php = '%s_php' % objs_name

        self._write_rule('%s = [%s]' % (objs_name_php, ','.join(obj_names_php)))

        target_path = self._target_file_path()
        target_lib = os.path.basename(target_path)
        target_path_php = os.path.join(os.path.dirname(target_path), target_lib)

        (link_all_symbols_lib_list,
         lib_str,
         whole_link_flags) = self._get_static_deps_lib_list()

        if self.srcs or self.expanded_deps:
            self._write_rule('%s = %s.SharedLibrary("%s", %s, %s, SHLIBPREFIX="")' % (
                    var_name,
                    env_name,
                    target_path_php,
                    objs_name_php,
                    lib_str))

        if link_all_symbols_lib_list:
            self._write_rule('%s.Depends(%s, [%s])' % (
                env_name, var_name, ', '.join(link_all_symbols_lib_list)))

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        dep_files_map = {}
        dep_files_map = self._swig_library_rules_py()
        if (getattr(self.options, 'generate_java', False) or
            self.data.get('generate_java')):
            self._swig_library_rules_java(dep_files_map)
        if getattr(self.options, 'generate_php', False):
            if not self.php_inc_list:
                console.error_exit('failed to build //%s:%s, please install php modules' % (
                           self.path, self.name))
            else:
                self._swig_library_rules_php(dep_files_map)


def swig_library(name,
                 srcs=[],
                 deps=[],
                 warning='',
                 java_package='',
                 java_lib_packed=False,
                 optimize=[],
                 extra_swigflags=[],
                 **kwargs):
    """swig_library target. """
    target = SwigLibrary(name,
                         srcs,
                         deps,
                         warning,
                         java_package,
                         java_lib_packed,
                         optimize,
                         extra_swigflags,
                         blade.blade,
                         kwargs)
    blade.blade.register_target(target)


build_rules.register_function(swig_library)
