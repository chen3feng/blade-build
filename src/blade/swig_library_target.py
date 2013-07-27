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
import java_jar_target
import py_targets
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
                          warning,
                          [], [], [], optimize, extra_swigflags, [],
                          blade,
                          kwargs)
        self.data['options']['cpperraswarn'] = warning
        self.data['options']['java_package'] = java_package
        self.data['options']['java_lib_packed'] = java_lib_packed

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
        var_name = self._generate_variable_name(self.data['path'],
                                                self.data['name'],
                                                'dynamic_py')

        obj_names_py = []
        flag_list = []
        warning = self.data.get('options', {}).get('cpperraswarn', '')
        flag_list.append(('cpperraswarn', warning))
        pyswig_flags = ''
        for flag in flag_list:
            if flag[0] == 'cpperraswarn':
                if flag[1] == 'yes':
                    pyswig_flags += ' -cpperraswarn'

        builder_name = '%s_bld' % var_name
        builder_alias = '%s_bld_alias' % var_name
        swig_bld_cmd = 'swig -python -threads %s -c++ -I%s -o $TARGET $SOURCE' % (
                pyswig_flags, self.build_path)

        self._write_rule("%s = Builder(action=MakeAction('%s', "
                "compile_swig_python_message))" % (
                builder_name, swig_bld_cmd))
        self._write_rule('%s.Append(BUILDERS={"%s" : %s})' % (
                env_name, builder_alias, builder_name))

        self._setup_cc_flags()

        py_targets.binary_dep_source_map[self.key] = []
        py_targets.binary_dep_source_cmd[self.key] = []
        dep_files = []
        dep_files_map = {}
        for src in self.data['srcs']:
            pyswig_src = self._pyswig_gen_file(self.data['path'], src)
            self._write_rule('%s.%s(["%s"], "%s")' % (
                    env_name,
                    builder_alias,
                    pyswig_src,
                    os.path.join(self.data['path'], src)))
            py_targets.binary_dep_source_map[self.key].append(
                    self._pyswig_gen_python_file(self.data['path'], src))
            obj_name_py = "%s_object" % self._generate_variable_name(
                self.data['path'], src, 'python')
            obj_names_py.append(obj_name_py)

            self._write_rule(
                "%s = %s.SharedObject(target = '%s' + top_env['OBJSUFFIX'], "
                "source = '%s')" % (obj_name_py,
                                    env_name,
                                    pyswig_src,
                                    pyswig_src))
            py_targets.binary_dep_source_cmd[self.key].append(
                    obj_name_py)
            dep_files = self._swig_extract_dependency_files(
                                os.path.join(self.data['path'], src))
            self._write_rule("%s.Depends('%s', %s)" % (
                             env_name,
                             pyswig_src,
                             dep_files))
            dep_files_map[os.path.join(self.data['path'], src)] = dep_files

        objs_name = self._objs_name()
        objs_name_py = "%s_py" % objs_name
        self._write_rule("%s = [%s]" % (objs_name_py, ','.join(obj_names_py)))

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

        if self.data['srcs'] or self.data['deps']:
            self._write_rule("%s = %s.SharedLibrary('%s', %s, %s, SHLIBPREFIX = '')"
                    % (var_name,
                       env_name,
                       target_path_py,
                       objs_name_py,
                       lib_str))
            py_targets.binary_dep_source_map[self.key].append(
                    "%s.so" % target_path_py)
            py_targets.binary_dep_source_cmd[self.key].append(var_name)

        if link_all_symbols_lib_list:
            self._write_rule("%s.Depends(%s, [%s])" % (
                env_name, var_name, ', '.join(link_all_symbols_lib_list)))

        self._generate_target_explict_dependency(var_name)

        return dep_files_map

    def _swig_library_rules_java(self, dep_files_map):
        """_swig_library_rules_java. """
        env_name = self._env_name()
        var_name = self._generate_variable_name(self.data['path'],
                                                self.data['name'],
                                                'dynamic_java')
        self.java_jar_dep_vars = java_jar_target.get_java_jar_dep_vars()
        self.java_jar_dep_vars[self.key] = []

        java_jar_dep_source_map = java_jar_target.get_java_jar_dep_source_map()

        build_jar = False
        java_lib_packed = False
        # Append -fno-strict-aliasing flag to cxxflags and cppflags
        self._write_rule('%s.Append(CPPFLAGS = ["-fno-strict-aliasing"])' % env_name)
        if self.data.get('options', {}).get('generate_java', False):
            build_jar = True

        flag_list = []
        flag_list.append(('cpperraswarn',
                          self.data.get('options', {}).get('cpperraswarn', '')))
        flag_list.append(('package',
                          self.data.get('options', {}).get('java_package', '')))
        java_lib_packed = self.data.get('options', {}).get('java_lib_packed', False)
        flag_list.append(('java_lib_packed',
                          self.data.get('options', {}).get('java_lib_packed', False)))
        javaswig_flags = ''
        depend_outdir = False
        out_dir = os.path.join(self.build_path, self.data['path'])
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
                                           self.data['path'], package_dir)
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
                        self.java_jar_dep_vars[self.key].append(swig_outdir_cmd)
                    if build_jar:
                        java_jar_dep_source_map[self.key] = (
                                out_dir,
                                os.path.join(self.build_path, self.data['path']),
                                self.data['name'])

        builder_name = '%s_bld' % var_name
        builder_alias = '%s_bld_alias' % var_name
        swig_bld_cmd = "swig -java %s -c++ -I%s -o $TARGET $SOURCE" % (
                       javaswig_flags, self.build_path)
        self._write_rule("%s = Builder(action=MakeAction('%s', "
                "compile_swig_java_message))" % (
                builder_name, swig_bld_cmd))
        self._write_rule('%s.Append(BUILDERS={"%s" : %s})' % (
                env_name, builder_alias, builder_name))
        self._swig_library_rules_java_helper(depend_outdir, build_jar,
                                             java_lib_packed, out_dir,
                                             builder_alias, dep_files_map)

    def _swig_library_rules_java_helper(self,
                                        dep_outdir,
                                        java_build_jar,
                                        lib_packed,
                                        out_dir,
                                        builder_alias,
                                        dep_files_map):
        env_name = self._env_name()
        var_name = self._generate_variable_name(self.data['path'],
                                                self.data['name'],
                                                'dynamic_java')
        depend_outdir = dep_outdir
        build_jar = java_build_jar
        java_lib_packed = lib_packed
        env_name = self._env_name()
        out_dir_dummy = os.path.join(out_dir, 'dummy_file')
        obj_names_java = []

        scons_platform = self.blade.get_scons_platform()
        java_includes = scons_platform.get_java_include()
        if java_includes:
            self._write_rule("%s.Append(CPPPATH=%s)" % (env_name, java_includes))

        sources_dependency_map = java_jar_target.get_sources_explict_dependency_map()
        sources_dependency_map[self.key] = []
        dep_files = []
        for src in self.data['srcs']:
            javaswig_src = self._javaswig_gen_file(self.data['path'], src)
            src_basename = os.path.basename(src)
            javaswig_var = "%s_%s" % (
                    var_name, self._regular_variable_name(src_basename))
            self._write_rule("%s = %s.%s(['%s'], '%s')" % (
                    javaswig_var,
                    env_name,
                    builder_alias,
                    javaswig_src,
                    os.path.join(self.data['path'], src)))
            sources_dependency_map[self.key].append(javaswig_src)
            if depend_outdir:
                self._write_rule('%s.Depends(%s, "%s")' % (
                        env_name,
                        javaswig_var,
                        out_dir_dummy))
            self.java_jar_dep_vars[self.key].append(javaswig_var)

            obj_name_java = "%s_object" % self._generate_variable_name(
                    self.data['path'], src, 'dynamic_java')
            obj_names_java.append(obj_name_java)

            self._write_rule(
                    "%s = %s.SharedObject(target = '%s' + top_env['OBJSUFFIX'], "
                    "source = '%s')" % (
                            obj_name_java,
                            env_name,
                            javaswig_src,
                            javaswig_src))

            dep_key = os.path.join(self.data['path'], src)
            if dep_key in dep_files_map.keys():
                dep_files = dep_files_map[dep_key]
            else:
                dep_files = self._swig_extract_dependency_files(dep_key)
            self._write_rule("%s.Depends('%s', %s)" % (
                             env_name,
                             javaswig_src,
                             dep_files))

        objs_name = self._objs_name()
        objs_name_java = "%s_dynamic_java" % objs_name
        self._write_rule("%s = [%s]" % (objs_name_java,
                                    ','.join(obj_names_java)))

        target_path_java = '%s_java' % self._target_file_path()

        (link_all_symbols_lib_list,
         lib_str,
         whole_link_flags) = self._get_static_deps_lib_list()

        if self.data['srcs'] or self.data['deps']:
            self._write_rule("%s = %s.SharedLibrary('%s', %s, %s)" % (
                    var_name,
                    env_name,
                    target_path_java,
                    objs_name_java,
                    lib_str))

        if link_all_symbols_lib_list:
            self._write_rule("%s.Depends(%s, [%s])" % (
                env_name, var_name, ', '.join(link_all_symbols_lib_list)))

        self._generate_target_explict_dependency(var_name)

        jar_files_packing_map = java_jar_target.get_java_jar_files_packing_map()
        if build_jar and java_lib_packed:
            lib_dir = os.path.dirname(target_path_java)
            lib_name = os.path.basename(target_path_java)
            lib_name = 'lib%s.so' % lib_name
            jar_files_packing_map[self.key] = (
                    os.path.join(lib_dir, lib_name), self.data['name'])

    def _swig_library_rules_php(self, dep_files_map):
        env_name = self._env_name()
        var_name = self._generate_variable_name(self.data['path'], self.data['name'])
        obj_names_php = []

        flag_list = []
        warning = self.data.get('options', {}).get('cpperraswarn', '')
        flag_list.append(('cpperraswarn', warning))
        self.phpswig_flags = ''
        phpswig_flags = ''
        for flag in flag_list:
            if flag[0] == 'cpperraswarn':
                if flag[1] == 'yes':
                    phpswig_flags += ' -cpperraswarn'
        self.phpswig_flags = phpswig_flags

        builder_name = '%s_php_bld' % self._regular_variable_name(self.data['name'])
        builder_alias = '%s_php_bld_alias' % self._regular_variable_name(self.data['name'])
        swig_bld_cmd = "swig -php %s -c++ -I%s -o $TARGET $SOURCE" % (
                       phpswig_flags, self.build_path)

        self._write_rule("%s = Builder(action=MakeAction('%s', "
                "compile_swig_php_message))" % (
                builder_name, swig_bld_cmd))
        self._write_rule('%s.Append(BUILDERS={"%s" : %s})' % (
                          env_name, builder_alias, builder_name))

        if self.php_inc_list:
            self._write_rule("%s.Append(CPPPATH=%s)" % (env_name, self.php_inc_list))

        dep_files = []
        dep_files_map = {}
        for src in self.data['srcs']:
            phpswig_src = self._phpswig_gen_file(self.data['path'], src)
            self._write_rule('%s.%s(["%s"], "%s")' % (
                    env_name,
                    builder_alias,
                    phpswig_src,
                    os.path.join(self.data['path'], src)))
            obj_name_php = "%s_object" % self._generate_variable_name(
                self.data['path'], src, 'php')
            obj_names_php.append(obj_name_php)

            self._write_rule(
                "%s = %s.SharedObject(target = '%s' + top_env['OBJSUFFIX'], "
                "source = '%s')" % (obj_name_php,
                                    env_name,
                                    phpswig_src,
                                    phpswig_src))

            dep_key = os.path.join(self.data['path'], src)
            if dep_key in dep_files_map.keys():
                dep_files = dep_files_map[dep_key]
            else:
                dep_files = self._swig_extract_dependency_files(dep_key)
            self._write_rule("%s.Depends('%s', %s)" % (
                             env_name,
                             phpswig_src,
                             dep_files))

        objs_name = self._objs_name()
        objs_name_php = "%s_php" % objs_name

        self._write_rule("%s = [%s]" % (objs_name_php, ','.join(obj_names_php)))

        target_path = self._target_file_path(self.data['path'], self.data['name'])
        target_lib = os.path.basename(target_path)
        target_path_php = os.path.join(os.path.dirname(target_path), target_lib)

        (link_all_symbols_lib_list,
         lib_str,
         whole_link_flags) = self._get_static_deps_lib_list()

        if self.data['srcs'] or self.data['deps']:
            self._write_rule("%s = %s.SharedLibrary('%s', %s, %s, SHLIBPREFIX='')" % (
                    var_name,
                    env_name,
                    target_path_php,
                    objs_name_php,
                    lib_str))

        if link_all_symbols_lib_list:
            self._write_rule("%s.Depends(%s, [%s])" % (
                env_name, var_name, ', '.join(link_all_symbols_lib_list)))

        self._generate_target_explict_dependency(var_name)

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        dep_files_map = {}
        dep_files_map = self._swig_library_rules_py()
        if (hasattr(self.options, 'generate_java')
                and self.options.generate_java) or (
                        self.data.get('options', {}).get('generate_java', False)):
            self._swig_library_rules_java(dep_files_map)
        if hasattr(self.options, 'generate_php') and self.options.generate_php:
            if not self.php_inc_list:
                console.error_exit("failed to build //%s:%s, please install php modules" % (
                           self.data['path'], self.data['name']))
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
