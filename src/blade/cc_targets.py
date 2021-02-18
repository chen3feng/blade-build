# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011

# pylint: disable=too-many-lines

"""
This is the cc_target module which is the super class
of all of the cc targets, like cc_library, cc_binary.
"""

from __future__ import absolute_import
from __future__ import print_function

import os
import subprocess
from string import Template

from blade import build_manager
from blade import config
from blade import console
from blade import build_rules
from blade.constants import HEAP_CHECK_VALUES
from blade.target import Target
from blade.util import (
    mkdir_p,
    path_under_dir,
    pickle,
    stable_unique,
    var_to_list,
    var_to_list_or_none)


# See https://gcc.gnu.org/onlinedocs/gcc/Overall-Options.html#Overall-Options
_SOURCE_FILE_EXTS = {'c', 'cc', 'cp', 'cxx', 'cpp', 'CPP', 'c++', 'C', 's', 'S', 'asm'}
_HEADER_FILE_EXTS = {'h', 'hh', 'H', 'hp', 'hpp', 'hxx', 'HPP', 'h++', 'inc', 'inl', 'tcc'}


def is_header_file(filename):
    """Whether a file is a C/C++ header file."""
    _, ext = os.path.splitext(filename)
    ext = ext[1:]  # Remove leading '.'
    # See https://gcc.gnu.org/onlinedocs/gcc/Overall-Options.html
    return ext in _HEADER_FILE_EXTS


# A dict[hdr, set(target)]
# For a header file, which targets declared it.
_hdr_targets_map = {}

# A dict[inc, set(target)]
# For a include dir, which targets declared it.
_hdr_dir_targets_map = {}


def declare_hdrs(target, hdrs):
    """Declare hdr to lib relationships

    Args:
        target: the target which owns the hdrs
        hdrs:list, the full path (based in workspace troot) of hdrs
    """
    for hdr in hdrs:
        assert not hdr.startswith(target.build_dir)
        hdr = target._source_file_path(hdr)
        if hdr not in _hdr_targets_map:
            _hdr_targets_map[hdr] = set()
        _hdr_targets_map[hdr].add(target.key)


def declare_hdr_dir(target, inc):
    """Declare a inc:lib relationship

    Args:
        target: the target which owns the include dir
        inc:str, the full path (based in workspace troot) of include dir
    """
    assert not inc.startswith(target.build_dir), inc
    inc = target._source_file_path(inc)
    if inc not in _hdr_dir_targets_map:
        _hdr_dir_targets_map[inc] = set()
    _hdr_dir_targets_map[inc].add(target.key)


# dict(hdr, set(targets))
_private_hdrs_target_map = {}


def declare_private_hdrs(target, hdrs):
    """Declare private header files of a cc target."""
    for h in hdrs:
        hdr = target._source_file_path(h)
        if hdr not in _private_hdrs_target_map:
            _private_hdrs_target_map[hdr] = set()
        _private_hdrs_target_map[hdr].add(target.key)


def inclusion_declaration():
    return {
        'public_hdrs': _hdr_targets_map,
        'public_incs': _hdr_dir_targets_map,
        'private_hdrs': _private_hdrs_target_map,
        'allowed_undeclared_hdrs': config.get_item('cc_config', 'allowed_undeclared_hdrs')
    }


def _transitive_declared_generated_includes(target):
    """Collect header/include declarations."""
    attr_key = 'transitive_generated_inludes'
    if attr_key in target.data:
        return target.data[attr_key]

    declared_hdrs = set()
    declared_incs = set()
    build_targets = target.blade.get_build_targets()
    for dkey in target.deps:
        dep = build_targets[dkey]
        for hdr in dep.attr.get('generated_hdrs', []):
            declared_incs.add(target._remove_build_dir_prefix(hdr))
        for inc in dep.attr.get('generated_incs', []):
            declared_incs.add(target._remove_build_dir_prefix(inc))
        dep_hdrs, dep_incs = _transitive_declared_generated_includes(dep)
        declared_incs.update(dep_hdrs)
        declared_incs.update(dep_incs)
    result = declared_hdrs, declared_incs
    target.data[attr_key] = result
    return result


