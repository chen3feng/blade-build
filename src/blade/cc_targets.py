"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the cc_target module which is the super class
 of all of the scons cc targets, like cc_library, cc_binary.

"""


import os
import blade
import configparse

import console
import build_rules
from blade_util import var_to_list
from target import Target


# The prebuilt cc_library file map which is needed to establish
# symbolic links while testing
prebuilt_cc_library_file_map = {}


# The cc objects pool, a map to hold all the objects name.
_objects_pool = {}


class CcTarget(Target):
    """A scons cc target subclass.

    This class is derived from SconsTarget and it is the base class
    of cc_library, cc_binary etc.

    """
    def __init__(self,
                 name,
                 target_type,
                 srcs,
                 deps,
                 warning,
                 defs,
                 incs,
                 export_incs,
                 optimize,
                 extra_cppflags,
                 extra_linkflags,
                 blade,
                 kwargs):
        """Init method.

        Init the cc target.

        """
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)
        defs = var_to_list(defs)
        incs = var_to_list(incs)
        export_incs = var_to_list(export_incs)
        opt = var_to_list(optimize)
        extra_cppflags = var_to_list(extra_cppflags)
        extra_linkflags = var_to_list(extra_linkflags)

        Target.__init__(self,
                        name,
                        target_type,
                        srcs,
                        deps,
                        blade,
                        kwargs)

        self.data['options']['warning'] = warning
        self.data['options']['defs'] = defs
        self.data['options']['incs'] = incs
        self.data['options']['export_incs'] = export_incs
        self.data['options']['optimize'] = opt
        self.data['options']['extra_cppflags'] = extra_cppflags
        self.data['options']['extra_linkflags'] = extra_linkflags

        self._check_defs()
        self._check_incorrect_no_warning()

    def _check_deprecated_deps(self):
        """check that whether it depends upon a deprecated library. """
        for dep in self.data.get('direct_deps', []):
            target = self.target_database.get(dep, {})
            if target.data.get('options', {}).get('deprecated', False):
                replaced_targets = target.data.get('deps', [])
                replaced_target = ''
                if replaced_targets:
                    replaced_target = replaced_targets[0]
                console.warning("//%s:%s : "
                                "//%s:%s has been deprecated, "
                                "please depends on //%s:%s" % (
                                self.data['path'], self.data['name'],
                                target.data['path'], target.data['name'],
                                replaced_target[0], replaced_target[1]))

    def _prepare_to_generate_rule(self):
        """Should be overridden. """
        self._check_deprecated_deps()
        self._clone_env()

    def _clone_env(self):
        """Select env. """
        env_name = self._env_name()
        warning = self.data.get('options', {}).get('warning', '')
        if warning == 'yes':
            self._write_rule("%s = env_with_error.Clone()" % env_name)
        else:
            self._write_rule("%s = env_no_warning.Clone()" % env_name)

    def _check_defs(self):
        """_check_defs.

        It will warn if user defines cpp keyword in defs list.

        """
        cxx_keyword_list = [
            "and", "and_eq", "alignas", "alignof", "asm", "auto",
            "bitand", "bitor", "bool", "break", "case", "catch",
            "char", "char16_t", "char32_t", "class", "compl", "const",
            "constexpr", "const_cast", "continue", "decltype", "default",
            "delete", "double", "dynamic_cast", "else", "enum",
            "explicit", "export", "extern", "false", "float", "for",
            "friend", "goto", "if", "inline", "int", "long", "mutable",
            "namespace", "new", "noexcept", "not", "not_eq", "nullptr",
            "operator", "or", "or_eq", "private", "protected", "public",
            "register", "reinterpret_cast", "return", "short", "signed",
            "sizeof", "static", "static_assert", "static_cast", "struct",
            "switch", "template", "this", "thread_local", "throw",
            "true", "try", "typedef", "typeid", "typename", "union",
            "unsigned", "using", "virtual", "void", "volatile", "wchar_t",
            "while", "xor", "xor_eq"]
        defs_list = self.data.get('options', {}).get('defs', [])
        for macro in defs_list:
            pos = macro.find('=')
            if pos != -1:
                macro = macro[0:pos]
            if macro in cxx_keyword_list:
                console.warning("DO NOT specify c++ keyword %s in defs list" % macro)

    def _check_incorrect_no_warning(self):
        """check if warning=no is correctly used or not. """
        warning = self.data.get('options', {}).get('warning', 'yes')
        srcs = self.data.get('srcs', [])
        if not srcs or warning != 'no':
            return

        keywords_list = self.blade.get_sources_keyword_list()
        for keyword in keywords_list:
            if keyword in self.data['path']:
                return

        illegal_path_list = []
        for keyword in keywords_list:
            illegal_path_list += [s for s in srcs if not keyword in s]

        if illegal_path_list:
            console.warning("//%s:%s : warning='no' is only allowed "
                    "for code in thirdparty." % (
                     self.key[0], self.key[1]))

    def _objs_name(self):
        """_objs_name.

        Concatinating target path, target name to be objs var and returns.

        """
        return "objs_%s" % self._generate_variable_name(self.data['path'],
                                                        self.data['name'])

    def _prebuilt_cc_library_build_path(self, path='', name='', dynamic=0):
        """Returns the build path of the prebuilt cc library. """
        if not path:
            path = self.data['path']
        if not name:
            name = self.data['name']
        suffix = 'a'
        if dynamic:
            suffix = 'so'
        return os.path.join(self.build_path, path, 'lib%s.%s' % (name, suffix))

    def _prebuilt_cc_library_src_path(self, path='', name='', dynamic=0):
        """Returns the source path of the prebuilt cc library. """
        if not path:
            path = self.data['path']
        if not name:
            name = self.data['name']
        options = self.blade.get_options()
        suffix = 'a'
        if dynamic:
            suffix = 'so'
        return os.path.join(path, 'lib%s_%s' % (options.m, options.profile),
                            'lib%s.%s' % (name, suffix))

    def _setup_cc_flags(self):
        """_setup_cc_flags. """
        env_name = self._env_name()
        flags_from_option, incs_list = self._get_cc_flags()
        if flags_from_option:
            self._write_rule("%s.Append(CPPFLAGS=%s)" % (env_name, flags_from_option))
        if incs_list:
            self._write_rule("%s.Append(CPPPATH=%s)" % (env_name, incs_list))

    def _setup_extra_link_flags(self):
        """extra_linkflags. """
        extra_linkflags = self.data.get('options', {}).get('extra_linkflags', [])
        if extra_linkflags:
            self._write_rule("%s.Append(LINKFLAGS=%s)" % (self._env_name(), extra_linkflags))

    def _check_gcc_flag(self, gcc_flag_list):
        options = self.blade.get_options()
        gcc_flags_list_checked = []
        for flag in gcc_flag_list:
            if flag == '-fno-omit-frame-pointer':
                if options.profile != 'release':
                    continue
            gcc_flags_list_checked.append(flag)
        return gcc_flags_list_checked

    def _get_optimize_flags(self):
        """get optimize flags such as -O2"""
        oflags = []
        opt_list = self.data['options'].get('optimize')
        if not opt_list:
            cc_config = configparse.blade_config.get_config('cc_config')
            opt_list = cc_config['optimize']
        if opt_list:
            for flag in opt_list:
                if flag.startswith('-'):
                    oflags.append(flag)
                else:
                    oflags.append('-' + flag)
        else:
            oflags = ['-O2']
        return oflags

    def _get_cc_flags(self):
        """_get_cc_flags.

        Return the cpp flags according to the BUILD file and other configs.

        """
        cpp_flags = []

        # Warnings
        if self.data['options'].get('warning', '') == 'no':
            cpp_flags.append('-w')

        # Defs
        defs = self.data['options'].get('defs', [])
        cpp_flags += [('-D' + macro) for macro in defs]

        # Optimize flags

        if (self.blade.get_options().profile == 'release' or
            self.data['options'].get('always_optimize')):
            cpp_flags += self._get_optimize_flags()

        # Add the compliation flags here
        # 1. -fno-omit-frame-pointer to release
        blade_gcc_flags = ['-fno-omit-frame-pointer']
        blade_gcc_flags_checked = self._check_gcc_flag(blade_gcc_flags)
        cpp_flags += list(set(blade_gcc_flags_checked).difference(set(cpp_flags)))

        cpp_flags += self.data['options'].get('extra_cppflags', [])

        # Incs
        incs = self.data['options'].get('incs', [])
        if not incs:
            incs = self.data['options'].get('export_incs', [])
        new_incs_list = [os.path.join(self.data['path'], inc) for inc in incs]
        new_incs_list += self._export_incs_list()
        # Remove duplicate items in incs list and keep the order
        incs_list = []
        for inc in new_incs_list:
            new_inc = os.path.normpath(inc)
            if new_inc not in incs_list:
                incs_list.append(new_inc)

        return (cpp_flags, incs_list)

    def _dep_is_library(self, dep):
        """_dep_is_library.

        Returns
        -----------
        True or False: Whether this dep target is library or not.

        Description
        -----------
        Whether this dep target is library or not.

        """
        build_targets = self.blade.get_build_targets()
        target_type = build_targets[dep].data.get('type')
        return ('library' in target_type or 'plugin' in target_type)

    def _export_incs_list(self):
        """_export_incs_list.
        TODO
        """
        deps = self.data['deps']
        inc_list = []
        for lib in deps:
            # lib is (path, libname) pair.
            if not lib:
                continue

            if not self._dep_is_library(lib):
                continue

            # system lib
            if lib[0] == "#":
                continue

            target = self.target_database[lib]
            for inc in target.data['options'].get('export_incs', []):
                path = os.path.normpath('%s/%s' % (lib[0], inc))
                inc_list.append(path)

        return inc_list

    def _static_deps_list(self):
        """_static_deps_list.

        Returns
        -----------
        link_all_symbols_lib_list: the libs to link all its symbols into target
        lib_list: the libs list to be statically linked into static library

        Description
        -----------
        It will find the libs needed to be linked into the target statically.

        """
        build_targets = self.blade.get_build_targets()
        deps = self.data['deps']
        lib_list = []
        link_all_symbols_lib_list = []
        for dep in deps:
            if not self._dep_is_library(dep):
                continue

            # system lib
            if dep[0] == "#":
                lib_name = "'%s'" % dep[1]
            else:
                lib_name = self._generate_variable_name(dep[0], dep[1])

            if build_targets[dep].data['options'].get('link_all_symbols'):
                link_all_symbols_lib_list.append(lib_name)
            else:
                lib_list.append(lib_name)

        return (link_all_symbols_lib_list, lib_list)

    def _dynamic_deps_list(self):
        """_dynamic_deps_list.

        Returns
        -----------
        lib_list: the libs list to be dynamically linked into dynamic library

        Description
        -----------
        It will find the libs needed to be linked into the target dynamically.

        """
        build_targets = self.blade.get_build_targets()
        deps = self.data['deps']
        lib_list = []
        for lib in deps:
            if not self._dep_is_library(lib):
                continue

            if (build_targets[lib].data['type'] == 'cc_library' and
                not build_targets[lib].data['srcs']):
                continue
            # system lib
            if lib[0] == "#":
                lib_name = "'%s'" % lib[1]
            else:
                lib_name = self._generate_variable_name(lib[0],
                                                        lib[1],
                                                        "dynamic")

            lib_list.append(lib_name)

        return lib_list

    def _get_static_deps_lib_list(self):
        """Returns a tuple that needed to write static deps rules. """
        (link_all_symbols_lib_list, lib_list) = self._static_deps_list()
        lib_str = 'LIBS=[%s]' % ','.join(lib_list)
        whole_link_flags = []
        if link_all_symbols_lib_list:
            whole_link_flags = ['"-Wl,--whole-archive"']
            for i in link_all_symbols_lib_list:
                whole_link_flags.append(i)
            whole_link_flags.append('"-Wl,--no-whole-archive"')
        return (link_all_symbols_lib_list, lib_str, ', '.join(whole_link_flags))

    def _get_dynamic_deps_lib_list(self):
        """Returns the libs string. """
        lib_list = self._dynamic_deps_list()
        lib_str = "LIBS=[]"
        if lib_list:
            lib_str = 'LIBS=[%s]' % ','.join(lib_list)
        return lib_str

    def _prebuilt_cc_library(self, dynamic=0):
        """prebuilt cc library rules. """
        build_targets = self.blade.get_build_targets()
        prebuilt_target_file = ''
        prebuilt_src_file = ''
        prebuilt_symlink = ''
        allow_only_dynamic = True
        need_static_lib_targets = ['cc_test',
                                   'cc_binary',
                                   'cc_benchmark',
                                   'cc_plugin',
                                   'swig_library']
        for key in build_targets.keys():
            if (self.key in build_targets[key].data['deps'] and
                build_targets[key].data['type'] in need_static_lib_targets):
                allow_only_dynamic = False

        var_name = self._generate_variable_name(self.data['path'],
                                                self.data['name'])
        if not allow_only_dynamic:
            self._write_rule(
                    'Command("%s", "%s", Copy("$TARGET", "$SOURCE"))' % (
                             self._prebuilt_cc_library_build_path(),
                             self._prebuilt_cc_library_src_path()))
            self._write_rule("%s = top_env.File('%s')" % (
                             var_name,
                             self._prebuilt_cc_library_build_path()))
        if dynamic:
            prebuilt_target_file = self._prebuilt_cc_library_build_path(
                                            self.data['path'],
                                            self.data['name'],
                                            dynamic=1)
            prebuilt_src_file = self._prebuilt_cc_library_src_path(
                                            self.data['path'],
                                            self.data['name'],
                                            dynamic=1)
            self._write_rule(
                    'Command("%s", "%s", Copy("$TARGET", "$SOURCE"))' % (
                     prebuilt_target_file,
                     prebuilt_src_file))
            var_name = self._generate_variable_name(self.data['path'],
                                                    self.data['name'],
                                                    "dynamic")
            self._write_rule("%s = top_env.File('%s')" % (
                        var_name,
                        prebuilt_target_file))
            prebuilt_symlink = os.path.realpath(prebuilt_src_file)
            prebuilt_symlink = os.path.basename(prebuilt_symlink)
            prebuilt_cc_library_file_map[self.key] = (prebuilt_target_file,
                                                prebuilt_symlink)

    def _cc_library(self):
        """_cc_library.

        It will output the cc_library rule into the buffer.

        """
        var_name = self._generate_variable_name(self.data['path'], self.data['name'])
        self._write_rule("%s = %s.Library('%s', %s)" % (
                var_name,
                self._env_name(),
                self._target_file_path(),
                self._objs_name()))
        self._write_rule("%s.Depends(%s, %s)" % (
                self._env_name(),
                var_name,
                self._objs_name()))
        self._generate_target_explict_dependency(var_name)

    def _dynamic_cc_library(self):
        """_dynamic_cc_library.

        It will output the dynamic_cc_library rule into the buffer.

        """
        self._setup_extra_link_flags()

        var_name = self._generate_variable_name(self.data['path'],
                                                self.data['name'],
                                                'dynamic')

        lib_str = self._get_dynamic_deps_lib_list()
        if self.data['srcs'] or self.data['deps']:
            self._write_rule('%s.Append(LINKFLAGS=["-Xlinker", "--no-undefined"])'
                             % self._env_name())
            self._write_rule("%s = %s.SharedLibrary('%s', %s, %s)" % (
                    var_name,
                    self._env_name(),
                    self._target_file_path(),
                    self._objs_name(),
                    lib_str))
            self._write_rule("%s.Depends(%s, %s)" % (
                    self._env_name(),
                    var_name,
                    self._objs_name()))
        self._generate_target_explict_dependency(var_name)

    def _cc_objects_rules(self):
        """_cc_objects_rules.

        Generate the cc objects rules for the srcs in srcs list.

        """
        target_types = ["cc_library",
                        "cc_binary",
                        "cc_test",
                        "cc_plugin"]

        if not self.data['type'] in target_types:
            console.error_exit("logic error, type %s err in object rule" % self.data['type'])

        path = self.data['path']
        objs_name = self._objs_name()
        env_name = self._env_name()

        self._setup_cc_flags()

        objs = []
        sources = []
        for src in self.data['srcs']:
            obj = "%s_%s_object" % (self._generate_variable_name(path, src),
                                    self._regular_variable_name(self.data['name']))
            target_path = os.path.join(
                    self.build_path, path, '%s.objs' % self.data['name'], src)
            self._write_rule(
                    "%s = %s.SharedObject(target = '%s' + top_env['OBJSUFFIX']"
                    ", source = '%s')" % (obj,
                                          env_name,
                                          target_path,
                                          self._target_file_path(path, src)))
            self._write_rule("%s.Depends(%s, '%s')" % (
                             env_name,
                             obj,
                             self._target_file_path(path, src)))
            sources.append(self._target_file_path(path, src))
            objs.append(obj)
        self._write_rule("%s = [%s]" % (objs_name, ','.join(objs)))
        return sources


class CcLibrary(CcTarget):
    """A cc target subclass.

    This class is derived from SconsTarget and it generates the library
    rules including dynamic library rules accoring to user option.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 warning,
                 defs,
                 incs,
                 export_incs,
                 optimize,
                 always_optimize,
                 prebuilt,
                 link_all_symbols,
                 deprecated,
                 extra_cppflags,
                 extra_linkflags,
                 blade,
                 kwargs):
        """Init method.

        Init the cc target.

        """
        CcTarget.__init__(self,
                          name,
                          'cc_library',
                          srcs,
                          deps,
                          warning,
                          defs,
                          incs,
                          export_incs,
                          optimize,
                          extra_cppflags,
                          extra_linkflags,
                          blade,
                          kwargs)
        if prebuilt:
            self.data['type'] = 'prebuilt_cc_library'
            self.data['srcs'] = []
        self.data['options']['link_all_symbols'] = link_all_symbols
        self.data['options']['always_optimize'] = always_optimize
        self.data['options']['deprecated'] = deprecated

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        building_dynamic = 0
        options = self.blade.get_options()
        if (hasattr(options, 'generate_dynamic') and options.generate_dynamic) or (
            self.data.get('options', {}).get('build_dynamic', False)):
            building_dynamic = 1

        if self.data['type'] == 'prebuilt_cc_library':
            self._prebuilt_cc_library(building_dynamic)
        else:
            self._cc_objects_rules()
            self._cc_library()
            if building_dynamic:
                self._dynamic_cc_library()


