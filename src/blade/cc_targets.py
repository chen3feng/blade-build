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
import blade_util
import configparse
from blade_util import error_exit
from blade_util import var_to_list
from blade_util import warning
from blade_platform import CcFlagsManager
from target import Target


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

        self.data['options']['warnings'] = warning
        self.data['options']['defs'] = defs
        self.data['options']['incs'] = incs
        self.data['options']['optimize'] = opt
        self.data['options']['extra_cppflags'] = extra_cppflags
        self.data['options']['extra_linkflags'] = extra_linkflags

        self.targets = None

        self._check_defs()
        self._check_incorrect_no_warning()

    def _check_deprecated_deps(self):
        """check that whether it depends upon a deprecated library. """
        for dep in self.data.get('direct_deps', []):
            target = self.target_database.get(dep, {})
            if target.get('options', {}).get('deprecated', False):
                replaced_targets = target.get('deps', [])
                replaced_target = ''
                if replaced_targets:
                    replaced_target = eval(str(replaced_targets[0]))
                blade_util.warning("//%s:%s : "
                                   "//%s:%s has been deprecated, "
                                   "please depends on //%s:%s" % (
                                   self.data['path'], self.data['name'],
                                   target['path'], target['name'],
                                   replaced_target[0],replaced_target[1]))

    def _prepare_to_generate_rule(self):
        """Should be overridden. """
        self._check_deprecated_deps()
        self._clone_env()

    def _check_optimize_flags(self, oflag):
        """_check_optimize_flags.

        It will exit if user defines unregconized optimize flag.

        """
        opt_list = ['O0', 'O1', 'O2', 'O3', 'Os', 'Ofast']
        if not oflag in opt_list:
            error_exit("please specify optimization flags only in %s" % (
                       ','.join(opt_list)))

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
                warning("DO NOT specify c++ keyword %s in defs list" % macro )

    def _check_incorrect_no_warning(self):
        """check if warning=no is correctly used or not. """
        warnings = self.data.get('options', {}).get('warnings', 'yes')
        srcs = self.data.get('srcs', [])
        if not srcs or warnings == 'yes':
            return

        keywords_list = self.blade.get_sources_keyword_list()
        for keyword in keywords_list:
            if keyword in self.current_source_path:
                return

        illegal_path_list = []
        for keyword in keywords_list:
            illegal_path_list += [s for s in srcs if not keyword in s]

        if illegal_path_list:
            warning("//%s:%s : warning='no' is only allowed "
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
        if not dynamic:
            return "%s" % os.path.join(
                self.build_path,
                path,
                'lib%s.a' % name)
        else:
            return "%s" % os.path.join(
                self.build_path,
                path,
                'lib%s.so' % name)


    def _prebuilt_cc_library_src_path(self, path='', name='', dynamic=0):
        """Returns the source path of the prebuilt cc library. """
        if not path:
            path = self.data['path']
        if not name:
            name = self.data['name']
        options = self.blade.get_options()
        if not dynamic:
            return "%s" % os.path.join(
                path,
                'lib%s_%s' % (options.m, options.profile),
                'lib%s.a' % name)
        else:
            return "%s" % os.path.join(
                path,
                'lib%s_%s' % (options.m, options.profile),
                'lib%s.so' % name)

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

    def _get_cc_flags(self):
        """_get_cc_flags.

        It will return the cpp flags according to the BUILD file.

        """
        warnings = self.data.get('options', {}).get('warnings', '')
        defs_list = self.data.get('options', {}).get('defs', [])
        incs_list = self.data.get('options', {}).get('incs', [])
        opt_list = self.data.get('options', {}).get('optimize', [])
        extra_cppflags = self.data.get('options', {}).get('extra_cppflags', [])
        always_optimize = self.data.get('options', {}).get('always_optimize', False)

        options = self.blade.get_options()
        user_oflag = ''
        cpp_flags = []
        new_defs_list = []
        new_incs_list = []
        new_opt_list = []
        if warnings == 'no':
            cpp_flags.append('-w')
        if defs_list:
            new_defs_list = [('-D' + macro) for macro in defs_list]
            cpp_flags += new_defs_list
        if incs_list:
            for inc in incs_list:
                new_incs_list.append(os.path.join(self.data['path'], inc))
        if opt_list:
            for flag in opt_list:
                if flag.find('O') == -1:
                    new_opt_list.append('-' + flag)
                else:
                    self._check_optimize_flags(flag)
                    user_oflag = '-%s' % flag
            cpp_flags += new_opt_list

        oflag = ''
        if always_optimize:
            oflag = user_oflag if user_oflag else '-O2'
            cpp_flags.append(oflag)
        else:
            if options.profile == 'release':
                oflag = user_oflag if user_oflag else '-O2'
                cpp_flags.append(oflag)

        # Add the compliation flags here
        # 1. -fno-omit-frame-pointer to release
        blade_gcc_flags = ['-fno-omit-frame-pointer']
        blade_gcc_flags_checked = self._check_gcc_flag(blade_gcc_flags)
        cpp_flags += list(set(blade_gcc_flags_checked).difference(set(cpp_flags)))

        # Remove duplicate items in incs list and keep the order
        incs_list = []
        for inc in new_incs_list:
            new_inc = os.path.normpath(inc)
            if new_inc not in incs_list:
                incs_list.append(new_inc)

        # TODO(michael): Enable this to support header files conflicting
        # requirements from reverted-index team, these lines of code
        # SHOULD be removed in the future
        cpp_flags += [('-I' + inc) for inc in incs_list]

        return (cpp_flags + extra_cppflags, incs_list)

    def _dep_is_library(self, dep):
        """_dep_is_library.

        Returns
        -----------
        True or False: Whether this dep target is library or not.

        Description
        -----------
        Whether this dep target is library or not.

        """
        target_type = self.targets[dep].get('type')
        return ('library' in target_type or 'plugin' in target_type)

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
        if not self.blade.get_expanded():
            error_exit('logic error in blade, expand targets at first')
        self.targets = self.blade.get_all_targets_expanded()
        if not self.targets:
            error_exit('logic error in blade, no expanded targets')
        deps = self.targets[self.key]['deps']
        lib_list = []
        link_all_symbols_lib_list = []
        for lib in deps:
            # lib is (path, libname) pair.
            if not lib:
                continue

            if not self._dep_is_library(lib):
                continue

            # system lib
            if lib[0] == "#":
                lib_name = "'%s'" % lib[1]
                lib_path = lib[1]
            else:
                lib_name = self._generate_variable_name(lib[0], lib[1])
                lib_path = self._target_file_path(lib[0], 'lib%s.a' % lib[1])

            if self.targets[lib].get('options', {}).get('link_all_symbols', 0):
                link_all_symbols_lib_list.append((lib_path, lib_name))
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
        if not self.blade.get_expanded():
            error_exit('logic error in blade, expand targets at first')
        self.targets = self.blade.get_all_targets_expanded()
        if not self.targets:
            error_exit('logic error in blade, no expanded targets')
        deps = self.targets[self.key]['deps']
        lib_list = []
        for lib in deps:
            # lib is (path, libname) pair.
            if not lib:
                continue

            if not self._dep_is_library(lib):
                continue

            if (self.targets[lib]['type'] == 'cc_library' and
                not self.targets[lib]['srcs']):
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
        lib_str = "LIBS=[]"
        if lib_list:
            lib_str = 'LIBS=[%s]' % ','.join(lib_list)
        whole_link_flags = []
        if link_all_symbols_lib_list:
            whole_link_flags = ["-Wl,--whole-archive"]
            for i in link_all_symbols_lib_list:
                whole_link_flags.append(i[0])
            whole_link_flags.append('-Wl,--no-whole-archive')
        return (link_all_symbols_lib_list, lib_str, whole_link_flags)

    def _get_dynamic_deps_lib_list(self):
        """Returns the libs string. """
        lib_list = self._dynamic_deps_list()
        lib_str = "LIBS=[]"
        if lib_list:
            lib_str = 'LIBS=[%s]' % ','.join(lib_list)
        return lib_str

    def _prebuilt_cc_library(self, dynamic=0):
        """pre build cc library rules. """
        self.targets = self.blade.get_all_targets_expanded()
        self.prebuilt_file_map = self.blade.get_prebuilt_cc_library_file_map()
        prebuilt_target_file = ''
        prebuilt_src_file = ''
        prebuilt_symlink = ''
        allow_only_dynamic = True
        need_static_lib_targets = ['cc_test',
                                   'cc_binary',
                                   'cc_plugin',
                                   'swig_library']
        for key in self.targets.keys():
            if self.key in self.targets[key].get('deps', []) and (
                    self.targets[key].get('type', None) in need_static_lib_targets):
                allow_only_dynamic = False

        var_name = self._generate_variable_name(self.data['path'],
                                                self.data['name'])
        if not allow_only_dynamic:
            self._write_rule(
                    'Command("%s", "%s", Copy("$TARGET", "$SOURCE"))' % (
                             self._prebuilt_cc_library_build_path(),
                             self._prebuilt_cc_library_src_path()))
            self._write_rule("%s = env.File('%s')" % (
                             var_name,
                             self._prebuilt_cc_library_build_path()))
        if dynamic == 1:
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
            self._write_rule("%s = env.File('%s')" % (
                        var_name,
                        prebuilt_target_file))
            prebuilt_symlink = os.path.realpath(prebuilt_src_file)
            prebuilt_symlink = os.path.basename(prebuilt_symlink)
            self.prebuilt_file_map[self.key] = (prebuilt_target_file,
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
        if self.targets[self.key]['srcs'] or self.targets[self.key]['deps']:
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
                    '%s.Append(LINKFLAGS=%s)' % (env_name, whole_link_flags))

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

        for i in link_all_symbols_lib_list:
            self._write_rule("%s.Depends(%s, %s)" % (
                    env_name, var_name, i[1]))

        self._write_rule('%s.Append(LINKFLAGS=str(version_obj[0]))' % env_name)
        self._write_rule("%s.Requires(%s, version_obj)" % (
                         env_name, var_name))

    def _dynamic_cc_binary(self):
        """_dynamic_cc_binary. """
        var_name = self._generate_variable_name(self.data['path'], self.data['name'])

        if self.data.get('options', {}).get('export_dynamic', False):
            self._write_rule(
                "%s.Append(LINKFLAGS='-rdynamic')" % self._env_name())

        self._setup_extra_link_flags()

        lib_str = self._get_dynamic_deps_lib_list()
        self._write_rule("%s = %s.Program('%s', %s, %s)" % (
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
                        "dynamic_cc_binary",
                        "cc_test",
                        "dynamic_cc_test",
                        "cc_plugin"]

        if not self.data['type'] in target_types:
            error_exit("logic error, type %s err in object rule" % self.data['type'])

        self.objects = self.blade.get_cc_objects_pool()

        path = self.data['path']
        objs_name = self._objs_name()
        env_name = self._env_name()

        self._setup_cc_flags()

        objs = []
        sources = []
        for src in self.data['srcs']:
            src_name = self._generate_variable_name(path, src)
            src_name = '%s_%s' % (src_name, self.data['name'])
            if src_name not in self.objects:
                self.objects[src_name] = (
                        "%s_%s_object" % (
                                self._generate_variable_name(path, src),
                                self._regular_variable_name(self.data['name'])))
                target_path = os.path.join(
                        self.build_path, path, '%s.objs' % self.data['name'], src)
                self._write_rule(
                        "%s = %s.SharedObject(target = '%s' + env['OBJSUFFIX']"
                        ", source = '%s')" % (self.objects[src_name],
                                              env_name,
                                              target_path,
                                              self._target_file_path(path, src)))
                self._write_rule("%s.Depends(%s, '%s')" % (
                                 env_name,
                                 self.objects[src_name],
                                 self._target_file_path(path, src)))
            sources.append(self._target_file_path(path, src))
            objs.append(self.objects[src_name])
        self._write_rule("%s = [%s]" % (objs_name, ','.join(objs)))
        return sources

    def scons_rules(self):
        """scons_rules.

        This method should be impolemented in subclass.

        """
        error_exit('cc_target should be subclassing')


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

    def _clone_env(self):
        """override this method. """
        env_name = self._env_name()
        warnings = self.data.get('options', {}).get('warnings', '')
        if warnings == 'no':
            self._write_rule("%s = env_no_warning.Clone()" % env_name)
        else:
            self._write_rule("%s = env_with_error.Clone()" % env_name)

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

            if building_dynamic == 1:
                self._dynamic_cc_library()


def cc_library(name,
               srcs=[],
               deps=[],
               warning='yes',
               defs=[],
               incs=[],
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
        blade_util.warning("//%s:%s: 'pre_build' has been deprecated, "
                           "please use 'prebuilt'" % (target.data['path'],
                                                      target.data['name']))
    blade.blade.register_scons_target(target.key,
                                      target)


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
                          optimize,
                          extra_cppflags,
                          extra_linkflags,
                          blade,
                          kwargs)
        if dynamic_link:
            self.data['type'] = 'dynamic_cc_binary'

        if export_dynamic:
            self.data['options']['export_dynamic'] = True

    def _clone_env(self):
        """override this method. """
        env_name = self._env_name()
        warnings = self.data.get('options', {}).get('warnings', '')
        if warnings == 'no':
            self._write_rule("%s = env_no_warning.Clone()" % env_name)
        else:
            self._write_rule("%s = env_with_error.Clone()" % env_name)

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        self._cc_objects_rules()

        if self.data['type'] == 'cc_binary':
            self._cc_binary()
        elif self.data['type'] == 'dynamic_cc_binary':
            self._dynamic_cc_binary()


def cc_binary(name,
              srcs=[],
              deps=[],
              warning='yes',
              defs=[],
              incs=[],
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
                                optimize,
                                dynamic_link,
                                extra_cppflags,
                                extra_linkflags,
                                export_dynamic,
                                blade.blade,
                                kwargs)
    blade.blade.register_scons_target(cc_binary_target.key, cc_binary_target)


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
                 optimize,
                 prebuilt,
                 extra_cppflags,
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
                          optimize,
                          extra_cppflags,
                          [],
                          blade,
                          kwargs)
        if prebuilt:
            self.data['type'] = 'prebuilt_cc_library'
            self.data['srcs'] = []

    def _clone_env(self):
        """override this method. """
        env_name = self._env_name()
        warnings = self.data.get('options', {}).get('warnings', '')
        if warnings == 'no':
            self._write_rule("%s = env_no_warning.Clone()" % env_name)
        else:
            self._write_rule("%s = env_with_error.Clone()" % env_name)

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
                    '%s.Append(LINKFLAGS=%s)' % (env_name, whole_link_flags))

        if self.targets[self.key]['srcs'] or self.targets[self.key]['deps']:
            self._write_rule('%s.Append(LINKFLAGS=["-fPIC"])'
                             % env_name)
            self._write_rule("%s = %s.SharedLibrary('%s', %s, %s)" % (
                    var_name,
                    env_name,
                    self._target_file_path(),
                    self._objs_name(),
                    lib_str))

        for i in link_all_symbols_lib_list:
            self._write_rule("%s.Depends(%s, %s)" % (env_name, var_name, i[1]))

        self._generate_target_explict_dependency(var_name)