class CcTarget(Target):
    """
    This class is derived from Target and it is the base class
    of cc_library, cc_binary etc.
    """

    def __init__(self,
                 name,
                 type,
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
                 kwargs,
                 src_exts=_SOURCE_FILE_EXTS):
        """Init method.

        Init the cc target.

        """
        # pylint: disable=too-many-locals
        srcs = var_to_list(srcs)
        private_hdrs = [src for src in srcs if is_header_file(src)]
        srcs = [src for src in srcs if not is_header_file(src)]
        deps = var_to_list(deps)

        super(CcTarget, self).__init__(
                name=name,
                type=type,
                srcs=srcs,
                src_exts=src_exts,
                deps=deps,
                visibility=visibility,
                kwargs=kwargs)

        self._check_defs(defs)
        self._check_incorrect_no_warning(warning)

        self.attr['warning'] = warning
        self.attr['private_hdrs'] = private_hdrs
        self.attr['defs'] = var_to_list(defs)
        self.attr['incs'] = self._incs_to_fullpath(incs)
        self.attr['export_incs'] = self._incs_to_fullpath(export_incs)
        self.attr['optimize'] = var_to_list_or_none(optimize)
        self.attr['extra_cppflags'] = var_to_list(extra_cppflags)
        self.attr['extra_linkflags'] = var_to_list(extra_linkflags)
        # TODO(chen3feng): Move to CcLibrary
        options = self.blade.get_options()
        self.attr['generate_dynamic'] = (getattr(options, 'generate_dynamic', False) or
                                         config.get_item('cc_library_config', 'generate_dynamic'))
        self.attr['expanded_srcs'] = self._expand_sources(srcs)
        self.attr['expanded_hdrs'] = self._expand_sources(private_hdrs)
        declare_private_hdrs(self, private_hdrs)

    def _expand_sources(self, files):
        """Expand files to [(path, full_path)]."""
        result = []
        for src in files:
            full_path = self._source_file_path(src)
            if not os.path.exists(full_path):
                # Assume generated
                full_path = self._target_file_path(src)
            result.append((src, full_path))
        return result

    def _incs_to_fullpath(self, incs):
        """Expand incs to full path"""
        result = []
        for inc in var_to_list(incs):
            if inc.startswith('//'):  # Full path
                result.append(inc[2:])
            else:
                result.append(os.path.normpath(os.path.join(self.path, inc)))
        return result

    def _set_hdrs(self, hdrs):
        """Set The "hdrs" attribute properly"""
        if hdrs is None:
            suppress = config.get_item('cc_library_config', 'hdrs_missing_suppress')
            if self.key not in suppress:
                severity = config.get_item('cc_library_config', 'hdrs_missing_severity')
                getattr(self, severity)(
                        'Missing "hdrs" declaration. The public header files should be declared '
                        'explicitly, if no public header file, set "hdrs" to empty (hdrs = [])')
        if not hdrs:
            return
        hdrs = var_to_list(hdrs)
        self._check_sources('header', hdrs, _HEADER_FILE_EXTS)
        declare_hdrs(self, hdrs)
        self.attr['expanded_hdrs'] += self._expand_sources(hdrs)

    def _check_deprecated_deps(self):
        """Check whether it depends upon a deprecated library."""
        for key in self.deps:
            dep = self.target_database.get(key)
            if dep and dep.attr.get('deprecated'):
                replaced_deps = dep.deps
                if replaced_deps:
                    self.warning('//%s is deprecated, please depends on //%s' % (
                        dep, replaced_deps[0]))

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

    def _check_defs(self, defs):
        """_check_defs.
        It will warn if user defines c++ keyword in defs list.
        """
        for macro in defs:
            pos = macro.find('=')
            if pos != -1:
                macro = macro[0:pos]
            if macro in CcTarget.__cxx_keyword_list:
                self.warning('DO NOT define c++ keyword "%s" as a macro' % macro)

    def _check_incorrect_no_warning(self, warning):
        """check if warning=no is correctly used or not."""
        srcs = self.srcs
        if not srcs or warning != 'no':
            return

        keywords_list = self.blade.get_sources_keyword_list()
        for keyword in keywords_list:
            if keyword in self.path:
                return

        illegal_path_list = []
        for keyword in keywords_list:
            illegal_path_list += [s for s in srcs if keyword not in s]

        if illegal_path_list:
            self.warning(""""warning='no'" should only be used for thirdparty libraries.""")

    def _check_binary_link_only(self):
        """Check whether a `binary_link_only` library is used correctly"""
        if self.attr.get('binary_link_only'):
            # A binary_link_only library is always allowed to depends on another binary_link_only
            # library
            return
        for dkey in self.deps:
            dep = self.target_database[dkey]
            if dep.attr.get('binary_link_only'):
                self.error('"%s" is a binary_link_only library, can only be a dependent of '
                           'executable target or another binary_link_only library' % dep.fullname)

    def _get_optimize_flags(self):
        """Get optimize flags according to build mode and attributes"""
        optimize = self.attr.get('optimize')
        if optimize is not None:
            optimize = ' '.join(optimize)
        if self.attr.get('always_optimize'):
            return optimize if optimize is not None else '$optimize_flags'
        if self.blade.get_options().profile == 'release':
            return optimize
        return None

    def _get_cc_flags(self):
        """_get_cc_flags.

        Return the cpp flags according to the BUILD file and other configs.

        """
        cpp_flags = []

        # Defs
        defs = self.attr.get('defs', [])
        cpp_flags += [('-D' + macro) for macro in defs]
        cpp_flags += self.attr.get('extra_cppflags', [])

        # Incs
        incs = self._get_incs_list()

        return (cpp_flags, incs)

    def _get_as_flags(self):
        """Return as flags according to the build architecture."""
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
            inc_list += target.attr.get('export_incs', [])
        return inc_list

    def _get_incs_list(self):
        """Get all incs includes export_incs of all depends."""
        incs = self.attr.get('incs', []) + self.attr.get('export_incs', [])
        incs += self._export_incs_list()
        # Remove duplicate items in incs list and keep the order
        incs = stable_unique(incs)
        return incs

    def _get_rule_from_suffix(self, src):
        """
        Return cxx for C++ source files with suffix as .cc/.cpp/.cxx,
        return cc otherwise for C, Assembler, etc.
        """
        for suffix in ('.cc', '.cpp', '.cxx'):
            if src.endswith(suffix):
                return 'cxx'
        return 'cc'

    def _get_cc_vars(self):
        """Get warning, compile options and include directories for cc build."""
        vars = {}
        # Warnings
        if self.attr.get('warning') != 'yes':
            vars['c_warnings'] = '-w'
            vars['cxx_warnings'] = '-w'

        cppflags, includes = self._get_cc_flags()
        if cppflags:
            vars['cppflags'] = ' '.join(cppflags)
        if includes:
            vars['includes'] = ' '.join(['-I%s' % inc for inc in includes])

        optimize = self._get_optimize_flags()
        if optimize is not None:
            vars['optimize'] = optimize

        return vars

    def _generate_link_flags(self):
        """Generate linker flags for cc link."""
        ldflags = []
        extra_linkflags = self.attr.get('extra_linkflags')
        if extra_linkflags:
            ldflags = extra_linkflags
        if 'allow_undefined' in self.attr:
            allow_undefined = self.attr['allow_undefined']
            if not allow_undefined:
                ldflags.append('-Xlinker --no-undefined')
        return ldflags

    def _generate_link_all_symbols_link_flags(self, libs):
        """Generate link flags for libraries which should be linked with all symbols."""
        if libs:
            return ['-Wl,--whole-archive'] + libs + ['-Wl,--no-whole-archive']
        return []

    def _dynamic_dependencies(self):
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
            if dep.path == '#':
                sys_libs.append(dep.name)
            else:
                lib = dep._get_target_file('so')
                if lib:
                    usr_libs.append(lib)
        return sys_libs, usr_libs

    def _static_dependencies(self):
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
            if dep.path == '#':
                sys_libs.append(dep.name)
            else:
                lib = dep._get_target_file('a')
                if lib:
                    if dep.attr.get('link_all_symbols'):
                        link_all_symbols_libs.append(lib)
                    else:
                        usr_libs.append(lib)
        return sys_libs, usr_libs, link_all_symbols_libs

    def _cc_compile_deps(self):
        """Return a stamp which depends on targets which generate header files."""
        deps = self._collect_cc_compile_deps()
        if len(deps) > 1:
            # If there are more deps, we generate a phony stamp as an alias # to simplify
            # the generated ninja file. For more details, see:
            # https://ninja-build.org/manual.html#_the_literal_phony_literal_rule
            stamp = self._target_file_path(self.name + '__compile_deps__')
            self.generate_build('phony', stamp, inputs=deps, clean=[])
            deps = [stamp]
        return deps

    def _collect_cc_compile_deps(self):
        """Calculate the dependencies for source file compiling.

        If a dependency will generate c/c++ header files, we must depends on it during the
        compiling stage, otherwise, the 'Missing header file' error will occurs.

        Only the generated header files need to be considered. Because the normal header files
        have been covered by the dependency file generated by gcc (the `.d` file) automatically.
        """
        result = set()
        for key in self.expanded_deps:
            dep = self.target_database[key]
            generated_hdrs = dep.attr.get('generated_hdrs')
            if generated_hdrs:
                # NOTE: Here is an optimization: If we know the detaild generated header files,
                # depends on them explicitly rather than depending on the whole target improves
                # the parallelism.
                # For example, if we depends on a proto_library, once its `pb.h` is generated,
                # our source file can be compiled without waiting for its library beeing generated.
                result.update(generated_hdrs)
            elif 'generated_incs' in dep.attr:
                # We know that this target generate header files, but we don't know the details,
                # so we have to depends on its final target file.
                target_file = dep._get_target_file()
                if target_file:
                    result.add(target_file)
            # For any other cases, depends on nothing for compiling.

        return list(result)

    def _cc_objects(self, expanded_srcs, generated_headers=None):
        """Generate cc objects build rules in ninja."""
        vars = self._get_cc_vars()
        # Use `order_only_deps` for generated header files,
        # See https://ninja-build.org/manual.html#ref_dependencies for details.
        order_only_deps = []
        order_only_deps += self._cc_compile_deps()
        if generated_headers and len(generated_headers) > 1:
            order_only_deps += generated_headers
        objs_dir = self._target_file_path(self.name + '.objs')
        objs = []
        for src, full_src in expanded_srcs:
            obj = os.path.join(objs_dir, src + '.o')
            rule = self._get_rule_from_suffix(src)
            self.generate_build(rule, obj, inputs=full_src,
                                order_only_deps=order_only_deps,
                                variables=vars, clean=[])
            objs.append(obj)

        if 'inclusion_check_info_file' in self.data:
            self._generate_inclusion_check(objs_dir, objs, vars, order_only_deps)
        self._remove_on_clean(objs_dir)
        return objs

    def _generated_cc_objects(self, sources, generated_headers=None):
        """Compile generated cc sources"""
        expanded_sources = [(src, self._target_file_path(src)) for src in sources]
        return self._cc_objects(expanded_sources, generated_headers)

    def _generate_inclusion_check(self, objs_dir, objs, vars, order_only_deps):
        implicit_deps = objs[:]
        # Generate inclusion stack file for header files.
        # The source file does not need to generate this file separately, because it is generated
        # at the same time during compilation.
        for hdr, full_hdr in self.attr['expanded_hdrs']:
            if path_under_dir(full_hdr, self.build_dir):  # Don't check generated header files
                continue
            output = os.path.join(objs_dir, hdr + '.H')
            implicit_deps.append(output)
            self.generate_build('cxxhdrs', output, inputs=full_hdr,
                                order_only_deps=order_only_deps, variables=vars, clean=[])

        check_info_file = self.data['inclusion_check_info_file']
        check_result_file = check_info_file + '.result'
        self.generate_build('ccincchk', outputs=check_result_file, inputs=check_info_file,
                            implicit_deps=implicit_deps)

    def _static_cc_library(self, objs):
        output = self._target_file_path('lib%s.a' % self.name)
        self.generate_build('ar', output, inputs=objs,
                            implicit_deps=self.data.get('inclusion_check_result_file'))
        self._add_default_target_file('a', output)

    def _dynamic_cc_library(self, objs):
        output = self._target_file_path('lib%s.so' % self.name)
        ldflags = self._generate_link_flags()
        sys_libs, usr_libs = self._dynamic_dependencies()
        extra_ldflags = ['-l%s' % lib for lib in sys_libs]
        self._cc_link(output, 'solink', objs=objs, deps=usr_libs,
                      ldflags=ldflags, extra_ldflags=extra_ldflags)
        self._add_target_file('so', output)

    def _soname_of(self, so_path):
        """Get the `soname` of a shared library."""
        soname = None
        try:
            output = subprocess.check_output('objdump -p %s' % so_path, shell=True)
            for line in output.splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[0] == 'SONAME':
                    soname = parts[1]
                    break
        except subprocess.CalledProcessError:
            pass
        return soname

    def _cc_library(self, objs):
        self._static_cc_library(objs)
        if self.attr.get('generate_dynamic'):
            self._dynamic_cc_library(objs)

    def _cc_link(self, output, rule, objs, deps,
                 ldflags=None, extra_ldflags=None,
                 implicit_deps=None, order_only_deps=None):
        vars = {}
        if ldflags:
            vars['ldflags'] = ' '.join(ldflags)
        if extra_ldflags:
            vars['extra_ldflags'] = ' '.join(extra_ldflags)
        incchk = self.data.get('inclusion_check_result_file')
        if incchk:
            if implicit_deps is None:
                implicit_deps = [incchk]
            else:
                implicit_deps.append(incchk)
        self.generate_build(rule, output,
                            inputs=objs + deps,
                            implicit_deps=implicit_deps,
                            order_only_deps=order_only_deps,
                            variables=vars)

    def _cleanup_target_files(self):
        """Clean up built result files"""
        for f in self._get_target_files():
            try:
                os.remove(f)
                console.debug('Remove "%s" due to hdr dep missing' % f)
            except OSError:
                pass

    def _write_inclusion_check_info(self):
        """Write a files contains necessary formation for inclusion checking."""
        verify_suppress = config.get_item('cc_config', 'hdr_dep_missing_suppress')
        declared_hdrs, declared_incs = self._collect_declared_headers()
        declared_genhdrs, declared_genincs = _transitive_declared_generated_includes(self)
        target_check_info = {
            'type': self.type,
            'name': self.name,
            'path': self.path,
            'key': self.key,
            'deps': self.deps,
            'build_dir': self.build_dir,
            'source_location': self.source_location,
            'expanded_srcs': self.attr['expanded_srcs'],
            'expanded_hdrs': self.attr['expanded_hdrs'],
            'declared_hdrs': declared_hdrs,
            'declared_incs': declared_incs,
            'declared_genhdrs': declared_genhdrs,
            'declared_genincs': declared_genincs,
            'severity': config.get_item('cc_config', 'hdr_dep_missing_severity'),
            'suppress': verify_suppress.get(self.key, {}),
        }
        content = pickle.dumps(target_check_info)
        filename = self._target_file_path(self.name + '.incchk')
        self.data['inclusion_check_info_file'] = filename

        # Only update file when content changes to avoid unnecessary recheck
        if os.path.exists(filename):
            with open(filename, 'rb') as f:
                if f.read() == content:
                    return
        else:
            mkdir_p(self._target_dir())
        with open(filename, 'wb') as f:
            f.write(content)

    def _collect_declared_headers(self):
        """Collect direct headers declarations."""
        declared_hdrs = set(full_hdr for hdr, full_hdr in self.attr['expanded_hdrs'])
        declared_incs = set(self.attr.get('generated_incs', []))

        build_targets = self.blade.get_build_targets()
        for key in self.deps:
            dep = build_targets[key]
            for hdr, full_hdr in dep.attr.get('expanded_hdrs', []):
                declared_hdrs.add(self._remove_build_dir_prefix(full_hdr))
            for inc in dep.attr.get('generated_incs', []):
                declared_incs.add(self._remove_build_dir_prefix(inc))
        return declared_hdrs, declared_incs