def cc_library(name,
               srcs=[],
               deps=[],
               warning='yes',
               defs=[],
               incs=[],
               export_incs=[],
               optimize=[],
               always_optimize=False,
               pre_build=False,
               prebuilt=False,
               link_all_symbols=False,
               deprecated=False,
               extra_cppflags=[],
               extra_linkflags=[],
               **kwargs):
    """cc_library target. """
    target = CcLibrary(name,
                       srcs,
                       deps,
                       warning,
                       defs,
                       incs,
                       export_incs,
                       optimize,
                       always_optimize,
                       prebuilt or pre_build,
                       link_all_symbols,
                       deprecated,
                       extra_cppflags,
                       extra_linkflags,
                       blade.blade,
                       kwargs)
    if pre_build:
        console.warning("//%s:%s: 'pre_build' has been deprecated, "
                           "please use 'prebuilt'" % (target.data['path'],
                                                      target.data['name']))
    blade.blade.register_target(target)


build_rules.register_function(cc_library)


class CcBinary(CcTarget):
    """A scons cc target subclass.

    This class is derived from SconsCCTarget and it generates the cc_binary
    rules according to user options.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 warning,
                 defs,
                 incs,
                 export_incs,
                 optimize,
                 dynamic_link,
                 extra_cppflags,
                 extra_linkflags,
                 export_dynamic,
                 blade,
                 kwargs):
        """Init method.

        Init the cc target.

        """
        CcTarget.__init__(self,
                          name,
                          'cc_binary',
                          srcs,
                          deps,
                          warning,
                          defs,
                          incs,
                          export_incs,
                          optimize,
                          extra_cppflags,
                          extra_linkflags,
                          blade,
                          kwargs)
        self.data['options']['dynamic_link'] = dynamic_link
        self.data['options']['export_dynamic'] = export_dynamic

        cc_binary_config = configparse.blade_config.get_config('cc_binary_config')
        # add extra link library
        link_libs = var_to_list(cc_binary_config['extra_libs'])
        self._add_hardcode_library(link_libs)

    def _cc_binary(self):
        """_cc_binary rules. """
        env_name = self._env_name()
        var_name = self._generate_variable_name(self.data['path'], self.data['name'])

        platform = self.blade.get_scons_platform()
        if platform.get_gcc_version() > '4.5':
            link_flag_list = ["-static-libgcc", "-static-libstdc++"]
            self._write_rule('%s.Append(LINKFLAGS=%s)' % (env_name, link_flag_list))

        (link_all_symbols_lib_list,
         lib_str,
         whole_link_flags) = self._get_static_deps_lib_list()
        if whole_link_flags:
            self._write_rule(
                    '%s.Append(LINKFLAGS=[%s])' % (env_name, whole_link_flags))

        if self.data.get('options', {}).get('export_dynamic', False):
            self._write_rule(
                "%s.Append(LINKFLAGS='-rdynamic')" % env_name)

        self._setup_extra_link_flags()

        self._write_rule("%s = %s.Program('%s', %s, %s)" % (
            var_name,
            env_name,
            self._target_file_path(),
            self._objs_name(),
            lib_str))
        self._write_rule("%s.Depends(%s, %s)" % (
            env_name,
            var_name,
            self._objs_name()))
        self._generate_target_explict_dependency(var_name)

        if link_all_symbols_lib_list:
            self._write_rule("%s.Depends(%s, [%s])" % (
                    env_name, var_name, ', '.join(link_all_symbols_lib_list)))

        self._write_rule('%s.Append(LINKFLAGS=str(version_obj[0]))' % env_name)
        self._write_rule("%s.Requires(%s, version_obj)" % (
                         env_name, var_name))

    def _dynamic_cc_binary(self):
        """_dynamic_cc_binary. """
        env_name = self._env_name()
        var_name = self._generate_variable_name(self.data['path'], self.data['name'])
        if self.data.get('options', {}).get('export_dynamic', False):
            self._write_rule("%s.Append(LINKFLAGS='-rdynamic')" % env_name)

        self._setup_extra_link_flags()

        lib_str = self._get_dynamic_deps_lib_list()
        self._write_rule("%s = %s.Program('%s', %s, %s)" % (
            var_name,
            env_name,
            self._target_file_path(),
            self._objs_name(),
            lib_str))
        self._write_rule("%s.Depends(%s, %s)" % (
            env_name,
            var_name,
            self._objs_name()))
        self._write_rule('%s.Append(LINKFLAGS=str(version_obj[0]))' % env_name)
        self._write_rule("%s.Requires(%s, version_obj)" % (
                         env_name, var_name))

        self._generate_target_explict_dependency(var_name)

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        self._cc_objects_rules()

        if self.data['options']['dynamic_link']:
            self._dynamic_cc_binary()
        else:
            self._cc_binary()


def cc_binary(name,
              srcs=[],
              deps=[],
              warning='yes',
              defs=[],
              incs=[],
              export_incs=[],
              optimize=[],
              dynamic_link=False,
              extra_cppflags=[],
              extra_linkflags=[],
              export_dynamic=False,
              **kwargs):
    """cc_binary target. """
    cc_binary_target = CcBinary(name,
                                srcs,
                                deps,
                                warning,
                                defs,
                                incs,
                                export_incs,
                                optimize,
                                dynamic_link,
                                extra_cppflags,
                                extra_linkflags,
                                export_dynamic,
                                blade.blade,
                                kwargs)
    blade.blade.register_target(cc_binary_target)


build_rules.register_function(cc_binary)


def cc_benchmark(name, deps=[], **kwargs):
    """cc_benchmark target. """
    cc_config = configparse.blade_config.get_config('cc_config')
    benchmark_libs = cc_config['benchmark_libs']
    benchmark_main_libs = cc_config['benchmark_main_libs']
    deps = var_to_list(deps) + benchmark_libs + benchmark_main_libs
    cc_binary(name=name, deps=deps, **kwargs)


build_rules.register_function(cc_benchmark)


class CcPlugin(CcTarget):
    """A scons cc target subclass.

    This class is derived from SconsCCTarget and it generates the cc_plugin
    rules according to user options.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 warning,
                 defs,
                 incs,
                 export_incs,
                 optimize,
                 prebuilt,
                 extra_cppflags,
                 extra_linkflags,
                 blade,
                 kwargs):
        """Init method.

        Init the cc plugin target.

        """
        CcTarget.__init__(self,
                          name,
                          'cc_plugin',
                          srcs,
                          deps,
                          warning,
                          defs,
                          incs,
                          export_incs,
                          optimize,
                          extra_cppflags,
                          extra_linkflags,
                          blade,
                          kwargs)
        if prebuilt:
            self.data['type'] = 'prebuilt_cc_library'
            self.data['srcs'] = []

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        env_name = self._env_name()
        var_name = self._generate_variable_name(self.data['path'],
                                                self.data['name'],
                                                'dynamic')

        self._cc_objects_rules()

        (link_all_symbols_lib_list,
         lib_str,
         whole_link_flags) = self._get_static_deps_lib_list()
        if whole_link_flags:
            self._write_rule(
                    '%s.Append(LINKFLAGS=[%s])' % (env_name, whole_link_flags))

        if self.data['srcs'] or self.data['deps']:
            self._write_rule("%s = %s.SharedLibrary('%s', %s, %s)" % (
                    var_name,
                    env_name,
                    self._target_file_path(),
                    self._objs_name(),
                    lib_str))

        if link_all_symbols_lib_list:
            self._write_rule("%s.Depends(%s, [%s])" % (
                env_name, var_name, ', '.join(link_all_symbols_lib_list)))

        self._generate_target_explict_dependency(var_name)


