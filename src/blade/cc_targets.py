# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the cc_target module which is the super class
 of all of the scons cc targets, like cc_library, cc_binary.

"""


import os
import subprocess
import Queue

import blade
import configparse
import console
import build_rules
from blade_util import var_to_list, stable_unique
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
                 visibility,
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
                        visibility,
                        blade,
                        kwargs)

        self.data['warning'] = warning
        self.data['defs'] = defs
        self.data['incs'] = incs
        self.data['export_incs'] = export_incs
        self.data['optimize'] = opt
        self.data['extra_cppflags'] = extra_cppflags
        self.data['extra_linkflags'] = extra_linkflags

        self._check_defs()
        self._check_incorrect_no_warning()

    def _check_deprecated_deps(self):
        """Check whether it depends upon a deprecated library. """
        for key in self.deps:
            dep = self.target_database.get(key)
            if dep and dep.data.get('deprecated'):
                replaced_deps = dep.deps
                if replaced_deps:
                    console.warning('%s: //%s has been deprecated, '
                                    'please depends on //%s:%s' % (
                                    self.fullname, dep.fullname,
                                    replaced_deps[0][0], replaced_deps[0][1]))

    def _prepare_to_generate_rule(self):
        """Should be overridden. """
        self._check_deprecated_deps()
        self._clone_env()

    def _clone_env(self):
        """Select env. """
        env_name = self._env_name()
        warning = self.data.get('warning', '')
        if warning == 'yes':
            self._write_rule('%s = env_with_error.Clone()' % env_name)
        else:
            self._write_rule('%s = env_no_warning.Clone()' % env_name)

    __cxx_keyword_list = frozenset([
        'and', 'and_eq', 'alignas', 'alignof', 'asm', 'auto',
        'bitand', 'bitor', 'bool', 'break', 'case', 'catch',
        'char', 'char16_t', 'char32_t', 'class', 'compl', 'const',
        'constexpr', 'const_cast', 'continue', 'decltype', 'default',
        'delete', 'double', 'dynamic_cast', 'else', 'enum',
        'explicit', 'export', 'extern', 'false', 'float', 'for',
        'friend', 'goto', 'if', 'inline', 'int', 'long', 'mutable',
        'namespace', 'new', 'noexcept', 'not', 'not_eq', 'nullptr',
        'operator', 'or', 'or_eq', 'private', 'protected', 'public',
        'register', 'reinterpret_cast', 'return', 'short', 'signed',
        'sizeof', 'static', 'static_assert', 'static_cast', 'struct',
        'switch', 'template', 'this', 'thread_local', 'throw',
        'true', 'try', 'typedef', 'typeid', 'typename', 'union',
        'unsigned', 'using', 'virtual', 'void', 'volatile', 'wchar_t',
        'while', 'xor', 'xor_eq'])

    def _check_defs(self):
        """_check_defs.

        It will warn if user defines cpp keyword in defs list.

        """
        defs_list = self.data.get('defs', [])
        for macro in defs_list:
            pos = macro.find('=')
            if pos != -1:
                macro = macro[0:pos]
            if macro in CcTarget.__cxx_keyword_list:
                console.warning('DO NOT define c++ keyword %s as macro' % macro)

    def _check_incorrect_no_warning(self):
        """check if warning=no is correctly used or not. """
        warning = self.data.get('warning', 'yes')
        srcs = self.srcs
        if not srcs or warning != 'no':
            return

        keywords_list = self.blade.get_sources_keyword_list()
        for keyword in keywords_list:
            if keyword in self.path:
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

        Concatenating target path, target name to be objs var and returns.

        """
        return 'objs_%s' % self._generate_variable_name(self.path, self.name)

    def _prebuilt_cc_library_path(self, prefer_dynamic=False):
        """

        Return source and target path of the prebuilt cc library.
        When both .so and .a exist, return .so if prefer_dynamic is True.
        Otherwise return the existing one.

        """
        a_src_path = self._prebuilt_cc_library_pathname(dynamic=False)
        so_src_path = self._prebuilt_cc_library_pathname(dynamic=True)
        libs = (a_src_path, so_src_path) # Ordered by priority
        if prefer_dynamic:
            libs = (so_src_path, a_src_path)
        source = ''
        for lib in libs:
            if os.path.exists(lib):
                source = lib
                break
        if not source:
            console.error_exit('%s: Can not find either %s or %s' % (
                               self.fullname, libs[0], libs[1]))
        target = self._target_file_path(os.path.basename(source))
        return source, target

    def _prebuilt_cc_library_pathname(self, dynamic=False):
        options = self.blade.get_options()
        suffix = 'a'
        if dynamic:
            suffix = 'so'
        return os.path.join(self.path, 'lib%s_%s' % (options.m, options.profile),
                            'lib%s.%s' % (self.name, suffix))

    def _prebuilt_cc_library_dynamic_soname(self, so):
        """Get the soname of prebuilt shared library. """
        soname = None
        output = subprocess.check_output('objdump -p %s' % so, shell=True)
        for line in output.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] == 'SONAME':
                soname = parts[1]
                break
        return soname

    def _setup_cc_flags(self):
        """_setup_cc_flags. """
        env_name = self._env_name()
        flags_from_option, incs_list = self._get_cc_flags()
        if flags_from_option:
            self._write_rule('%s.Append(CPPFLAGS=%s)' % (env_name, flags_from_option))
        if incs_list:
            self._write_rule('%s.Append(CPPPATH=%s)' % (env_name, incs_list))

    def _setup_as_flags(self):
        """_setup_as_flags. """
        env_name = self._env_name()
        as_flags, aspp_flags = self._get_as_flags()
        if as_flags:
            self._write_rule('%s.Append(ASFLAGS=%s)' % (env_name, as_flags))
        if aspp_flags:
            self._write_rule('%s.Append(ASPPFLAGS=%s)' % (env_name, aspp_flags))

    def _setup_link_flags(self):
        """linkflags. """
        extra_linkflags = self.data.get('extra_linkflags')
        if extra_linkflags:
            self._write_rule('%s.Append(LINKFLAGS=%s)' % (self._env_name(), extra_linkflags))

    def _get_optimize_flags(self):
        """get optimize flags such as -O2"""
        oflags = []
        opt_list = self.data.get('optimize')
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
        if self.data.get('warning', '') == 'no':
            cpp_flags.append('-w')

        # Defs
        defs = self.data.get('defs', [])
        cpp_flags += [('-D' + macro) for macro in defs]

        # Optimize flags
        if (self.blade.get_options().profile == 'release' or
            self.data.get('always_optimize')):
            cpp_flags += self._get_optimize_flags()
            # Add -fno-omit-frame-pointer to optimize mode for easy debugging.
            cpp_flags += ['-fno-omit-frame-pointer']

        cpp_flags += self.data.get('extra_cppflags', [])

        # Incs
        incs = self.data.get('incs', []) + self.data.get('export_incs', [])
        incs = [os.path.normpath(os.path.join(self.path, inc)) for inc in incs]
        incs += self._export_incs_list()
        # Remove duplicate items in incs list and keep the order
        incs = stable_unique(incs)

        return (cpp_flags, incs)

    def _get_as_flags(self):
        """_get_as_flags.

        Return the as flags according to the build architecture.

        """
        options = self.blade.get_options()
        as_flags = ['-g', '--' + options.m]
        aspp_flags = ['-Wa,--' + options.m]
        return as_flags, aspp_flags

    def _export_incs_list(self):
        """_export_incs_list.
        TODO
        """
        deps = self.expanded_deps
        inc_list = []
        for lib in deps:
            # system lib
            if lib[0] == '#':
                continue

            target = self.target_database[lib]
            for inc in target.data.get('export_incs', []):
                path = os.path.normpath(os.path.join(target.path, inc))
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
        lib_list = []
        link_all_symbols_lib_list = []
        for dep in self.expanded_deps:
            dep_target = build_targets[dep]
            if dep_target.type == 'cc_library' and not dep_target.srcs:
                continue
            # system lib
            if dep_target.type == 'system_library':
                lib_name = "'%s'" % dep_target.name
            else:
                lib_name = dep_target.data.get('static_cc_library_var')
            if lib_name:
                if dep_target.data.get('link_all_symbols'):
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
        lib_list = []
        for lib in self.expanded_deps:
            dep_target = build_targets[lib]
            if (dep_target.type == 'cc_library' and
                not dep_target.srcs):
                continue
            # system lib
            if lib[0] == '#':
                lib_name = "'%s'" % lib[1]
            else:
                lib_name = dep_target.data.get('dynamic_cc_library_var')
            if lib_name:
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
        return 'LIBS=[%s]' % ','.join(lib_list)

    def _prebuilt_cc_library_is_depended(self):
        build_targets = self.blade.get_build_targets()
        for key in build_targets:
            target = build_targets[key]
            if (self.key in target.expanded_deps and
                target.type != 'prebuilt_cc_library'):
                return True
        return False

    def _prebuilt_cc_library_rules(self, var_name, target, source):
        """Generate scons rules for prebuilt cc library. """
        if source.endswith('.a'):
            self._write_rule('%s = top_env.File("%s")' % (var_name, source))
        else:
            self._write_rule('%s = top_env.Command("%s", "%s", '
                             'Copy("$TARGET", "$SOURCE"))' % (
                             var_name, target, source))

    def _prebuilt_cc_library(self):
        """Prebuilt cc library rules. """
        # We allow a prebuilt cc_library doesn't exist if it is not used.
        # So if this library is not depended by any target, don't generate any
        # rule to avoid runtime error and also avoid unnecessary runtime cost.
        if not self._prebuilt_cc_library_is_depended():
            return

        # Paths for static linking, may be a dynamic library!
        static_src_path, static_target_path = self._prebuilt_cc_library_path()
        var_name = self._var_name()
        self._prebuilt_cc_library_rules(var_name, static_target_path, static_src_path)
        self.data['static_cc_library_var'] = var_name

        dynamic_src_path, dynamic_target_path = '', ''
        if self._need_dynamic_library():
            dynamic_src_path, dynamic_target_path = self._prebuilt_cc_library_path(
                    prefer_dynamic=True)
            # Avoid copy twice if has only one kind of library
            if dynamic_target_path != static_target_path:
                var_name = self._var_name('dynamic')
                self._prebuilt_cc_library_rules(var_name,
                                                dynamic_target_path,
                                                dynamic_src_path)
            self.data['dynamic_cc_library_var'] = var_name

        # Make a symbol link if either lib is a so
        self.file_and_link = None
        so_src, so_target = '', ''
        if static_target_path.endswith('.so'):
            so_src = static_src_path
            so_target = static_target_path
        elif dynamic_target_path.endswith('.so'):
            so_src = dynamic_src_path
            so_target = dynamic_target_path
        if so_src:
            soname = self._prebuilt_cc_library_dynamic_soname(so_src)
            if soname:
                self.file_and_link = (so_target, soname)

    def _static_cc_library(self):
        """_cc_library.

        It will output the cc_library rule into the buffer.

        """
        env_name = self._env_name()
        var_name = self._var_name()
        self._write_rule('%s = %s.Library("%s", %s)' % (
                var_name,
                env_name,
                self._target_file_path(),
                self._objs_name()))
        self.data['static_cc_library_var'] = var_name
        self._add_default_target_var('a', var_name)

    def _dynamic_cc_library(self):
        """_dynamic_cc_library.

        It will output the dynamic_cc_library rule into the buffer.

        """
        self._setup_link_flags()

        var_name = self._var_name('dynamic')
        env_name = self._env_name()

        lib_str = self._get_dynamic_deps_lib_list()
        if self.srcs or self.expanded_deps:
            if not self.data.get('allow_undefined'):
                self._write_rule('%s.Append(LINKFLAGS=["-Xlinker", "--no-undefined"])'
                        % env_name)
            self._write_rule('%s = %s.SharedLibrary("%s", %s, %s)' % (
                    var_name,
                    env_name,
                    self._target_file_path(),
                    self._objs_name(),
                    lib_str))
            self.data['dynamic_cc_library_var'] = var_name
            self._add_target_var('so', var_name)

    def _need_dynamic_library(self):
        options = self.blade.get_options()
        config = configparse.blade_config.get_config('cc_library_config')
        return (getattr(options, 'generate_dynamic') or
                self.data.get('build_dynamic') or
                config.get('generate_dynamic'))

    def _cc_library(self):
        self._static_cc_library()
        if self._need_dynamic_library():
            self._dynamic_cc_library()

    def _generate_generated_header_files_depends(self, var_name):
        """Generate dependencies to targets that generate header files. """
        env_name = self._env_name()
        q = Queue.Queue(0)
        for key in self.deps:
            q.put(key)

        keys = set()
        while not q.empty():
            key = q.get()
            if key not in keys:
                keys.add(key)
                dep = self.target_database[key]
                if dep._generate_header_files():
                    if dep.srcs:
                        self._write_rule('%s.Depends(%s, %s)' % (
                                         env_name, var_name, dep._var_name()))
                    else:
                        for k in dep.deps:
                            q.put(k)

    def _cc_objects_rules(self):
        """_cc_objects_rules.

        Generate the cc objects rules for the srcs in srcs list.

        """
        target_types = ['cc_library',
                        'cc_binary',
                        'cc_test',
                        'cc_plugin']

        if not self.type in target_types:
            console.error_exit('logic error, type %s err in object rule' % self.type)

        objs_name = self._objs_name()
        env_name = self._env_name()

        self._setup_cc_flags()

        objs = []
        for src in self.srcs:
            obj = '%s_%s_object' % (self._var_name_of(src),
                                    self._regular_variable_name(self.name))
            target_path = self._target_file_path() + '.objs/%s' % src
            source_path = self._target_file_path(src)  # Also find generated files
            rule_args = ('target = "%s" + top_env["OBJSUFFIX"], source = "%s"' %
                         (target_path, source_path))
            if self.data.get('secure'):
                rule_args += ', CXX = "$SECURECXX"'
            self._write_rule('%s = %s.SharedObject(%s)' % (obj, env_name, rule_args))
            if self.data.get('secure'):
                self._securecc_object_rules(obj, source_path)
            objs.append(obj)
        self._write_rule('%s = [%s]' % (objs_name, ','.join(objs)))
        self._generate_generated_header_files_depends(objs_name)

        if objs:
            objs_dirname = self._target_file_path() + '.objs'
            self._write_rule('%s.Clean([%s], "%s")' % (env_name, objs_name, objs_dirname))

    def _securecc_object_rules(self, obj, src):
        """Touch the source file if needed and generate specific object rules for securecc. """
        env_name = self._env_name()
        self._write_rule('%s.AlwaysBuild(%s)' % (env_name, obj))
        if not os.path.exists(src):
            dir = os.path.dirname(src)
            if not os.path.isdir(dir):
                os.makedirs(dir)
            open(src, 'w').close()