class CcLibrary(CcTarget):
    """
    This class is derived from CcTarget and it generates the library
    rules including dynamic library rules according to user option.
    """

    def __init__(self,
                 name,
                 srcs,
                 hdrs,
                 deps,
                 visibility,
                 warning,
                 defs,
                 incs,
                 export_incs,
                 optimize,
                 always_optimize,
                 link_all_symbols,
                 binary_link_only,
                 deprecated,
                 extra_cppflags,
                 extra_linkflags,
                 allow_undefined,
                 secure,
                 kwargs):
        """Init method.

        Init the cc library.

        """
        # pylint: disable=too-many-locals
        super(CcLibrary, self).__init__(
                name=name,
                type='cc_library',
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                warning=warning,
                defs=defs,
                incs=incs,
                export_incs=export_incs,
                optimize=optimize,
                extra_cppflags=extra_cppflags,
                extra_linkflags=extra_linkflags,
                kwargs=kwargs)
        self.attr['link_all_symbols'] = link_all_symbols
        self.attr['binary_link_only'] = binary_link_only
        self.attr['always_optimize'] = always_optimize
        self.attr['deprecated'] = deprecated
        self.attr['allow_undefined'] = allow_undefined
        self._set_secure(secure)
        self._set_hdrs(hdrs)

    def before_generate(self):  # override
        """Override"""
        self._write_inclusion_check_info()
        self._check_binary_link_only()


    def _set_secure(self, secure):
        if secure:
            self.attr['secure'] = secure
            for src in self.srcs:
                path = self._source_file_path(src)
                if not os.path.exists(path):
                    # Touch a place holder file for securecc, will be deleted by securecc
                    path = self._target_file_path(src)
                    dirname = os.path.dirname(path)
                    if not os.path.exists(dirname):
                        os.makedirs(dirname)
                    open(path, 'w').close()
                    self._remove_on_clean(path)

    def _securecc_object(self, obj, src, implicit_deps, vars):
        assert obj.endswith('.o')
        pos = obj.rfind('.', 0, -2)
        assert pos != -1
        secure_obj = '%s__securecc__.cc.o' % obj[:pos]
        path = self._source_file_path(src)
        if not os.path.exists(path):
            path = self._target_file_path(src)
        self.generate_build('securecccompile', secure_obj, inputs=path,
                            implicit_deps=implicit_deps, variables=vars, clean=[])
        self.generate_build('securecc', obj, inputs=secure_obj, clean=[])

    def _securecc_objects(self, sources):
        """Generate securecc compile rules in ninja."""
        vars = self._get_cc_vars()
        implicit_deps = self._cc_compile_deps()

        objs_dir = self._target_file_path(self.name + '.objs')
        objs = []
        for src in sources:
            obj = '%s.o' % os.path.join(objs_dir, src)
            self._securecc_object(obj, src, implicit_deps, vars)
            objs.append(obj)
        self._remove_on_clean(objs_dir)
        return objs

    def generate(self):
        """Generate build code for cc object/library."""
        self._check_deprecated_deps()
        if self.srcs:
            if self.attr.get('secure'):
                objs = self._securecc_objects(self.srcs)
            else:
                objs = self._cc_objects(self.attr['expanded_srcs'])
            self._cc_library(objs)