def cc_plugin(name,
              srcs=[],
              deps=[],
              warning='yes',
              defs=[],
              incs=[],
              optimize=[],
              prebuilt=False,
              pre_build=False,
              extra_cppflags=[],
              **kwargs):
    """cc_plugin target. """
    target = CcPlugin(name,
                      srcs,
                      deps,
                      warning,
                      defs,
                      incs,
                      optimize,
                      prebuilt or pre_build,
                      extra_cppflags,
                      blade.blade,
                      kwargs)
    if pre_build:
        blade_util.warning("//%s:%s: 'pre_build' has been deprecated, "
                           "please use 'prebuilt'" % (target.data['path'],
                                                      target.data['name']))
    blade.blade.register_scons_target(target.key, target)


# See http://google-perftools.googlecode.com/svn/trunk/doc/heap_checker.html
HEAP_CHECK_VALUES = set([
    'minimal',
    'normal',
    'strict',
    'draconian',
    'as-is',
    'local',
])


class CcTest(CcTarget):
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
        CcTarget.__init__(self,
                          name,
                          'cc_test',
                          srcs,
                          deps,
                          warning,
                          defs,
                          incs,
                          optimize,
                          extra_cppflags,
                          extra_linkflags,
                          blade,
                          kwargs)
        testdata = var_to_list(testdata)
        self.data['options']['testdata'] = testdata

        cc_test_config = configparse.blade_config.get_config('cc_test_config')
        gtest_lib = var_to_list(cc_test_config['gtest_libs'])
        gtest_main_lib = var_to_list(cc_test_config['gtest_main_libs'])

        # Hardcode deps rule to thirdparty gtest main lib.
        self._add_hardcode_library(gtest_lib)
        self._add_hardcode_library(gtest_main_lib)

        # dynamic link by default
        if dynamic_link is None:
            dynamic_link = cc_test_config['dynamic_link']
        if dynamic_link:
            self.data['type'] = 'dynamic_cc_test'

        if export_dynamic:
            self.data['options']['export_dynamic'] = True

        if always_run:
            self.data['options']['always_run'] = True

        if exclusive:
            self.data['options']['exclusive'] = True

        if heap_check is None:
            heap_check = cc_test_config.get('heap_check', '')
        else:
            if heap_check not in HEAP_CHECK_VALUES:
                error_exit("//%s:%s: heap_check can only be in %s" % (
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

    def _clone_env(self):
        """override this method. """
        env_name = self._env_name()
        warnings = self.data.get('options', {}).get('warnings', '')
        if warnings == 'no':
            self._write_rule("%s = env_no_warning.Clone()" % env_name)
        else:
            self._write_rule("%s = env_with_error.Clone()" % env_name)

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        self._cc_objects_rules()

        if self.data['type'] == 'cc_test':
            self._cc_binary()
        elif self.data['type'] == 'dynamic_cc_test':
            self._dynamic_cc_binary()


def cc_test(name,
            srcs=[],
            deps=[],
            warning='yes',
            defs=[],
            incs=[],
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
    blade.blade.register_scons_target(cc_test_target.key, cc_test_target)


class LexYaccLibrary(CcTarget):
    """A scons cc target subclass.

    This class is derived from SconsCCTarget and it generates lex yacc rules.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 recursive,
                 prefix,
                 blade,
                 kwargs):
        """Init method.

        Init the cc lex yacc target

        """
        if len(srcs) != 2:
            raise Exception, ("'srcs' for lex_yacc_library should "
                              "be a pair of (lex_source, yacc_source)")
        CcTarget.__init__(self,
                          name,
                          'lex_yacc_library',
                          srcs,
                          deps,
                          'yes',
                          [], [], [], [], [],
                          blade,
                          kwargs)
        self.data['options']['recursive'] = recursive
        self.data['options']['prefix'] = prefix

    def _clone_env(self):
        """override this method. """
        env_name = self._env_name()
        self._write_rule("%s = env.Clone()" % env_name)

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        env_name = self._env_name()

        var_name = self._generate_variable_name(self.data['path'], self.data['name'])
        lex_source_file = self._target_file_path(self.data['path'],
                                                 self.data['srcs'][0])
        lex_cc_file = '%s.cc' % lex_source_file

        lex_flags = []
        if self.data.get('options', {}).get('recursive', False):
            lex_flags.append('-R')
        prefix = self.data.get('options', {}).get('prefix', None)
        if prefix:
            lex_flags.append('-P %s' % prefix)
        self._write_rule(
            "lex_%s = %s.CXXFile(LEXFLAGS=%s, target='%s', source='%s');" % (
                var_name, env_name, lex_flags, lex_cc_file, lex_source_file))
        yacc_source_file = os.path.join(self.build_path,
                                        self.data['path'],
                                        self.data['srcs'][1])
        yacc_cc_file = '%s.cc' % yacc_source_file
        yacc_hh_file = '%s.hh' % yacc_source_file

        yacc_flags = []
        if prefix:
            yacc_flags.append('-p %s' % prefix)

        self._write_rule(
            "yacc_%s = %s.Yacc(YACCFLAGS=%s, target=['%s', '%s'], source='%s');" % (
                var_name, env_name, yacc_flags,
                yacc_cc_file, yacc_hh_file, yacc_source_file))
        self._write_rule("%s.Depends(lex_%s, yacc_%s)" % (env_name,
                                                          var_name, var_name))

        self._write_rule(
            "%s = ['%s', '%s']" % (self._objs_name(),
                                   lex_cc_file,
                                   yacc_cc_file))
        self._write_rule("%s = %s.Library('%s', %s)" % (
                var_name,
                env_name,
                self._target_file_path(),
                self._objs_name()))
        self._generate_target_explict_dependency(var_name)

        options = self.blade.get_options()
        if (hasattr(options, 'generate_dynamic') and options.generate_dynamic) or (
            self.data.get('options', {}).get('build_dynamic', False)):
            self._dynamic_cc_library()


def lex_yacc_library(name,
                     srcs=[],
                     deps=[],
                     recursive=False,
                     prefix=None,
                     **kwargs):
    """lex_yacc_library. """
    lex_yacc_library = LexYaccLibrary(name,
                                      srcs,
                                      deps,
                                      recursive,
                                      prefix,
                                      blade.blade,
                                      kwargs)
    blade.blade.register_scons_target(lex_yacc_library.key, lex_yacc_library)


class ProtoLibrary(CcTarget):
    """A scons proto library target subclass.

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

        Init the proto target.

        """
        srcs_list = var_to_list(srcs)
        self._check_proto_srcs_name(srcs_list)
        CcTarget.__init__(self,
                          name,
                          'proto_library',
                          srcs,
                          deps,
                          'yes',
                          [], [], optimize, [], [],
                          blade,
                          kwargs)

        proto_config = configparse.blade_config.get_config('protoc_config')
        protobuf_lib = var_to_list(proto_config['protobuf_libs'])

        # Hardcode deps rule to thirdparty protobuf lib.
        self._add_hardcode_library(protobuf_lib)

        # Link all the symbols by default
        self.data['options']['link_all_symbols'] = True
        self.data['options']['deprecated'] = deprecated

    def _check_proto_srcs_name(self, srcs_list):
        """_check_proto_srcs_name.

        Checks whether the proto file's name ends with 'proto'.

        """
        err = 0
        for src in srcs_list:
            base_name = os.path.basename(src)
            pos = base_name.rfind('.')
            if pos == -1:
                err = 1
            file_suffix = base_name[pos + 1:]
            if file_suffix != 'proto':
                err = 1
            if err == 1:
                error_exit("invalid proto file name %s" % src)

    def _proto_gen_files(self, path, src):
        """_proto_gen_files. """
        proto_name = src[:-6]
        return (self._target_file_path(path, '%s.pb.cc' % proto_name),
                self._target_file_path(path, '%s.pb.h' % proto_name))

    def _proto_gen_php_file(self, path, src):
        """Generate the php file name. """
        proto_name = src[:-6]
        return self._target_file_path(path, '%s.pb.php' % proto_name)

    def _proto_gen_python_file(self, path, src):
        """Generate the python file name. """
        proto_name = src[:-6]
        return self._target_file_path(path, '%s_pb2.py' % proto_name)

    def _get_java_package_name(self, src):
        """Get the java package name from proto file if it is specified. """
        package_name_java = 'java_package'
        package_name = 'package'
        if not os.path.isfile(src):
            return ""
        package_line = ''
        package = ''
        normal_package_line = ''
        for line in open(src):
            line = line.strip()
            if line.startswith('//'):
                continue
            pos = line.find('//')
            if pos != -1:
                line = line[0:pos]
            if package_name_java in line:
                package_line = line
                break
            if line.startswith(package_name):
                normal_package_line = line

        if package_line:
            package = package_line.split('=')[1]
            package = package.strip("""'";\n""")
            package = package.replace('.', '/')
            return package
        elif normal_package_line:
            package = normal_package_line.split(' ')[1]
            package = package.strip("""'";\n""")
            package = package.replace('.', '/')
            return package
        else:
            return ""

    def _proto_java_gen_file(self, path, src, package):
        """Generate the java files name of the proto library. """
        proto_name = src[:-6]
        base_name  = os.path.basename(proto_name)
        base_name  = ''.join(base_name.title().split('_'))
        base_name  = '%s.java' % base_name
        dir_name = os.path.join(path, package)
        proto_name = os.path.join(dir_name, base_name)
        return os.path.join(self.build_path, proto_name)

    def _proto_java_rules(self):
        """Generate scons rules for the java files from proto file. """
        java_jar_dep_source_map =self.blade.get_java_jar_dep_source_map()
        self.sources_dependency_map = self.blade.get_sources_explict_dependency_map()
        self.sources_dependency_map[self.key] = []
        for src in self.data['srcs']:
            src_path = os.path.join(self.data['path'], src)
            package_dir = self._get_java_package_name(src_path)
            proto_java_src_package = self._proto_java_gen_file(self.data['path'],
                                                               src,
                                                               package_dir)

            self._write_rule("%s.ProtoJava(['%s'], '%s')" % (
                    self._env_name(),
                    proto_java_src_package,
                    src_path))

            java_jar_dep_source_map[self.key] = (
                     os.path.dirname(proto_java_src_package),
                     os.path.join(self.build_path, self.data['path']),
                     self.data['name'])
            self.sources_dependency_map[self.key].append(proto_java_src_package)

    def _proto_php_rules(self):
        """Generate php files. """
        for src in self.data['srcs']:
            src_path = os.path.join(self.data['path'], src)
            proto_php_src = self._proto_gen_php_file(self.data['path'], src)
            self._write_rule("%s.ProtoPhp(['%s'], '%s')" % (
                    self._env_name(),
                    proto_php_src,
                    src_path))

    def _proto_python_rules(self):
        """Generate python files. """
        self.blade.python_binary_dep_source_map[self.key] = []
        self.blade.python_binary_dep_source_cmd[self.key] = []
        for src in self.data['srcs']:
            src_path = os.path.join(self.data['path'], src)
            proto_python_src = self._proto_gen_python_file(self.data['path'], src)
            py_cmd_var = "%s_python" % self._generate_variable_name(
                    self.data['path'], self.data['name'])
            self._write_rule("%s = %s.ProtoPython(['%s'], '%s')" % (
                    py_cmd_var,
                    self._env_name(),
                    proto_python_src,
                    src_path))
            self.blade.python_binary_dep_source_cmd[self.key].append(py_cmd_var)
            self.blade.python_binary_dep_source_map[self.key].append(
                    proto_python_src)

    def _clone_env(self):
        """override this method. """
        env_name = self._env_name()
        self._write_rule("%s = env.Clone()" % env_name)

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
            self._proto_java_rules()

        if (hasattr(self.options, 'generate_php')
                and self.options.generate_php) and (
                       self.data.get('options', {}).get('generate_php', False) or (
                              self.key in self.direct_targets)):
            self._proto_php_rules()

        if (hasattr(self.options, 'generate_python')
                and self.options.generate_python) or (
                    self.data.get('options', {}).get('generate_python', False) or (
                              self.key in self.direct_targets)):
            self._proto_python_rules()

        self._setup_cc_flags()

        sources = []
        obj_names = []
        for src in self.data['srcs']:
            (proto_src, proto_hdr) = self._proto_gen_files(self.data['path'], src)

            self._write_rule("%s.Proto(['%s', '%s'], '%s')" % (
                    env_name,
                    proto_src,
                    proto_hdr,
                    os.path.join(self.data['path'], src)))
            obj_name = "%s_object" % self._generate_variable_name(
                self.data['path'], src)
            obj_names.append(obj_name)
            self._write_rule(
                "%s = %s.SharedObject(target = '%s' + env['OBJSUFFIX'], "
                "source = '%s')" % (obj_name,
                                    env_name,
                                    proto_src,
                                    proto_src))
            sources.append(proto_src)
        self._write_rule("%s = [%s]" % (self._objs_name(), ','.join(obj_names)))
        self._write_rule("%s.Depends(%s, %s)" % (
                         env_name, self._objs_name(), sources))

        self._cc_library()
        options = self.blade.get_options()
        if (hasattr(options, 'generate_dynamic') and options.generate_dynamic) or (
            self.data.get('options', {}).get('build_dynamic', False)):
            self._dynamic_cc_library()


def proto_library(name,
                  srcs=[],
                  deps=[],
                  optimize=[],
                  deprecated=False,
                  **kwargs):
    """proto_library target. """
    proto_library_target = ProtoLibrary(name,
                                        srcs,
                                        deps,
                                        optimize,
                                        deprecated,
                                        blade.blade,
                                        kwargs)
    blade.blade.register_scons_target(proto_library_target.key,
                                      proto_library_target)


class ResourceLibrary(CcTarget):
    """A scons cc target subclass.

    This class is derived from SconsCCTarget and it is the scons class
    to generate resource library rules.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 optimize,
                 extra_cppflags,
                 blade,
                 kwargs):
        """Init method.

        Init the cc target.

        """
        CcTarget.__init__(self,
                          name,
                          'resource_library',
                          srcs,
                          deps,
                          'yes',
                          [],
                          [],
                          optimize,
                          extra_cppflags,
                          [],
                          blade,
                          kwargs)

    def _clone_env(self):
        """override this method. """
        env_name = self._env_name()
        self._write_rule("%s = env.Clone()" % env_name)

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        env_name = self._env_name()
        (out_dir, res_file_name) = self._resource_library_rules_helper()

        self.data['options']['res_srcs'] = []
        for src in self.data['srcs']:
            src_path = os.path.join(self.data['path'], src)
            src_base = os.path.basename(src_path)
            src_base_name = '%s.c' % self._regular_variable_name(src_base)
            new_src_path = os.path.join(out_dir, src_base_name)
            cmd_bld = '%s_bld' % self._regular_variable_name(new_src_path)
            self._write_rule('%s = %s.ResourceFile("%s", "%s")' % (
                         cmd_bld, env_name, new_src_path, src_path))
            self.data['options']['res_srcs'].append(new_src_path)

        self._resource_library_rules_objects()

        self._cc_library()

        options = self.blade.get_options()
        if (hasattr(options, 'generate_dynamic') and options.generate_dynamic) or (
            self.data.get('options', {}).get('build_dynamic', False)):
            self._dynamic_cc_library()

    def _resource_library_rules_objects(self):
        """Generate resource library object rules.  """
        env_name = self._env_name()
        objs_name = self._objs_name()

        self._setup_cc_flags()

        objs = []
        res_srcs = self.data.get('options', {}).get('res_srcs', [])
        res_objects = {}
        path = self.data['path']
        for src in res_srcs:
            base_src_name = self._regular_variable_name(os.path.basename(src))
            src_name = base_src_name + '_' + self.data['name'] + '_res'
            if src_name not in res_objects:
                res_objects[src_name] = (
                        "%s_%s_object" % (
                                base_src_name,
                                self._regular_variable_name(self.data['name'])))
                target_path = os.path.join(self.build_path,
                                           path,
                                           '%s.objs' % self.data['name'],
                                           base_src_name)
                self._write_rule(
                        "%s = %s.SharedObject(target = '%s' + env['OBJSUFFIX']"
                        ", source = '%s')" % (res_objects[src_name],
                                              env_name,
                                              target_path,
                                              src))
            objs.append(res_objects[src_name])
        self._write_rule('%s = [%s]' % (objs_name, ','.join(objs)))

    def _resource_library_rules_helper(self):
        """The helper method to generate scons resource rules, mainly applies builder.  """
        env_name = self._env_name()
        out_dir = os.path.join(self.build_path, self.data['path'])
        res_name = self._regular_variable_name(self.data['name'])
        res_file_name = res_name
        res_file_header = res_file_name + '.h'
        res_header_path = os.path.join(out_dir, res_file_header)

        src_list = []
        for src in self.data['srcs']:
            src_path = os.path.join(self.data['path'], src)
            src_list.append(src_path)

        cmd_bld = '%s_header_cmd_bld' % res_name
        self._write_rule('%s = %s.ResourceHeader("%s", %s)' % (
                     cmd_bld, env_name, res_header_path, src_list))

        return (out_dir, res_file_name)


def resource_library(name,
                     srcs=[],
                     deps=[],
                     optimize=[],
                     extra_cppflags = [],
                     **kwargs):
    """scons_resource_library. """
    resource_library_target = ResourceLibrary(name,
                                              srcs,
                                              deps,
                                              optimize,
                                              extra_cppflags,
                                              blade.blade,
                                              kwargs)
    blade.blade.register_scons_target(resource_library_target.key,
                                      resource_library_target)


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
                          [], [], optimize, extra_swigflags, [],
                          blade,
                          kwargs)
        self.data['options']['cpperraswarn'] = warning
        self.data['options']['java_package'] = java_package
        self.data['options']['java_lib_packed'] = java_lib_packed

        scons_platform = self.blade.get_scons_platform()
        self.php_inc_list = scons_platform.get_php_include()
        self.options = self.blade.get_options()
        self.ccflags_manager = self.blade.get_ccflags_manager()

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
        env_name  = self._env_name()
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

        self.blade.python_binary_dep_source_map[self.key] = []
        self.blade.python_binary_dep_source_cmd[self.key] = []
        dep_files = []
        dep_files_map = {}
        for src in self.data['srcs']:
            pyswig_src = self._pyswig_gen_file(self.data['path'], src)
            self._write_rule('%s.%s(["%s"], "%s")' % (
                    env_name,
                    builder_alias,
                    pyswig_src,
                    os.path.join(self.data['path'], src)))
            self.blade.python_binary_dep_source_map[self.key].append(
                    self._pyswig_gen_python_file(self.data['path'], src))
            obj_name_py = "%s_object" % self._generate_variable_name(
                self.data['path'], src, 'python')
            obj_names_py.append(obj_name_py)

            self._write_rule(
                "%s = %s.SharedObject(target = '%s' + env['OBJSUFFIX'], "
                "source = '%s')" % (obj_name_py,
                                    env_name,
                                    pyswig_src,
                                    pyswig_src))
            self.blade.python_binary_dep_source_cmd[self.key].append(
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
                    '%s.Append(LINKFLAGS=%s)' % (env_name, whole_link_flags))

        if self.data['srcs'] or self.data['deps']:
            self._write_rule('%s.Append(LINKFLAGS=["-fPIC"])' % env_name)
            self._write_rule("%s = %s.SharedLibrary('%s', %s, %s, SHLIBPREFIX = '')"
                    % (var_name,
                       env_name,
                       target_path_py,
                       objs_name_py,
                       lib_str))
            self.blade.python_binary_dep_source_map[self.key].append(
                    "%s.so" % target_path_py)
            self.blade.python_binary_dep_source_cmd[self.key].append(var_name)

        for i in link_all_symbols_lib_list:
            self._write_rule("%s.Depends(%s, %s)" % (
                    env_name, var_name, i[1]))

        self._generate_target_explict_dependency(var_name)

        return dep_files_map

    def _swig_library_rules_java(self, dep_files_map):
        """_swig_library_rules_java. """
        env_name = self._env_name()
        var_name = self._generate_variable_name(self.data['path'],
                                                self.data['name'],
                                                'dynamic_java')
        self.java_jar_dep_vars = self.blade.get_java_jar_dep_vars()
        self.java_jar_dep_vars[self.key] = []

        java_jar_dep_source_map = self.blade.get_java_jar_dep_source_map()

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

        sources_dependency_map = self.blade.get_sources_explict_dependency_map()
        sources_dependency_map[self.key] = []
        dep_files = []
        for src in self.data['srcs']:
            javaswig_src = self._javaswig_gen_file(self.data['path'], src)
            src_basename = os.path.basename(src)
            javaswig_var = "%s_%s"% (
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
                    "%s = %s.SharedObject(target = '%s' + env['OBJSUFFIX'], "
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

        for i in link_all_symbols_lib_list:
            self._write_rule("%s.Depends(%s, %s)" % (
                    env_name, var_name, i[1]))

        self._generate_target_explict_dependency(var_name)

        jar_files_packing_map = self.blade.get_java_jar_files_packing_map()
        if build_jar and java_lib_packed:
            lib_dir = os.path.dirname(target_path_java)
            lib_name = os.path.basename(target_path_java)
            lib_name = 'lib%s.so' % lib_name
            jar_files_packing_map[self.key] = (
                    os.path.join(lib_dir,lib_name), self.data['name'])

    def _swig_library_rules_php(self, dep_files_map):
        env_name  = self._env_name()
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
                    os.path.join(self.data['path'],src)))
            obj_name_php = "%s_object" % self._generate_variable_name(
                self.data['path'], src, 'php')
            obj_names_php.append(obj_name_php)

            self._write_rule(
                "%s = %s.SharedObject(target = '%s' + env['OBJSUFFIX'], "
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
            self._write_rule('%s.Append(LINKFLAGS=["-fPIC"])' % env_name)
            self._write_rule("%s = %s.SharedLibrary('%s', %s, %s, SHLIBPREFIX='')" % (
                    var_name,
                    env_name,
                    target_path_php,
                    objs_name_php,
                    lib_str))

        for i in link_all_symbols_lib_list:
            self._write_rule("%s.Depends(%s, %s)" % (
                    env_name, var_name, i[1]))

        self._generate_target_explict_dependency(var_name)

    def _clone_env(self):
        """override this method. """
        env_name = self._env_name()
        self._write_rule("%s = env_no_warning.Clone()" % env_name)

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
                error_exit("failed to build //%s:%s, please install php modules" % (
                           self.data['path'], self.data['name']))
            else:
                self._swig_library_rules_php(dep_files_map)


def swig_library(name,
                 srcs=[],
                 deps=[],
                 warning='yes',
                 java_package='',
                 java_lib_packed=False,
                 optimize=[],
                 extra_swigflags=[],
                 **kwargs):
    """swig_library target. """
    swig_library_target = SwigLibrary(name,
                                      srcs,
                                      deps,
                                      warning,
                                      java_package,
                                      java_lib_packed,
                                      optimize,
                                      extra_swigflags,
                                      blade.blade,
                                      kwargs)
    blade.blade.register_scons_target(swig_library_target.key,
                                      swig_library_target)