def cc_plugin(name,
              srcs=[],
              deps=[],
              warning='yes',
              defs=[],
              incs=[],
              export_incs=[],
              optimize=[],
              prebuilt=False,
              pre_build=False,
              extra_cppflags=[],
              extra_linkflags=[],
              **kwargs):
    """cc_plugin target. """
    target = CcPlugin(name,
                      srcs,
                      deps,
                      warning,
                      defs,
                      incs,
                      export_incs,
                      optimize,
                      prebuilt or pre_build,
                      extra_cppflags,
                      extra_linkflags,
                      blade.blade,
                      kwargs)
    if pre_build:
        console.warning("//%s:%s: 'pre_build' has been deprecated, "
                        "please use 'prebuilt'" % (target.data['path'],
                                                   target.data['name']))
    blade.blade.register_target(target)


build_rules.register_function(cc_plugin)


# See http://google-perftools.googlecode.com/svn/trunk/doc/heap_checker.html
HEAP_CHECK_VALUES = set([
    'minimal',
    'normal',
    'strict',
    'draconian',
    'as-is',
    'local',
])


class CcTest(CcBinary):
    """A scons cc target subclass.

    This class is derived from SconsCCTarget and it generates the cc_test
    rules according to user options.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 warning,
                 defs,
                 incs,
                 export_incs,
                 optimize,
                 dynamic_link,
                 testdata,
                 extra_cppflags,
                 extra_linkflags,
                 export_dynamic,
                 always_run,
                 exclusive,
                 heap_check,
                 heap_check_debug,
                 blade,
                 kwargs):
        """Init method.

        Init the cc target.

        """
        cc_test_config = configparse.blade_config.get_config('cc_test_config')
        if dynamic_link is None:
            dynamic_link = cc_test_config['dynamic_link']

        CcBinary.__init__(self,
                          name,
                          srcs,
                          deps,
                          warning,
                          defs,
                          incs,
                          export_incs,
                          optimize,
                          dynamic_link,
                          extra_cppflags,
                          extra_linkflags,
                          export_dynamic,
                          blade,
                          kwargs)
        self.data['type'] = 'cc_test'
        self.data['options']['testdata'] = var_to_list(testdata)
        self.data['options']['always_run'] = always_run
        self.data['options']['exclusive'] = exclusive

        gtest_lib = var_to_list(cc_test_config['gtest_libs'])
        gtest_main_lib = var_to_list(cc_test_config['gtest_main_libs'])

        # Hardcode deps rule to thirdparty gtest main lib.
        self._add_hardcode_library(gtest_lib)
        self._add_hardcode_library(gtest_main_lib)

        if heap_check is None:
            heap_check = cc_test_config.get('heap_check', '')
        else:
            if heap_check not in HEAP_CHECK_VALUES:
                console.error_exit("//%s:%s: heap_check can only be in %s" % (
                    self.data['path'], self.data['name'], HEAP_CHECK_VALUES))

        perftools_lib = var_to_list(cc_test_config['gperftools_libs'])
        perftools_debug_lib = var_to_list(cc_test_config['gperftools_debug_libs'])
        if heap_check:
            self.data['options']['heap_check'] = heap_check

            if heap_check_debug:
                perftools_lib_list = perftools_debug_lib
            else:
                perftools_lib_list = perftools_lib

            self._add_hardcode_library(perftools_lib_list)


def cc_test(name,
            srcs=[],
            deps=[],
            warning='yes',
            defs=[],
            incs=[],
            export_incs=[],
            optimize=[],
            dynamic_link=None,
            testdata=[],
            extra_cppflags=[],
            extra_linkflags=[],
            export_dynamic=False,
            always_run=False,
            exclusive=False,
            heap_check=None,
            heap_check_debug=False,
            **kwargs):
    """cc_test target. """
    cc_test_target = CcTest(name,
                            srcs,
                            deps,
                            warning,
                            defs,
                            incs,
                            export_incs,
                            optimize,
                            dynamic_link,
                            testdata,
                            extra_cppflags,
                            extra_linkflags,
                            export_dynamic,
                            always_run,
                            exclusive,
                            heap_check,
                            heap_check_debug,
                            blade.blade,
                            kwargs)
    blade.blade.register_target(cc_test_target)


build_rules.register_function(cc_test)