class PrebuiltCcLibrary(CcTarget):
    """
    This class describs a prebuilt cc_library target
    """

    def __init__(self,
                 name,
                 deps,
                 hdrs,
                 visibility,
                 export_incs,
                 libpath_pattern,
                 link_all_symbols,
                 binary_link_only,
                 deprecated,
                 kwargs):
        """Init method."""
        # pylint: disable=too-many-locals
        super(PrebuiltCcLibrary, self).__init__(
                name=name,
                type='prebuilt_cc_library',
                srcs=[],
                deps=deps,
                visibility=visibility,
                warning='no',
                defs=[],
                incs=[],
                export_incs=export_incs,
                optimize=None,
                extra_cppflags=[],
                extra_linkflags=[],
                kwargs=kwargs)
        self.attr['libpath_pattern'] = libpath_pattern
        self.attr['link_all_symbols'] = link_all_symbols
        self.attr['binary_link_only'] = binary_link_only
        self.attr['deprecated'] = deprecated
        self._set_hdrs(hdrs)
        self._setup()

    def _setup(self):
        # There are 3 cases for prebuilt library as below:
        #   1. Only static library(.a) exists
        #   2. Only dynamic library(.so) exists
        #   3. Both static and dynamic libraries exist
        # If there is only one kind of library, we have to use it any way.
        # But in the third case, we use static library for static linking,
        # and use dynamic library for dynamic linking.
        static_source = self._library_source_path('a')
        dynamic_source = self._library_source_path('so')
        has_static = os.path.exists(static_source)
        has_dynamic = os.path.exists(dynamic_source)

        if not has_static and not has_dynamic:
            self.error('Can not find either %s or %s' % (static_source, dynamic_source))
            return

        if has_static:
            self.attr['static_source'] = static_source
            self._add_target_file('a', static_source)
            if not has_dynamic:
                # Using static library for dynamic linking
                self._add_target_file('so', static_source)

        if has_dynamic:
            dynamic_target = self._target_file_path(os.path.basename(dynamic_source))
            self.attr['dynamic_source'] = dynamic_source
            self.attr['dynamic_target'] = dynamic_target
            self._add_target_file('so', dynamic_target)

            soname = self._soname_of(dynamic_source)
            if soname:
                self.data['soname_and_full_path'] = (soname, dynamic_target)

            if not has_static:
                # Using dynamic library for static linking
                self._add_target_file('a', dynamic_target)

    _default_libpath = None

    def _library_source_path(self, suffix):
        """Library full path in source dir"""
        options = self.blade.get_options()
        bits, arch, profile = options.bits, options.arch, options.profile
        if PrebuiltCcLibrary._default_libpath is None:
            pattern = config.get_item('cc_library_config', 'prebuilt_libpath_pattern')
            PrebuiltCcLibrary._default_libpath = Template(pattern).substitute(
                bits=bits, arch=arch, profile=profile)

        pattern = self.attr.get('libpath_pattern')
        if pattern is None:
            libpath = PrebuiltCcLibrary._default_libpath
        else:
            libpath = Template(pattern).substitute(bits=bits,
                                                   arch=arch,
                                                   profile=profile)

        libpath = os.path.join(self.path, libpath)

        return os.path.join(libpath, 'lib%s.%s' % (self.name, suffix))

    def _is_depended(self):
        """Does this library really be used"""
        build_targets = self.blade.get_build_targets()
        for key in self.expanded_dependents:
            t = build_targets[key]
            if t.type != 'prebuilt_cc_library':
                return True
        return False

    def _rpath_link(self, dynamic):
        path = self._library_source_path('so')
        if os.path.exists(path):
            return os.path.dirname(path)
        return None

    def soname_and_full_path(self):
        """Return soname and full path of the shared library, if any"""
        # When a prebuilt shared library with a 'soname' is linked into a program
        # Its name appears in the program's DT_NEEDED tag without full path.
        # So we need to make a symbolic link let the program find the library.
        return self.data.get('soname_and_full_path')

    def before_generate(self):  # override
        """Override"""
        self._write_inclusion_check_info()
        self._check_binary_link_only()

    def generate(self):
        """Generate build code for cc object/library."""
        self._check_deprecated_deps()
        # We allow a prebuilt cc_library doesn't exist if it is not used.
        # So if this library is not depended by any target, don't generate any
        # rule to avoid runtime error and also avoid unnecessary runtime cost.
        if not self._is_depended():
            return
        dynamic_source = self.attr.get('dynamic_source')
        dynamic_target = self.attr.get('dynamic_target')
        if dynamic_source and dynamic_target:
            self.generate_build('copy', dynamic_target, inputs=dynamic_source)


