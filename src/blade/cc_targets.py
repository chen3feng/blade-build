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
from string import Template
import Queue

import blade
import config
import console
import build_rules
from blade_util import var_to_list, stable_unique
from target import Target


if "check_output" not in dir( subprocess ):
    from blade_util import check_output
    subprocess.check_output = check_output


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
        self.data['incs'] = self._incs_to_fullpath(incs)
        self.data['export_incs'] = self._incs_to_fullpath(export_incs)
        self.data['optimize'] = opt
        self.data['extra_cppflags'] = extra_cppflags
        self.data['extra_linkflags'] = extra_linkflags
        self.data['objs_name'] = None
        self.data['hdrs'] = []

        self._check_defs()
        self._check_incorrect_no_warning()

    def _incs_to_fullpath(self, incs):
        return [os.path.normpath(os.path.join(self.path, inc)) for inc in incs]

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
            self._write_rule('%s = env_cc_warning.Clone()' % env_name)
        else:
            self._write_rule('%s = env_cc.Clone()' % env_name)

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

        It will warn if user defines c++ keyword in defs list.

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
            console.warning("//%s: warning='no' should only be used "
                            "for code in thirdparty." % self.fullname)

    def _objs_name(self):
        """Concatenating path and name to be objs var. """
        name = self.data['objs_name']
        if name is None:
            name = 'objs_%s' % self._generate_variable_name(self.path, self.name)
            self.data['objs_name'] = name
        return name

    def _set_objs_name(self, name):
        """Set objs var name to the input name. """
        self.data['objs_name'] = name

    def _prebuilt_cc_library_path(self, prefer_dynamic=False):
        """

        Return source and target path of the prebuilt cc library.
        When both .so and .a exist, return .so if prefer_dynamic is True.
        Otherwise return the existing one.

        """
        a_src_path, so_src_path = self._prebuilt_cc_library_pathname()
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

    _default_prebuilt_libpath = None

    def _prebuilt_cc_library_pathname(self):
        options = self.blade.get_options()
        bits, arch, profile = options.bits, options.arch, options.profile
        if CcTarget._default_prebuilt_libpath is None:
            pattern = config.get_item('cc_library_config', 'prebuilt_libpath_pattern')
            CcTarget._default_prebuilt_libpath = Template(pattern).substitute(
                    bits=bits, arch=arch, profile=profile)

        pattern = self.data.get('prebuilt_libpath_pattern')
        if pattern:
            libpath = Template(pattern).substitute(bits=bits,
                                                   arch=arch,
                                                   profile=profile)
        else:
            libpath = CcTarget._default_prebuilt_libpath
        return [os.path.join(self.path, libpath, 'lib%s.%s' % (self.name, s))
                for s in ['a', 'so']]

    def _prebuilt_cc_library_dynamic_soname(self, so):
        """Get the soname of prebuilt shared library. """
        soname = None
        try:
            output = subprocess.check_output('objdump -p %s' % so, shell=True)
            for line in output.splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[0] == 'SONAME':
                    soname = parts[1]
                    break
        except subprocess.CalledProcessError:
            pass
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
            opt_list = config.get_item('cc_config', 'optimize')
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
        incs = self._get_incs_list()

        return (cpp_flags, incs)

    def _get_as_flags(self):
        """Return as flags according to the build architecture. """
        options = self.blade.get_options()
        if options.m:
            as_flags = ['-g', '--' + options.m]
            aspp_flags = ['-Wa,--' + options.m]
            return as_flags, aspp_flags
        return [], []

    def _export_incs_list(self):
        inc_list = []
        for dep in self.expanded_deps:
            # system dep
            if dep[0] == '#':
                continue

            target = self.target_database[dep]
            inc_list += target.data.get('export_incs', [])
        return inc_list

    def _get_incs_list(self):
        """Get all incs includes export_incs of all depends. """
        incs = self.data.get('incs', []) + self.data.get('export_incs', [])
        incs += self._export_incs_list()
        # Remove duplicate items in incs list and keep the order
        incs = stable_unique(incs)
        return incs

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
        depended_targets = self.blade.get_depended_target_database()
        for key in depended_targets[self.key]:
            t = build_targets[key]
            if t.type != 'prebuilt_cc_library':
                return True
        return False

    def _prebuilt_cc_library_rules(self, var_name, target, source):
        """Generate scons rules for prebuilt cc library. """
        if source.endswith('.a'):
            self._write_rule('%s = top_env.File("%s")' % (var_name, os.path.realpath(source)))
        else:
            self._write_rule('%s = top_env.Command("%s", "%s", '
                             'Copy("$TARGET", "$SOURCE"))' % (
                             var_name, target, os.path.realpath(source)))

    def _prebuilt_cc_library_symbolic_link(self,
                                           static_lib_source, static_lib_target,
                                           dynamic_lib_source, dynamic_lib_target):
        """Make a symbolic link if either static or dynamic library is so. """
        self.file_and_link = None
        so_src, so_target = '', ''
        if static_lib_target.endswith('.so'):
            so_src = static_lib_source
            so_target = static_lib_target
        elif dynamic_lib_target.endswith('.so'):
            so_src = dynamic_lib_source
            so_target = dynamic_lib_target
        if so_src:
            soname = self._prebuilt_cc_library_dynamic_soname(so_src)
            if soname:
                self.file_and_link = (so_target, soname)

    def _prebuilt_cc_library_scons_rules(self):
        """Prebuilt cc library scons rules. """
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

        return (static_src_path, static_target_path,
                dynamic_src_path, dynamic_target_path)

    def _prebuilt_cc_library(self):
        """Prebuilt cc library rules. """
        # We allow a prebuilt cc_library doesn't exist if it is not used.
        # So if this library is not depended by any target, don't generate any
        # rule to avoid runtime error and also avoid unnecessary runtime cost.
        if not self._prebuilt_cc_library_is_depended():
            return

        if config.get_item('global_config', 'native_builder') == 'ninja':
            paths = self._prebuilt_cc_library_ninja_rules()
        else:
            paths = self._prebuilt_cc_library_scons_rules()
        self._prebuilt_cc_library_symbolic_link(*paths)

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
        return (getattr(options, 'generate_dynamic') or
                self.data.get('build_dynamic') or
                config.get_item('cc_library_config', 'generate_dynamic'))

    def _cc_library(self):
        self._static_cc_library()
        if self._need_dynamic_library():
            self._dynamic_cc_library()

    def _generated_header_files_dependencies(self):
        """Return dependencies which generate header files. """
        q = Queue.Queue(0)
        for key in self.deps:
            q.put(key)

        keys = set()
        deps = []
        while not q.empty():
            key = q.get()
            if key not in keys:
                keys.add(key)
                dep = self.target_database[key]
                if dep._generate_header_files():
                    if dep.srcs:
                        deps.append(dep)
                    else:
                        for k in dep.deps:
                            q.put(k)

        return deps

    def _generate_generated_header_files_depends(self, var_name):
        """Generate dependencies to targets that generate header files. """
        env_name = self._env_name()
        deps = self._generated_header_files_dependencies()
        for dep in deps:
            self._write_rule('%s.Depends(%s, %s)' % (
                             env_name, var_name, dep._var_name()))

    def _cc_objects_rules(self):
        """_cc_objects_rules.

        Generate the cc objects rules for the srcs in srcs list.

        """
        if self.type not in ('cc_library', 'cc_binary', 'cc_test', 'cc_plugin'):
            console.error_exit('logic error, type %s err in object rule' % self.type)

        env_name = self._env_name()
        objs_dir = self._target_file_path() + '.objs'

        self._setup_cc_flags()

        objs = []
        for src in self.srcs:
            obj = 'obj_%s' % self._var_name_of(src)
            target_path = os.path.join(objs_dir, src)
            source_path = self._target_file_path(src)  # Also find generated files
            rule_args = ('target = "%s" + top_env["OBJSUFFIX"], source = "%s"' %
                         (target_path, source_path))
            if self.data.get('secure'):
                rule_args += ', CXX = "$SECURECXX"'
            self._write_rule('%s = %s.SharedObject(%s)' % (obj, env_name, rule_args))
            if self.data.get('secure'):
                self._securecc_object_rules(obj, source_path)
            objs.append(obj)

        if len(objs) == 1:
            self._set_objs_name(objs[0])
            objs_name = objs[0]
        else:
            objs_name = self._objs_name()
            self._write_rule('%s = [%s]' % (objs_name, ','.join(objs)))
        self._generate_generated_header_files_depends(objs_name)

        if objs and self.blade.get_command() == 'clean':
            self._write_rule('%s.Clean([%s], "%s")' % (env_name, objs_name, objs_dir))

    def _securecc_object_rules(self, obj, src, scons=True):
        """Touch the source file if needed and generate specific object rules for securecc. """
        if scons:
            env_name = self._env_name()
            self._write_rule('%s.AlwaysBuild(%s)' % (env_name, obj))
        if not os.path.exists(src):
            dir = os.path.dirname(src)
            if not os.path.isdir(dir):
                os.makedirs(dir)
            open(src, 'w').close()

    def _prebuilt_cc_library_ninja_rules(self):
        """Prebuilt cc library ninja rules.

        There are 3 cases for prebuilt library as below:

            1. Only static library(.a) exists
            2. Only dynamic library(.so) exists
            3. Both static and dynamic libraries exist
        """
        static_src_path, static_target_path = self._prebuilt_cc_library_path()
        if static_src_path.endswith('.a'):
            path = static_src_path
        else:
            self.ninja_build(static_target_path, 'copy',
                             inputs=static_src_path)
            path = static_target_path
        self._add_default_target_file('a', path)

        dynamic_src_path, dynamic_target_path = '', ''
        if self._need_dynamic_library():
            dynamic_src_path, dynamic_target_path = self._prebuilt_cc_library_path(True)
            if dynamic_target_path != static_target_path:
                assert static_src_path.endswith('.a')
                assert dynamic_src_path.endswith('.so')
                self.ninja_build(dynamic_target_path, 'copy',
                                 inputs=dynamic_src_path)
                path = dynamic_target_path
            self._add_target_file('so', path)

        return (static_src_path, static_target_path,
                dynamic_src_path, dynamic_target_path)

    def _get_ninja_rule_from_suffix(self, src):
        """
        Return cxx for C++ source files with suffix as .cc/.cpp/.cxx,
        return cc otherwise for C, Assembler, etc.
        """
        for suffix in ('.cc', '.cpp', '.cxx'):
            if src.endswith(suffix):
                return 'cxx'
        return 'cc'

    def _setup_ninja_cc_vars(self, vars):
        """Set up warning, compile options and include directories for cc build. """
        if self.data.get('warning') != 'yes':
            vars['c_warnings'] = ''
            vars['cxx_warnings'] = ''
        cppflags, includes = self._get_cc_flags()
        if cppflags:
            vars['cppflags'] = ' '.join(cppflags)
        if includes:
            vars['includes'] = ' '.join(['-I%s' % inc for inc in includes])

    def _generate_ninja_link_flags(self):
        """Generate linker flags for cc link. """
        ldflags = []
        extra_linkflags = self.data.get('extra_linkflags')
        if extra_linkflags:
            ldflags = extra_linkflags
        if 'allow_undefined' in self.data:
            allow_undefined = self.data['allow_undefined']
            if not allow_undefined:
                ldflags.append('-Xlinker --no-undefined')
        return ldflags

    def _generate_link_all_symbols_link_flags(self, libs):
        """Generate link flags for libraries which should be linked with all symbols. """
        if libs:
            return ['-Wl,--whole-archive'] + libs + ['-Wl,--no-whole-archive']
        return []

    def _ninja_dynamic_dependencies(self):
        """
        Find dynamic dependencies for ninja build,
        including system libraries and user libraries.
        """
        targets = self.blade.get_build_targets()
        sys_libs, usr_libs = [], []
        for key in self.expanded_deps:
            dep = targets[key]
            if dep.type == 'cc_library' and not dep.srcs:
                continue
            if key[0] == '#':
                sys_libs.append(key[1])
            else:
                lib = dep._get_target_file('so')
                if lib:
                    usr_libs.append(lib)
        return sys_libs, usr_libs

    def _ninja_static_dependencies(self):
        """
        Find static dependencies for ninja build, including system libraries
        and user libraries.
        User libraries consist of normal libraries and libraries which should
        be linked all symbols within them using whole-archive option of gnu linker.
        """
        targets = self.blade.get_build_targets()
        sys_libs, usr_libs, link_all_symbols_libs = [], [], []
        for key in self.expanded_deps:
            dep = targets[key]
            if dep.type == 'cc_library' and not dep.srcs:
                continue
            if key[0] == '#':
                sys_libs.append(key[1])
            else:
                lib = dep._get_target_file('a')
                if lib:
                    if dep.data.get('link_all_symbols'):
                        link_all_symbols_libs.append(lib)
                    else:
                        usr_libs.append(lib)
        return sys_libs, usr_libs, link_all_symbols_libs

    def _cc_hdrs_ninja(self, hdrs_inclusion_srcs, vars):
        pass

    def _cc_objects_generated_header_files_dependency(self):
        """Return a stamp which depends on targets which generate header files. """
        deps = self._generated_header_files_dependencies()
        if not deps:
            return None
        stamp = self._target_file_path('%s__stamp__' % self.name)
        inputs = []
        for dep in deps:
            dep_output = dep._get_target_file()
            if dep_output:
                inputs.append(dep_output)
        self.ninja_build(stamp, 'stamp', inputs=inputs)
        return stamp

    def _securecc_object_ninja(self, obj, src, implicit_deps, vars):
        assert obj.endswith('.o')
        pos = obj.rfind('.', 0, -2)
        assert pos != -1
        secure_obj = '%s__securecc__.cc.o' % obj[:pos]
        path = self._source_file_path(src)
        if not os.path.exists(path):
            path = self._target_file_path(src)
            self._securecc_object_rules('', path, False)
        self.ninja_build(secure_obj, 'securecccompile', inputs=path,
                         implicit_deps=implicit_deps,
                         variables=vars)
        self.ninja_build(obj, 'securecc', inputs=secure_obj)

    def _cc_objects_ninja(self, sources=None, generated=False, generated_headers=None):
        """Generate cc objects build rules in ninja. """
        vars = {}
        self._setup_ninja_cc_vars(vars)
        implicit_deps = []
        stamp = self._cc_objects_generated_header_files_dependency()
        if stamp:
            implicit_deps.append(stamp)
        secure = self.data.get('secure')
        if secure:
            implicit_deps.append('__securecc_phony__')

        objs_dir = self._target_file_path() + '.objs'
        objs, hdrs_inclusion_srcs = [], []
        if sources:
            srcs = sources
        else:
            srcs = self.srcs
        for src in srcs:
            obj = '%s.o' % os.path.join(objs_dir, src)
            if secure:
                self._securecc_object_ninja(obj, src, implicit_deps, vars)
            else:
                rule = self._get_ninja_rule_from_suffix(src)
                if generated:
                    input = self._target_file_path(src)
                    if generated_headers and len(generated_headers) > 1:
                        implicit_deps += generated_headers
                else:
                    path = self._source_file_path(src)
                    if os.path.exists(path):
                        input = path
                        hdrs_inclusion_srcs.append((path, obj, rule))
                    else:
                        input = self._target_file_path(src)
                self.ninja_build(obj, rule, inputs=input,
                                 implicit_deps=implicit_deps,
                                 variables=vars)
            objs.append(obj)

        self.data['objs'] = objs
        if (config.get_item('cc_config', 'header_inclusion_dependencies') and
            hdrs_inclusion_srcs):
            self._cc_hdrs_ninja(hdrs_inclusion_srcs, vars)

    def _static_cc_library_ninja(self):
        output = self._target_file_path('lib%s.a' % self.name)
        objs = self.data.get('objs', [])
        self.ninja_build(output, 'ar', inputs=objs)
        self._add_default_target_file('a', output)

    def _dynamic_cc_library_ninja(self):
        output = self._target_file_path('lib%s.so' % self.name)
        ldflags = self._generate_ninja_link_flags()
        sys_libs, usr_libs = self._ninja_dynamic_dependencies()
        extra_ldflags = ['-l%s' % lib for lib in sys_libs]
        self._cc_link_ninja(output, 'solink', deps=usr_libs,
                            ldflags=ldflags, extra_ldflags=extra_ldflags)
        self._add_target_file('so', output)

    def _cc_library_ninja(self):
        self._static_cc_library_ninja()
        if self._need_dynamic_library():
            self._dynamic_cc_library_ninja()

    def _cc_link_ninja(self, output, rule, deps,
                       ldflags=None, extra_ldflags=None,
                       implicit_deps=None, order_only_deps=None):
        objs = self.data.get('objs', [])
        vars = {}
        if ldflags:
            vars['ldflags'] = ' '.join(ldflags)
        if extra_ldflags:
            vars['extra_ldflags'] = ' '.join(extra_ldflags)
        self.ninja_build(output, rule,
                         inputs=objs + deps,
                         implicit_deps=implicit_deps,
                         order_only_deps=order_only_deps,
                         variables=vars)


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
                 prebuilt_libpath_pattern,
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
            if prebuilt_libpath_pattern:
                self.data['prebuilt_libpath_pattern'] = prebuilt_libpath_pattern
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

    def _need_generate_hdrs(self):
        for path in self.blade.get_sources_keyword_list():
            if self.path.startswith(path):
                return False
        return True

    def _extract_cc_hdrs_from_stack(self, path):
        """Extract headers from header stack(.H) generated during preprocessing. """
        hdrs = []
        level_two_hdrs = {}
        with open(path) as f:
            current_hdr = ''
            for line in f.read().splitlines():
                if line.startswith('Multiple include guards may be useful for'):
                    break
                if line.startswith('. '):
                    hdr = line[2:]
                    if hdr[0] == '/':
                        current_hdr = ''
                    else:
                        if hdr.startswith('./'):
                            hdr = hdr[2:]
                        current_hdr = hdr
                        level_two_hdrs[current_hdr] = []
                        hdrs.append(hdr)
                elif line.startswith('.. ') and current_hdr:
                    hdr = line[3:]
                    if hdr[0] != '/':
                        if hdr.startswith('./'):
                            hdr = hdr[2:]
                        level_two_hdrs[current_hdr].append(hdr)

        return hdrs, level_two_hdrs

    def _cc_self_hdr_patterns(self, src):
        """Given src(dir/src/foo.cc), return the possible corresponding header paths.

        Although the header(foo.h) may sometimes be in different directories
        depending on various styles and layouts of different projects,
        Currently tries the following common patterns:

            1. dir/src/foo.h
            2. dir/include/foo.h
            3. dir/inc/foo.h
        """
        path = self._source_file_path(src)
        dir, base = os.path.split(path)
        pos = base.rindex('.')
        hdr_base = '%s.h' % base[:pos]
        self_hdr_patterns = [os.path.join(dir, hdr_base)]
        parent_dir = os.path.dirname(dir)
        if parent_dir:
            self_hdr_patterns.append(os.path.join(parent_dir, 'include', hdr_base))
            self_hdr_patterns.append(os.path.join(parent_dir, 'inc', hdr_base))
        return self_hdr_patterns

    def _extract_cc_hdrs(self, src):
        """Extract headers included by .cc/.h directly. """
        objs_dir = self._target_file_path() + '.objs'
        path = '%s.o.H' % os.path.join(objs_dir, src)
        if not os.path.exists(path):
            return []
        hdrs, level_two_hdrs = self._extract_cc_hdrs_from_stack(path)
        self_hdr_patterns = self._cc_self_hdr_patterns(src)
        self_hdr_index = -1
        for i, hdr in enumerate(hdrs):
            if hdr in self_hdr_patterns:
                self_hdr_index = i
                break

        if self_hdr_index == -1:
            return hdrs
        else:
            return hdrs[:self_hdr_index] + level_two_hdrs[hdr] + hdrs[self_hdr_index + 1:]

    @staticmethod
    def _parse_hdr_level(line):
        pos = line.find(' ')
        if pos == -1:
            return -1, ''
        level, hdr = line[:pos].count('.'), line[pos + 1:]
        if hdr.startswith('./'):
            hdr = hdr[2:]
        return level, hdr

    def _extract_generated_hdrs_inclusion_stacks(self, src, history):
        """Extract generated headers and inclusion stacks for each one of them.

        Given the following inclusions found in the app/example/foo.cc.o.H:

            . ./app/example/foo.h
            .. build64_release/app/example/proto/foo.pb.h
            ... build64_release/common/rpc/rpc_service.pb.h
            . build64_release/app/example/proto/bar.pb.h
            . ./common/rpc/rpc_client.h
            .. build64_release/common/rpc/rpc_options.pb.h

        Return a list with each item being a list representing where the
        generated header is included from in the current translation unit.

        Note that ONLY the first generated header is tracked while other
        headers included from the generated header directly or indirectly
        are ignored since that part of inclusion is ensured by imports of
        proto_library.

        As shown in the example above, it returns:

            [
                ['app/example/foo.h', 'build64_release/app/example/proto/foo.pb.h'],
                ['build64_release/app/example/proto/bar.pb.h'],
                ['common/rpc/rpc_client.h', 'build64_release/common/rpc/rpc_options.pb.h'],
            ]
        """
        objs_dir = self._target_file_path() + '.objs'
        path = '%s.o.H' % os.path.join(objs_dir, src)
        if (not os.path.exists(path) or
            (path in history and int(os.path.getmtime(path)) == history[path])):
            return '', []

        build_dir = self.build_path
        stacks, hdrs_stack = [], []

        def _process_hdr(level, hdr, current_level):
            if hdr.startswith('/'):
                skip_level = level
            elif hdr.startswith(build_dir):
                skip_level = level
                stacks.append(hdrs_stack + [hdr])
            else:
                current_level = level
                hdrs_stack.append(hdr)
                skip_level = -1
            return current_level, skip_level

        current_level = 0
        skip_level = -1
        with open(path) as f:
            for line in f.read().splitlines():
                if line.startswith('Multiple include guards may be useful for'):
                    break
                level, hdr = self._parse_hdr_level(line)
                if level == -1:
                    console.log('%s: Unrecognized line %s' % (self.fullname, line))
                    break
                if level > current_level:
                    if skip_level != -1 and level > skip_level:
                        continue
                    assert level == current_level + 1
                    current_level, skip_level = _process_hdr(level, hdr, current_level)
                else:
                    while current_level >= level:
                        current_level -= 1
                        hdrs_stack.pop()
                    current_level, skip_level = _process_hdr(level, hdr, current_level)

        return path, stacks

    def verify_header_inclusion_dependencies(self, history):
        if not self._need_generate_hdrs():
            return True

        build_targets = self.blade.get_build_targets()
        # TODO(wentingli): Check regular headers as well
        declared_hdrs = set()
        for key in self.expanded_deps:
            dep = build_targets[key]
            declared_hdrs.update(dep.data.get('generated_hdrs', []))

        preprocess_paths, failed_preprocess_paths = set(), set()
        for src in self.srcs:
            source = self._source_file_path(src)
            path, stacks = self._extract_generated_hdrs_inclusion_stacks(src, history)
            if not path:
                continue
            preprocess_paths.add(path)
            for stack in stacks:
                generated_hdr = stack[-1]
                if generated_hdr not in declared_hdrs:
                    failed_preprocess_paths.add(path)
                    stack.pop()
                    if not stack:
                        msg = ['In file included from %s' % source]
                    else:
                        stack.reverse()
                        msg = ['In file included from %s' % stack[0]]
                        prefix = '                 from %s'
                        msg += [prefix % h for h in stack[1:]]
                        msg.append(prefix % source)
                    console.info('\n%s' % '\n'.join(msg))
                    console.error('%s: Missing dependency declaration in BUILD for %s.' % (
                                  self.fullname, generated_hdr))

        for preprocess in failed_preprocess_paths:
            if preprocess in history:
                del history[preprocess]
        for preprocess in preprocess_paths - failed_preprocess_paths:
            history[preprocess] = int(os.path.getmtime(preprocess))
        return not failed_preprocess_paths

    def _cc_hdrs_ninja(self, hdrs_inclusion_srcs, vars):
        if not self._need_generate_hdrs():
            return

        for key in ('c_warnings', 'cxx_warnings'):
            if key in vars:
                del vars[key]
        for src, obj, rule in hdrs_inclusion_srcs:
            output = '%s.H' % obj
            rule = '%shdrs' % rule
            self.ninja_build(output, rule, inputs=src,
                             implicit_deps=[obj],
                             variables=vars)

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

    def ninja_rules(self):
        """Generate ninja build rules for cc object/library. """
        self._check_deprecated_deps()
        if self.type == 'prebuilt_cc_library':
            self._prebuilt_cc_library()
        elif self.srcs:
            self._cc_objects_ninja()
            self._cc_library_ninja()


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
               prebuilt_libpath_pattern=None,
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
                       prebuilt_libpath_pattern,
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

        # add extra link library
        link_libs = var_to_list(config.get_item('cc_binary_config', 'extra_libs'))
        self._add_hardcode_library(link_libs)

    def _allow_duplicate_source(self):
        return True

    def _expand_deps_generation(self):
        if self.data.get('dynamic_link'):
            build_targets = self.blade.get_build_targets()
            for dep in self.expanded_deps:
                build_targets[dep].data['build_dynamic'] = True

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

    def _generate_cc_binary_link_flags(self, dynamic_link):
        ldflags = []
        if (not dynamic_link and
            self.blade.get_scons_platform().get_gcc_version() > '4.5'):
            ldflags += ['-static-libgcc', '-static-libstdc++']
        if self.data.get('export_dynamic'):
            ldflags.append('-rdynamic')
        ldflags += self._generate_ninja_link_flags()
        for rpath_link in self._get_rpath_links():
            ldflags.append('-Wl,--rpath-link=%s' % rpath_link)
        return ldflags

    def _cc_binary_ninja(self, dynamic_link):
        ldflags = self._generate_cc_binary_link_flags(dynamic_link)
        implicit_deps = []
        if dynamic_link:
            sys_libs, usr_libs = self._ninja_dynamic_dependencies()
        else:
            sys_libs, usr_libs, link_all_symbols_libs = self._ninja_static_dependencies()
            if link_all_symbols_libs:
                ldflags += self._generate_link_all_symbols_link_flags(link_all_symbols_libs)
                implicit_deps = link_all_symbols_libs

        extra_ldflags, order_only_deps = [], []
        if self.data['embed_version']:
            scm = os.path.join(self.build_path, 'scm.cc.o')
            extra_ldflags.append(scm)
            order_only_deps.append(scm)
        extra_ldflags += ['-l%s' % lib for lib in sys_libs]
        output = self._target_file_path()
        self._cc_link_ninja(output, 'link', deps=usr_libs,
                            ldflags=ldflags, extra_ldflags=extra_ldflags,
                            implicit_deps=implicit_deps,
                            order_only_deps=order_only_deps)
        self._add_default_target_file('bin', output)

    def ninja_rules(self):
        """Generate ninja build rules for cc binary/test. """
        self._check_deprecated_deps()
        self._cc_objects_ninja()
        self._cc_binary_ninja(self.data['dynamic_link'])


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
    cc_config = config.get_section('cc_config')
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

    def ninja_rules(self):
        """Generate ninja build rules for cc plugin. """
        self._check_deprecated_deps()
        self._cc_objects_ninja()
        ldflags = self._generate_ninja_link_flags()
        implicit_deps = []
        sys_libs, usr_libs, link_all_symbols_libs = self._ninja_static_dependencies()
        if link_all_symbols_libs:
            ldflags += self._generate_link_all_symbols_link_flags(link_all_symbols_libs)
            implicit_deps = link_all_symbols_libs

        extra_ldflags = ['-l%s' % lib for lib in sys_libs]
        output = self._target_file_path('lib%s.so' % self.name)
        if self.srcs or self.expanded_deps:
            self._cc_link_ninja(output, 'solink', deps=usr_libs,
                                ldflags=ldflags, extra_ldflags=extra_ldflags,
                                implicit_deps=implicit_deps)
            self._add_default_target_file('so', output)


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
        cc_test_config = config.get_section('cc_test_config')
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