class CcLibrary(CcTarget):
    """A cc target subclass.

    This class is derived from SconsTarget and it generates the library
    rules including dynamic library rules according to user option.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
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
                 allow_undefined,
                 secure,
                 blade,
                 kwargs):
        """Init method.

        Init the cc library.

        """
        CcTarget.__init__(self,
                          name,
                          'cc_library',
                          srcs,
                          deps,
                          visibility,
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
            self.type = 'prebuilt_cc_library'
            self.srcs = []
        self.data['link_all_symbols'] = link_all_symbols
        self.data['always_optimize'] = always_optimize
        self.data['deprecated'] = deprecated
        self.data['allow_undefined'] = allow_undefined
        self.data['secure'] = secure

    def _rpath_link(self, dynamic):
        path = self._prebuilt_cc_library_path(dynamic)[1]
        if path.endswith('.so'):
            return os.path.dirname(path)
        return None

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        if self.type == 'prebuilt_cc_library':
            self._check_deprecated_deps()
            self._prebuilt_cc_library()
        elif self.srcs:
            self._prepare_to_generate_rule()
            self._cc_objects_rules()
            self._cc_library()


def cc_library(name,
               srcs=[],
               deps=[],
               visibility=None,
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
               allow_undefined=False,
               secure=False,
               **kwargs):
    """cc_library target. """
    target = CcLibrary(name,
                       srcs,
                       deps,
                       visibility,
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
                       allow_undefined,
                       secure,
                       blade.blade,
                       kwargs)
    if pre_build:
        console.warning("//%s:%s: 'pre_build' has been deprecated, "
                        "please use 'prebuilt'" % (target.path, target.name))
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
                 embed_version,
                 optimize,
                 dynamic_link,
                 extra_cppflags,
                 extra_linkflags,
                 export_dynamic,
                 blade,
                 kwargs):
        """Init method.

        Init the cc binary.

        """
        CcTarget.__init__(self,
                          name,
                          'cc_binary',
                          srcs,
                          deps,
                          None,
                          warning,
                          defs,
                          incs,
                          [],
                          optimize,
                          extra_cppflags,
                          extra_linkflags,
                          blade,
                          kwargs)
        self.data['embed_version'] = embed_version
        self.data['dynamic_link'] = dynamic_link
        self.data['export_dynamic'] = export_dynamic

        cc_binary_config = configparse.blade_config.get_config('cc_binary_config')
        # add extra link library
        link_libs = var_to_list(cc_binary_config['extra_libs'])
        self._add_hardcode_library(link_libs)

    def _allow_duplicate_source(self):
        return True

    def _get_rpath_links(self):
        """Get rpath_links from dependencies"""
        dynamic_link = self.data['dynamic_link']
        build_targets = self.blade.get_build_targets()
        rpath_links = []
        for lib in self.expanded_deps:
            if build_targets[lib].type == 'prebuilt_cc_library':
                path = build_targets[lib]._rpath_link(dynamic_link)
                if path and path not in rpath_links:
                    rpath_links.append(path)

        return rpath_links

    def _write_rpath_links(self):
        rpath_links = self._get_rpath_links()
        if rpath_links:
            for rpath_link in rpath_links:
                self._write_rule('%s.Append(LINKFLAGS="-Wl,--rpath-link=%s")' %
                        (self._env_name(), rpath_link))

    def _cc_binary(self):
        """_cc_binary rules. """
        env_name = self._env_name()
        var_name = self._var_name()

        platform = self.blade.get_scons_platform()
        if platform.get_gcc_version() > '4.5':
            link_flag_list = ['-static-libgcc', '-static-libstdc++']
            self._write_rule('%s.Append(LINKFLAGS=%s)' % (env_name, link_flag_list))

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

        self._write_rule('%s = %s.Program("%s", %s, %s)' % (
            var_name,
            env_name,
            self._target_file_path(),
            self._objs_name(),
            lib_str))
        self._add_default_target_var('bin', var_name)

        if link_all_symbols_lib_list:
            self._write_rule('%s.Depends(%s, [%s])' % (
                    env_name, var_name, ', '.join(link_all_symbols_lib_list)))

        self._write_rpath_links()
        if self.data['embed_version']:
            self._write_rule('%s.Append(LINKFLAGS=str(version_obj[0]))' % env_name)
            self._write_rule('%s.Requires(%s, version_obj)' % (env_name, var_name))

    def _dynamic_cc_binary(self):
        """_dynamic_cc_binary. """
        env_name = self._env_name()
        var_name = self._var_name()
        if self.data.get('export_dynamic'):
            self._write_rule('%s.Append(LINKFLAGS="-rdynamic")' % env_name)

        self._setup_link_flags()

        lib_str = self._get_dynamic_deps_lib_list()
        self._write_rule('%s = %s.Program("%s", %s, %s)' % (
            var_name,
            env_name,
            self._target_file_path(),
            self._objs_name(),
            lib_str))
        self._add_default_target_var('bin', var_name)

        if self.data['embed_version']:
            self._write_rule('%s.Append(LINKFLAGS=str(version_obj[0]))' % env_name)
            self._write_rule('%s.Requires(%s, version_obj)' % (env_name, var_name))

        self._write_rpath_links()

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        self._cc_objects_rules()

        if self.data['dynamic_link']:
            self._dynamic_cc_binary()
        else:
            self._cc_binary()


def cc_binary(name,
              srcs=[],
              deps=[],
              warning='yes',
              defs=[],
              incs=[],
              embed_version=True,
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
                                embed_version,
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
                 optimize,
                 prefix,
                 suffix,
                 extra_cppflags,
                 extra_linkflags,
                 allow_undefined,
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
                          None,
                          warning,
                          defs,
                          incs,
                          [],
                          optimize,
                          extra_cppflags,
                          extra_linkflags,
                          blade,
                          kwargs)
        self.prefix = prefix
        self.suffix = suffix
        self.data['allow_undefined'] = allow_undefined

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        env_name = self._env_name()
        var_name = self._var_name()

        self._cc_objects_rules()
        self._setup_link_flags()

        (link_all_symbols_lib_list,
         lib_str,
         whole_link_flags) = self._get_static_deps_lib_list()
        if whole_link_flags:
            self._write_rule(
                    '%s.Append(LINKFLAGS=[%s])' % (env_name, whole_link_flags))

        if self.prefix is not None:
            self._write_rule(
                    '%s.Replace(SHLIBPREFIX="%s")' % (env_name, self.prefix))

        if self.suffix is not None:
            self._write_rule(
                    '%s.Replace(SHLIBSUFFIX="%s")' % (env_name, self.suffix))

        if not self.data['allow_undefined']:
            self._write_rule('%s.Append(LINKFLAGS=["-Xlinker", "--no-undefined"])'
                    % env_name)

        if self.srcs or self.expanded_deps:
            self._write_rule('%s = %s.SharedLibrary("%s", %s, %s)' % (
                    var_name,
                    env_name,
                    self._target_file_path(),
                    self._objs_name(),
                    lib_str))
            self._add_default_target_var('so', var_name)

        if link_all_symbols_lib_list:
            self._write_rule('%s.Depends(%s, [%s])' % (
                env_name, var_name, ', '.join(link_all_symbols_lib_list)))


def cc_plugin(name,
              srcs=[],
              deps=[],
              warning='yes',
              defs=[],
              incs=[],
              optimize=[],
              prefix=None,
              suffix=None,
              extra_cppflags=[],
              extra_linkflags=[],
              allow_undefined=True,
              **kwargs):
    """cc_plugin target. """
    target = CcPlugin(name,
                      srcs,
                      deps,
                      warning,
                      defs,
                      incs,
                      optimize,
                      prefix,
                      suffix,
                      extra_cppflags,
                      extra_linkflags,
                      allow_undefined,
                      blade.blade,
                      kwargs)
    blade.blade.register_target(target)


build_rules.register_function(cc_plugin)


# See http://google-perftools.googlecode.com/svn/trunk/doc/heap_checker.html
HEAP_CHECK_VALUES = set([
    '',
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
                 embed_version,
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

        Init the cc test.

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
                          embed_version,
                          optimize,
                          dynamic_link,
                          extra_cppflags,
                          extra_linkflags,
                          export_dynamic,
                          blade,
                          kwargs)
        self.type = 'cc_test'
        self.data['testdata'] = var_to_list(testdata)
        self.data['always_run'] = always_run
        self.data['exclusive'] = exclusive

        gtest_lib = var_to_list(cc_test_config['gtest_libs'])
        gtest_main_lib = var_to_list(cc_test_config['gtest_main_libs'])

        # Hardcode deps rule to thirdparty gtest main lib.
        self._add_hardcode_library(gtest_lib)
        self._add_hardcode_library(gtest_main_lib)

        if heap_check is None:
            heap_check = cc_test_config.get('heap_check', '')
        else:
            if heap_check not in HEAP_CHECK_VALUES:
                console.error_exit('//%s:%s: heap_check can only be in %s' % (
                    self.path, self.name, HEAP_CHECK_VALUES))

        perftools_lib = var_to_list(cc_test_config['gperftools_libs'])
        perftools_debug_lib = var_to_list(cc_test_config['gperftools_debug_libs'])
        if heap_check:
            self.data['heap_check'] = heap_check

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
            embed_version=False,
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
                            embed_version,
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