def prebuilt_cc_library(
        name,
        deps=[],
        visibility=None,
        export_incs=[],
        hdrs=None,
        libpath_pattern=None,
        link_all_symbols=False,
        binary_link_only=False,
        deprecated=False,
        **kwargs):
    """prebuilt_cc_library rule"""
    target = PrebuiltCcLibrary(
            name=name,
            deps=deps,
            visibility=visibility,
            export_incs=export_incs,
            hdrs=hdrs,
            libpath_pattern=libpath_pattern,
            link_all_symbols=link_all_symbols,
            binary_link_only=binary_link_only,
            deprecated=deprecated,
            kwargs=kwargs)
    build_manager.instance.register_target(target)
    return target


def cc_library(
        name,
        srcs=[],
        hdrs=None,
        deps=[],
        visibility=None,
        warning='yes',
        defs=[],
        incs=[],
        export_incs=[],
        optimize=None,
        always_optimize=False,
        pre_build=False,
        prebuilt=False,
        prebuilt_libpath_pattern=None,
        link_all_symbols=False,
        binary_link_only=False,
        deprecated=False,
        extra_cppflags=[],
        extra_linkflags=[],
        allow_undefined=False,
        secure=False,
        **kwargs):
    """cc_library target."""
    # pylint: disable=too-many-locals
    if pre_build or prebuilt:
        target = prebuilt_cc_library(
                name=name,
                hdrs=hdrs,
                deps=deps,
                visibility=visibility,
                export_incs=export_incs,
                libpath_pattern=prebuilt_libpath_pattern,
                link_all_symbols=link_all_symbols,
                binary_link_only=binary_link_only,
                deprecated=deprecated,
                **kwargs)
        # target.warning('"cc_library.prebuilt" is deprecated, please use the standalone '
        #                '"prebuilt_cc_library" rule')
        return
    target = CcLibrary(
            name=name,
            srcs=srcs,
            hdrs=hdrs,
            deps=deps,
            visibility=visibility,
            warning=warning,
            defs=defs,
            incs=incs,
            export_incs=export_incs,
            optimize=optimize,
            always_optimize=always_optimize,
            link_all_symbols=link_all_symbols,
            binary_link_only=binary_link_only,
            deprecated=deprecated,
            extra_cppflags=extra_cppflags,
            extra_linkflags=extra_linkflags,
            allow_undefined=allow_undefined,
            secure=secure,
            kwargs=kwargs)
    build_manager.instance.register_target(target)


class ForeignCcLibrary(CcTarget):
    """
    This class describs a foreign cc_library target
    """

    def __init__(self,
                 name,
                 deps,
                 install_dir,
                 hdrs,
                 hdr_dir,
                 visibility,
                 export_incs,
                 lib_dir,
                 has_dynamic,
                 link_all_symbols,
                 binary_link_only,
                 deprecated,
                 kwargs):
        """Init method."""
        # pylint: disable=too-many-locals
        super(ForeignCcLibrary, self).__init__(
                name=name,
                type='foreign_cc_library',
                srcs=[],
                deps=deps,
                visibility=visibility,
                warning='no',
                defs=[],
                incs=[],
                export_incs=export_incs,
                optimize=None,
                extra_cppflags=[],
                extra_linkflags=[],
                kwargs=kwargs)
        self.attr['install_dir'] = install_dir
        self.attr['link_all_symbols'] = link_all_symbols
        self.attr['deprecated'] = deprecated
        self.attr['lib_dir'] = lib_dir
        self.attr['has_dynamic'] = has_dynamic

        if hdrs:
            hdrs = [os.path.join(install_dir, h) for h in var_to_list(hdrs)]
            declare_hdrs(self, hdrs)
            hdrs = [self._target_file_path(os.path.join(install_dir, h)) for h in hdrs]
            self.attr['generated_hdrs'] = hdrs
        else:
            hdr_dir = os.path.join(install_dir, hdr_dir)
            declare_hdr_dir(self, hdr_dir)
            hdr_dir = self._target_file_path(hdr_dir)
            self.attr['generated_incs'] = [hdr_dir]

    def _library_full_path(self, type):
        """Return full path of the library file with specified type"""
        assert type in ('a', 'so')
        return self._target_file_path(os.path.join(self.attr['install_dir'], self.attr['lib_dir'],
                                                   'lib%s.%s' % (self.name, type)))

    def soname_and_full_path(self):
        """Return soname and full path of the shared library, if any"""
        if 'soname_and_full_path' not in self.data:
            self.data['soname_and_full_path'] = None
            if self.attr['has_dynamic']:
                so_path = self._library_full_path('so')
                soname = self._soname_of(so_path)
                if soname:
                    self.data['soname_and_full_path'] = (soname, so_path)
        return self.data['soname_and_full_path']

    def before_generate(self):  # override
        """Override"""
        self._write_inclusion_check_info()
        self._check_binary_link_only()

    def _ninja_rules(self):
        a_path = self._library_full_path('a')
        so_path = self._library_full_path('so')

        self._add_default_target_file('a', a_path)
        self._add_target_file('so', so_path if self.attr['has_dynamic'] else a_path)

    def generate(self):
        """Generate build code for cc object/library."""
        self._check_deprecated_deps()
        self._ninja_rules()


def foreign_cc_library(
        name,
        install_dir='',
        lib_dir='lib',
        hdrs=[],
        hdr_dir='',
        export_incs=[],
        deps=[],
        has_dynamic=False,
        link_all_symbols=False,
        binary_link_only=False,
        visibility=None,
        deprecated=False,
        **kwargs):
    """Similar to a prebuilt cc_library, but it is built by a foreign build system,
    such as autotools, cmake, etc.

    Args:
        install_dir: str, the name of the directory where the package is installed,
            relative to the output directory
        hdrs: header files to be declared, always under the output directory
        hdr_dir: header file directory to be declared, always under the output directory
        lib_dir: str, the relative path of the lib dir under the `install_dir` dir.
        has_dynamic: bool, whether this library has a dynamic edition.
    """
    target = ForeignCcLibrary(
            name=name,
            deps=deps,
            visibility=visibility,
            export_incs=export_incs,
            install_dir=install_dir,
            hdrs=hdrs,
            hdr_dir=hdr_dir,
            lib_dir=lib_dir,
            has_dynamic=has_dynamic,
            link_all_symbols=link_all_symbols,
            binary_link_only=binary_link_only,
            deprecated=deprecated,
            kwargs=kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(cc_library)
build_rules.register_function(foreign_cc_library)
build_rules.register_function(prebuilt_cc_library)


class CcBinary(CcTarget):
    """
    This class is derived from CcTarget and it generates the cc_binary
    rules according to user options.
    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 warning,
                 defs,
                 incs,
                 embed_version,
                 optimize,
                 dynamic_link,
                 extra_cppflags,
                 extra_linkflags,
                 export_dynamic,
                 kwargs):
        """Init method.

        Init the cc binary.

        """
        # pylint: disable=too-many-locals
        super(CcBinary, self).__init__(
                name=name,
                type='cc_binary',
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                warning=warning,
                defs=defs,
                incs=incs,
                export_incs=[],
                optimize=optimize,
                extra_cppflags=extra_cppflags,
                extra_linkflags=extra_linkflags,
                kwargs=kwargs)
        self.attr['embed_version'] = embed_version
        self.attr['dynamic_link'] = dynamic_link
        self.attr['export_dynamic'] = export_dynamic

        # add extra link library
        link_libs = var_to_list(config.get_item('cc_binary_config', 'extra_libs'))
        self._add_implicit_library(link_libs)

    def _allow_duplicate_source(self):
        return True

    def _expand_deps_generation(self):
        if self.attr.get('dynamic_link'):
            build_targets = self.blade.get_build_targets()
            for dep in self.expanded_deps:
                build_targets[dep].attr['generate_dynamic'] = True

    def _get_rpath_links(self):
        """Get rpath_links from dependencies"""
        dynamic_link = self.attr['dynamic_link']
        build_targets = self.blade.get_build_targets()
        rpath_links = []
        for lib in self.expanded_deps:
            if build_targets[lib].type == 'prebuilt_cc_library':
                path = build_targets[lib]._rpath_link(dynamic_link)
                if path and path not in rpath_links:
                    rpath_links.append(path)

        return rpath_links

    def _generate_cc_binary_link_flags(self, dynamic_link):
        ldflags = []
        toolchain = self.blade.get_build_toolchain()
        if not dynamic_link and toolchain.cc_is('gcc') and toolchain.get_cc_version() > '4.5':
            ldflags += ['-static-libgcc', '-static-libstdc++']
        if self.attr.get('export_dynamic'):
            ldflags.append('-rdynamic')
        ldflags += self._generate_link_flags()
        for rpath_link in self._get_rpath_links():
            ldflags.append('-Wl,--rpath-link=%s' % rpath_link)
        return ldflags

    def _cc_binary(self, objs, dynamic_link):
        ldflags = self._generate_cc_binary_link_flags(dynamic_link)
        implicit_deps = []
        if dynamic_link:
            sys_libs, usr_libs = self._dynamic_dependencies()
        else:
            sys_libs, usr_libs, link_all_symbols_libs = self._static_dependencies()
            if link_all_symbols_libs:
                ldflags += self._generate_link_all_symbols_link_flags(link_all_symbols_libs)
                implicit_deps = link_all_symbols_libs

        extra_ldflags, order_only_deps = [], []
        if self.attr['embed_version']:
            scm = os.path.join(self.build_dir, 'scm.cc.o')
            extra_ldflags.append(scm)
            order_only_deps.append(scm)
        extra_ldflags += ['-l%s' % lib for lib in sys_libs]
        output = self._target_file_path(self.name)
        self._cc_link(output, 'link', objs=objs, deps=usr_libs,
                      ldflags=ldflags, extra_ldflags=extra_ldflags,
                      implicit_deps=implicit_deps,
                      order_only_deps=order_only_deps)
        self._add_default_target_file('bin', output)
        self._remove_on_clean(self._target_file_path(self.name + '.runfiles'))

    def before_generate(self):  # override
        """Override"""
        self._write_inclusion_check_info()

    def generate(self):
        """Generate build code for cc binary/test."""
        self._check_deprecated_deps()
        objs = self._cc_objects(self.attr['expanded_srcs'])
        self._cc_binary(objs, self.attr['dynamic_link'])


def cc_binary(name=None,
              srcs=[],
              deps=[],
              visibility=None,
              warning='yes',
              defs=[],
              incs=[],
              embed_version=True,
              optimize=None,
              dynamic_link=False,
              extra_cppflags=[],
              extra_linkflags=[],
              export_dynamic=False,
              **kwargs):
    """cc_binary target."""
    cc_binary_target = CcBinary(
            name=name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            warning=warning,
            defs=defs,
            incs=incs,
            embed_version=embed_version,
            optimize=optimize,
            dynamic_link=dynamic_link,
            extra_cppflags=extra_cppflags,
            extra_linkflags=extra_linkflags,
            export_dynamic=export_dynamic,
            kwargs=kwargs)
    build_manager.instance.register_target(cc_binary_target)


build_rules.register_function(cc_binary)


def cc_benchmark(name=None, deps=[], **kwargs):
    """cc_benchmark target."""
    cc_config = config.get_section('cc_config')
    benchmark_libs = cc_config['benchmark_libs']
    benchmark_main_libs = cc_config['benchmark_main_libs']
    deps = var_to_list(deps) + benchmark_libs + benchmark_main_libs
    cc_binary(name=name, deps=deps, **kwargs)


build_rules.register_function(cc_benchmark)


class CcPlugin(CcTarget):
    """
    This class is derived from CcTarget and it generates the cc_plugin
    rules according to user options.
    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 warning,
                 defs,
                 incs,
                 optimize,
                 prefix,
                 suffix,
                 extra_cppflags,
                 extra_linkflags,
                 allow_undefined,
                 strip,
                 kwargs):
        """Init method.

        Init the cc plugin target.

        """
        super(CcPlugin, self).__init__(
                  name=name,
                  type='cc_plugin',
                  srcs=srcs,
                  deps=deps,
                  visibility=visibility,
                  warning=warning,
                  defs=defs,
                  incs=incs,
                  export_incs=[],
                  optimize=optimize,
                  extra_cppflags=extra_cppflags,
                  extra_linkflags=extra_linkflags,
                  kwargs=kwargs)
        self.prefix = prefix
        self.suffix = suffix
        self.attr['allow_undefined'] = allow_undefined
        self.attr['strip'] = strip

    def before_generate(self):  # override
        """Override"""
        self._write_inclusion_check_info()

    def generate(self):
        """Generate build code for cc plugin."""
        self._check_deprecated_deps()
        objs = self._cc_objects(self.attr['expanded_srcs'])
        ldflags = self._generate_link_flags()
        implicit_deps = []
        sys_libs, usr_libs, link_all_symbols_libs = self._static_dependencies()
        if link_all_symbols_libs:
            ldflags += self._generate_link_all_symbols_link_flags(link_all_symbols_libs)
            implicit_deps = link_all_symbols_libs

        extra_ldflags = ['-l%s' % lib for lib in sys_libs]
        if self.name.endswith('.so'):
            output = self._target_file_path(self.name)
        else:
            output = self._target_file_path('lib%s.so' % self.name)
        if self.srcs or self.expanded_deps:
            if self.attr['strip']:
                link_output = '%s.unstripped' % output
            else:
                link_output = output
            self._cc_link(link_output, 'solink', objs=objs, deps=usr_libs,
                          ldflags=ldflags, extra_ldflags=extra_ldflags,
                          implicit_deps=implicit_deps)
            if self.attr['strip']:
                self.generate_build('strip', output, inputs=link_output)
            self._add_default_target_file('so', output)


def cc_plugin(
        name,
        srcs=[],
        deps=[],
        visibility=None,
        warning='yes',
        defs=[],
        incs=[],
        optimize=None,
        prefix=None,
        suffix=None,
        extra_cppflags=[],
        extra_linkflags=[],
        allow_undefined=True,
        strip=False,
        **kwargs):
    """cc_plugin target."""
    target = CcPlugin(
            name=name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            warning=warning,
            defs=defs,
            incs=incs,
            optimize=optimize,
            prefix=prefix,
            suffix=suffix,
            extra_cppflags=extra_cppflags,
            extra_linkflags=extra_linkflags,
            allow_undefined=allow_undefined,
            strip=strip,
            kwargs=kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(cc_plugin)


class CcTest(CcBinary):
    """
    This class is derived from CcTarget and it generates the cc_test
    rules according to user options.
    """

    def __init__(
            self,
            name,
            srcs,
            deps,
            visibility,
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
            kwargs):
        """Init method."""
        # pylint: disable=too-many-locals
        cc_test_config = config.get_section('cc_test_config')
        if dynamic_link is None:
            dynamic_link = cc_test_config['dynamic_link']

        super(CcTest, self).__init__(
                name=name,
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                warning=warning,
                defs=defs,
                incs=incs,
                embed_version=embed_version,
                optimize=optimize,
                dynamic_link=dynamic_link,
                extra_cppflags=extra_cppflags,
                extra_linkflags=extra_linkflags,
                export_dynamic=export_dynamic,
                kwargs=kwargs)
        self.type = 'cc_test'
        self.attr['testdata'] = var_to_list(testdata)
        self.attr['always_run'] = always_run
        self.attr['exclusive'] = exclusive

        gtest_lib = var_to_list(cc_test_config['gtest_libs'])
        gtest_main_lib = var_to_list(cc_test_config['gtest_main_libs'])

        # Hardcode deps rule to thirdparty gtest main lib.
        self._add_implicit_library(gtest_lib)
        self._add_implicit_library(gtest_main_lib)

        if heap_check is None:
            heap_check = cc_test_config.get('heap_check', '')
        else:
            if heap_check not in HEAP_CHECK_VALUES:
                self.error('heap_check can only be in %s' % HEAP_CHECK_VALUES)
                heap_check = ''

        perftools_lib = var_to_list(cc_test_config['gperftools_libs'])
        perftools_debug_lib = var_to_list(cc_test_config['gperftools_debug_libs'])
        if heap_check:
            self.attr['heap_check'] = heap_check

            if heap_check_debug:
                perftools_lib_list = perftools_debug_lib
            else:
                perftools_lib_list = perftools_lib

            self._add_implicit_library(perftools_lib_list)


def cc_test(name=None,
            srcs=[],
            deps=[],
            visibility=None,
            warning='yes',
            defs=[],
            incs=[],
            embed_version=False,
            optimize=None,
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
    """cc_test target."""
    # pylint: disable=too-many-locals
    cc_test_target = CcTest(
            name=name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            warning=warning,
            defs=defs,
            incs=incs,
            embed_version=embed_version,
            optimize=optimize,
            dynamic_link=dynamic_link,
            testdata=testdata,
            extra_cppflags=extra_cppflags,
            extra_linkflags=extra_linkflags,
            export_dynamic=export_dynamic,
            always_run=always_run,
            exclusive=exclusive,
            heap_check=heap_check,
            heap_check_debug=heap_check_debug,
            kwargs=kwargs)
    build_manager.instance.register_target(cc_test_target)


build_rules.register_function(cc_test)
