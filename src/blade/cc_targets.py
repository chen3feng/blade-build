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

import collections
import os
import subprocess
from string import Template

from blade import build_manager
from blade import config
from blade import console
from blade import build_rules
from blade.blade_util import var_to_list, stable_unique
from blade.constants import HEAP_CHECK_VALUES
from blade.target import Target


def is_header_file(filename):
    _, ext = os.path.splitext(filename)
    ext = ext[1:]  # Remove leading '.'
    # See https://gcc.gnu.org/onlinedocs/gcc/Overall-Options.html
    return ext in ('h', 'hh', 'H', 'hp', 'hpp', 'hxx', 'HPP', 'h++', 'inc', 'tcc')


# A dict[hdr, set(target)]
# For a header file, which targets declared it.
_hdr_targets_map = collections.defaultdict(set)

# A dict[inc, set(target)]
# For a include dir, which targets declared it.
_hdr_dir_targets_map = collections.defaultdict(set)


def _declare_hdrs(target, hdrs):
    """Declare hdr to lib relationships

    Args:
        target: the target which owns the hdrs
        hdrs:list, the full path (based in workspace troot) of hdrs
    """
    for hdr in hdrs:
        _hdr_targets_map[hdr].add(target.key)


def _declare_hdr_dir(target, inc):
    """Declare a inc:lib relationship

    Args:
        target: the target which owns the include dir
        inc:str, the full path (based in workspace troot) of include dir
    """
    _hdr_dir_targets_map[inc].add(target.key)


def _find_libs_by_header(hdr):
    libs = _hdr_targets_map.get(hdr)
    if libs:
        return libs
    hdr_dir = os.path.dirname(hdr)
    while True:
        libs = _hdr_dir_targets_map.get(hdr_dir)
        if libs:
            return libs
        old_hdr_dir = hdr_dir
        hdr_dir = os.path.dirname(hdr_dir)
        if hdr_dir == old_hdr_dir:
            return None


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
                 kwargs):
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
                deps=deps,
                visibility=visibility,
                kwargs=kwargs)

        self._check_defs(defs)
        self._check_incorrect_no_warning(warning)

        self.data['warning'] = warning
        self.data['private_hdrs'] = private_hdrs
        self.data['defs'] = var_to_list(defs)
        self.data['incs'] = self._incs_to_fullpath(incs)
        self.data['export_incs'] = self._incs_to_fullpath(export_incs)
        self.data['optimize'] = var_to_list(optimize)
        self.data['extra_cppflags'] = var_to_list(extra_cppflags)
        self.data['extra_linkflags'] = var_to_list(extra_linkflags)
        # TODO(chen3feng): Move to CcLibrary
        options = self.blade.get_options()
        self.data['generate_dynamic'] = (getattr(options, 'generate_dynamic', False) or
                                         config.get_item('cc_library_config', 'generate_dynamic'))

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
                        'explicitly, if it does not exist, set it to empty (hdrs = [])')
        if not hdrs:
            return
        expanded_hdrs = []
        for h in var_to_list(hdrs):
            hdr = self._source_file_path(h)
            if not os.path.exists(hdr):
                hdr = self._target_file_path(h)
            expanded_hdrs.append(hdr)
        self.data['hdrs'] = expanded_hdrs
        _declare_hdrs(self, expanded_hdrs)

    def _check_deprecated_deps(self):
        """Check whether it depends upon a deprecated library. """
        for key in self.deps:
            dep = self.target_database.get(key)
            if dep and dep.data.get('deprecated'):
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
                self.warning('DO NOT define c++ keyword "%s" as macro' % macro)

    def _check_incorrect_no_warning(self, warning):
        """check if warning=no is correctly used or not. """
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
            self.warning(""""warning='no'" should only be used for thirdparty libraries.""")

    def _get_optimize_flags(self):
        """get optimize flags such as -O2"""
        return self.data.get('optimize') or config.get_item('cc_config', 'optimize') or ['-O2']

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

    def _cc_compile_dep_files(self):
        """Calculate the dependencies which generate header files.

        If a dependency will generate c/c++ header files, we must depends on it during the
        compiling stage, otherwise, the 'Missing header file' error will occurs.

        NOTE: Here is an optimization: If we know the detaild generated header files, depends on
              them explicitly rather than depends on the whole target improves the parallelism.
        """
        queue = collections.deque(self.deps)

        keys = set()
        result = []
        while queue:
            key = queue.popleft()
            if key not in keys:
                keys.add(key)
                t = self.target_database[key]
                if t.data.get('generated_incs'):
                    # We know it will generate header files but has no details, so we have to
                    # depends on the whole target
                    result.append(t._get_target_file())
                elif 'generated_hdrs' in t.data:
                    generated_hdrs = t.data.get('generated_hdrs')
                    if generated_hdrs:
                        result += generated_hdrs
                elif 'cc_compile_deps_stamp' in t.data:
                    stamp = t.data['cc_compile_deps_stamp']
                    if stamp:
                        result.append(stamp)
                queue.extend(t.deps)

        return result

    def _get_rule_from_suffix(self, src):
        """
        Return cxx for C++ source files with suffix as .cc/.cpp/.cxx,
        return cc otherwise for C, Assembler, etc.
        """
        for suffix in ('.cc', '.cpp', '.cxx'):
            if src.endswith(suffix):
                return 'cxx'
        return 'cc'

    def _setup_cc_vars(self, vars):
        """Set up warning, compile options and include directories for cc build. """
        if self.data.get('warning') != 'yes':
            vars['c_warnings'] = ''
            vars['cxx_warnings'] = ''
        cppflags, includes = self._get_cc_flags()
        if cppflags:
            vars['cppflags'] = ' '.join(cppflags)
        if includes:
            vars['includes'] = ' '.join(['-I%s' % inc for inc in includes])

    def _generate_link_flags(self):
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
                    if dep.data.get('link_all_symbols'):
                        link_all_symbols_libs.append(lib)
                    else:
                        usr_libs.append(lib)
        return sys_libs, usr_libs, link_all_symbols_libs

    def _cc_hdrs(self, hdrs_inclusion_srcs, vars):
        if not self._need_verify_generate_hdrs():
            return

        for key in ('c_warnings', 'cxx_warnings'):
            if key in vars:
                del vars[key]
        for src, obj, rule in hdrs_inclusion_srcs:
            output = obj[:-2] + '.H'  # Replace '.o' suffix with '.H'
            rule = '%shdrs' % rule
            self.ninja_build(rule, output, inputs=src, implicit_deps=[obj], variables=vars)

    def _cc_compile_deps_stamp(self):
        """Return a stamp which depends on targets which generate header files. """
        self.data['cc_compile_deps_stamp'] = None
        deps = self._cc_compile_dep_files()
        if not deps:
            return None
        stamp = self._target_file_path(self.name + '__compile_deps__')
        self.ninja_build('phony', stamp, inputs=deps)
        self.data['cc_compile_deps_stamp'] = stamp
        return stamp

    def _cc_objects(self, sources, generated=False, generated_headers=None):
        """Generate cc objects build rules in ninja. """
        # pylint: disable=too-many-locals
        vars = {}
        self._setup_cc_vars(vars)
        implicit_deps = []
        stamp = self._cc_compile_deps_stamp()
        if stamp:
            implicit_deps.append(stamp)
        objs_dir = self._target_file_path(self.name + '.objs')
        objs, hdrs_inclusion_srcs = [], []
        for src in sources:
            obj = '%s.o' % os.path.join(objs_dir, src)
            rule = self._get_rule_from_suffix(src)
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
            self.ninja_build(rule, obj, inputs=input,
                             implicit_deps=implicit_deps,
                             variables=vars)
            objs.append(obj)

        self.data['objs'] = objs
        self._cc_hdrs(hdrs_inclusion_srcs, vars)

    def _static_cc_library(self):
        output = self._target_file_path('lib%s.a' % self.name)
        objs = self.data.get('objs', [])
        self.ninja_build('ar', output, inputs=objs)
        self._add_default_target_file('a', output)

    def _dynamic_cc_library(self):
        output = self._target_file_path('lib%s.so' % self.name)
        ldflags = self._generate_link_flags()
        sys_libs, usr_libs = self._dynamic_dependencies()
        extra_ldflags = ['-l%s' % lib for lib in sys_libs]
        self._cc_link(output, 'solink', deps=usr_libs,
                      ldflags=ldflags, extra_ldflags=extra_ldflags)
        self._add_target_file('so', output)

    def _cc_library(self):
        self._static_cc_library()
        if self.data.get('generate_dynamic'):
            self._dynamic_cc_library()

    def _cc_link(self, output, rule, deps,
                 ldflags=None, extra_ldflags=None,
                 implicit_deps=None, order_only_deps=None):
        objs = self.data.get('objs', [])
        vars = {}
        if ldflags:
            vars['ldflags'] = ' '.join(ldflags)
        if extra_ldflags:
            vars['extra_ldflags'] = ' '.join(extra_ldflags)
        self.ninja_build(rule, output,
                         inputs=objs + deps,
                         implicit_deps=implicit_deps,
                         order_only_deps=order_only_deps,
                         variables=vars)

    def _need_verify_generate_hdrs(self):
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
        """Extract headers included by .cc/.h directly"""
        objs_dir = self._target_file_path(self.name + '.objs')
        path = '%s.H' % os.path.join(objs_dir, src)
        if not os.path.exists(path):
            return []
        hdrs, level_two_hdrs = self._extract_cc_hdrs_from_stack(path)
        self_hdr_patterns = self._cc_self_hdr_patterns(src)
        for i, hdr in enumerate(hdrs):
            if hdr in self_hdr_patterns:
                return hdrs[:i] + level_two_hdrs[hdr] + hdrs[i + 1:]

        return hdrs

    @staticmethod
    def _parse_hdr_level(line):
        """Parse a normal line of a header stack file

        Example:
          . ./common/rpc/rpc_client.h
        """
        pos = line.find(' ')
        if pos == -1:
            return -1, ''
        level, hdr = line[:pos].count('.'), line[pos + 1:]
        if hdr.startswith('./'):
            hdr = hdr[2:]
        return level, hdr

    def _find_inclusion_file(self, src):
        """Find the '.H' file for the given src.

        The `.H` file is generated from gcc's `-H` option, see
        https://gcc.gnu.org/onlinedocs/gcc/Preprocessor-Options.html
        for details.
        """
        objs_dir = self._target_file_path(self.name + '.objs')
        path = '%s.H' % os.path.join(objs_dir, src)
        if not os.path.exists(path):
            return ''
        return path

    def _parse_inclusion_stacks(self, path):
        """Parae headers inclusion stacks from file.

        Given the following inclusions found in the app/example/foo.cc.H:

            . ./app/example/foo.h
            .. build64_release/app/example/proto/foo.pb.h
            ... build64_release/common/rpc/rpc_service.pb.h
            . build64_release/app/example/proto/bar.pb.h
            . ./common/rpc/rpc_client.h
            .. build64_release/common/rpc/rpc_options.pb.h

        Return a list with each item being a list representing where the header
        is included from in the current translation unit.

        Note that we will STOP tracking at the first generated header (if any)
        while other headers included from the header directly or indirectly are
        ignored since that part of dependency is ensured by the generator, such
        as proto_library.

        As shown in the example above, it returns the following stacks:

            [
                ['app/example/foo.h', 'build64_release/app/example/proto/foo.pb.h'],
                ['build64_release/app/example/proto/bar.pb.h'],
                ['common/rpc/rpc_client.h', 'build64_release/common/rpc/rpc_options.pb.h'],
            ]
        """
        build_dir = self.build_dir
        direct_hdrs = []  # The directly included header files
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
            for line in f:
                line = line.rstrip()  # Strip `\n`
                if not line.startswith('.'):
                    # The remaining lines are useless for us
                    break
                level, hdr = self._parse_hdr_level(line)
                if level == -1:
                    console.log('%s: Unrecognized line %s' % (path, line))
                    break
                if level == 1 and not hdr.startswith('/'):
                    direct_hdrs.append(hdr)
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

        return direct_hdrs, stacks

    @staticmethod
    def _hdr_is_declared(hdr, declared_hdrs, declared_incs):
        if hdr in declared_hdrs:
            return True
        for dir in declared_incs:
            if hdr.startswith(dir):
                return True
        return False

    def _verify_direct_headers(self, src, direct_hdrs, suppressd_hdrs):
        verified_hdrs = set()
        problematic_hdrs = set()
        msg = []
        for hdr in direct_hdrs:
            libs = _find_libs_by_header(hdr)
            if not libs:
                continue
            deps = set(self.deps + [self.key])  # Don't forget self
            if not (libs & deps):  # pylint: disable=superfluous-parens
                # NOTE:
                # We just don't report a suppressd hdr, but still need to record it as a failure.
                # Because a passed src will not be verified again, even if we remove it from the
                # suppress list.
                # Same reason in the _verify_generated_headers.
                problematic_hdrs.add(hdr)
                if hdr not in suppressd_hdrs:
                    msg.append('    For %s' % self._hdr_declaration_message(hdr, libs))
            verified_hdrs.add(hdr)
        if msg:
            msg.insert(0, '  In %s,' % src)
        return verified_hdrs, problematic_hdrs, msg

    @staticmethod
    def _hdr_declaration_message(hdr, libs=None):
        if libs is None:
            libs = _find_libs_by_header(hdr)
        if not libs:
            return hdr
        libs = ' or '.join(['//%s' % lib for lib in libs])
        return '%s, which belongs to %s' % (hdr, libs)

    def _verify_generated_headers(self, src, stacks, declared_hdrs, declared_incs,
                                  suppressd_hdrs, verified_hdrs):
        problematic_hdrs = set()
        msg = []
        for stack in stacks:
            generated_hdr = stack[-1]
            if generated_hdr in verified_hdrs:  # Already verified as direct_hdrs
                continue
            if self._hdr_is_declared(generated_hdr, declared_hdrs, declared_incs):
                continue
            stack.pop()
            problematic_hdrs.add(generated_hdr)
            if generated_hdr in suppressd_hdrs:
                continue
            source = self._source_file_path(src)
            msg.append('  For %s' % self._hdr_declaration_message(generated_hdr))
            if not stack:
                msg.append('    In file included from %s' % source)
            else:
                stack.reverse()
                msg.append('    In file included from %s' % self._hdr_declaration_message(stack[0]))
                prefix = '                     from %s'
                msg += [prefix % self._hdr_declaration_message(h) for h in stack[1:]]
                msg.append(prefix % source)
        return problematic_hdrs, msg

    def _cleanup_target_files(self):
        """Clean up built result files"""
        for f in self._get_target_files():
            try:
                os.remove(f)
                console.debug('Remove %s due to hdr dep missing' % f)
            except OSError:
                pass

    def verify_hdr_dep_missing(self, history, suppress):
        """
        Verify whether included header files is declared in "deps" correctly.

        Returns:
            Whether nothing is wrong.
        """
        # pylint: disable=too-many-locals
        if not self._need_verify_generate_hdrs():
            return True, {}

        # Collect header/include declarations
        declared_hdrs = set()
        declared_incs = set()

        build_targets = self.blade.get_build_targets()
        for key in self.expanded_deps:
            dep = build_targets[key]
            declared_hdrs.update(dep.data.get('generated_hdrs', []))
            declared_incs.update(dep.data.get('generated_incs', []))

        # Verify
        details = {}  # {src: list(hdrs)}
        preprocess_paths, failed_preprocess_paths = set(), set()

        direct_verify_msg = []
        generated_verify_msg = []

        for src in self.srcs:
            path = self._find_inclusion_file(src)
            if not path or (path in history and int(os.path.getmtime(path)) == history[path]):
                continue

            direct_hdrs, stacks = self._parse_inclusion_stacks(path)
            preprocess_paths.add(path)

            verified_hdrs, problematic_hdrs, msg = self._verify_direct_headers(
                    src, direct_hdrs, suppress.get(src, []))
            if problematic_hdrs:
                details[src] = list(problematic_hdrs)
                failed_preprocess_paths.add(path)
                direct_verify_msg += msg
                # Direct headers verification can cover the under one
                continue

            # But direct headers can not cover all, so it is still useful
            problematic_hdrs, msg = self._verify_generated_headers(
                    src, stacks, declared_hdrs, declared_incs, suppress.get(src, []), verified_hdrs)
            if problematic_hdrs:
                if src in details:
                    details[src] += problematic_hdrs
                else:
                    details[src] = list(problematic_hdrs)
                generated_verify_msg += msg
                failed_preprocess_paths.add(path)

        severity = config.get_item('cc_config', 'hdr_dep_missing_severity')
        output = getattr(self, severity)
        if direct_verify_msg:
            output('Missing dependency declaration:\n%s' % '\n'.join(direct_verify_msg))
        if generated_verify_msg:
            output('Missing indirect dependency declaration:\n%s' % '\n'.join(generated_verify_msg))

        # Update history
        for preprocess in failed_preprocess_paths:
            if preprocess in history:
                del history[preprocess]
        for preprocess in preprocess_paths - failed_preprocess_paths:
            history[preprocess] = int(os.path.getmtime(preprocess))

        failed = (direct_verify_msg or generated_verify_msg) and severity == 'error'
        if failed:
            self._cleanup_target_files()

        return not failed, details


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
        self.data['link_all_symbols'] = link_all_symbols
        self.data['always_optimize'] = always_optimize
        self.data['deprecated'] = deprecated
        self.data['allow_undefined'] = allow_undefined
        self._set_hdrs(hdrs)
        self._set_secure(secure)

    def _set_secure(self, secure):
        if secure:
            self.data['secure'] = secure
            for src in self.srcs:
                path = self._source_file_path(src)
                if not os.path.exists(path):
                    # Touch a place holder file for securecc, will be deleted by securecc
                    path = self._target_file_path(src)
                    dirname = os.path.dirname(path)
                    if not os.path.exists(dirname):
                        os.makedirs(dirname)
                    open(path, 'w').close()

    def _securecc_object(self, obj, src, implicit_deps, vars):
        assert obj.endswith('.o')
        pos = obj.rfind('.', 0, -2)
        assert pos != -1
        secure_obj = '%s__securecc__.cc.o' % obj[:pos]
        path = self._source_file_path(src)
        if not os.path.exists(path):
            path = self._target_file_path(src)
        self.ninja_build('securecccompile', secure_obj, inputs=path,
                         implicit_deps=implicit_deps, variables=vars)
        self.ninja_build('securecc', obj, inputs=secure_obj)

    def _securecc_objects(self, sources):
        """Generate securecc objects build rules in ninja. """
        vars = {}
        self._setup_cc_vars(vars)
        implicit_deps = []
        stamp = self._cc_compile_deps_stamp()
        if stamp:
            implicit_deps.append(stamp)

        objs_dir = self._target_file_path(self.name + '.objs')
        objs = []
        for src in sources:
            obj = '%s.o' % os.path.join(objs_dir, src)
            self._securecc_object(obj, src, implicit_deps, vars)
            objs.append(obj)

        self.data['objs'] = objs

    def ninja_rules(self):
        """Generate ninja build rules for cc object/library. """
        self._check_deprecated_deps()
        if self.srcs:
            if self.data.get('secure'):
                self._securecc_objects(self.srcs)
            else:
                self._cc_objects(self.srcs)
            self._cc_library()


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
                optimize=[],
                extra_cppflags=[],
                extra_linkflags=[],
                kwargs=kwargs)
        self.data['libpath_pattern'] = libpath_pattern
        self.data['link_all_symbols'] = link_all_symbols
        self.data['deprecated'] = deprecated
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

        # When a prebuilt shared library with a 'soname' is linked into a program
        # Its name appears in the program's DT_NEEDED tag without full path.
        # So we need to make a symbolic link let the program find the library.
        # Type: tuple(target_path, soname)
        # TODO(): bad naming
        self.file_and_link = None

        if has_static:
            self.data['static_source'] = static_source
            self._add_target_file('a', static_source)
            if not has_dynamic:
                # Using static library for dynamic linking
                self._add_target_file('so', static_source)

        if has_dynamic:
            dynamic_target = self._target_file_path(os.path.basename(dynamic_source))
            self.data['dynamic_source'] = dynamic_source
            self.data['dynamic_target'] = dynamic_target
            self._add_target_file('so', dynamic_target)

            soname = self._soname(dynamic_source)
            if soname:
                self.file_and_link = (dynamic_target, soname)

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

        pattern = self.data.get('libpath_pattern')
        if pattern is None:
            libpath = PrebuiltCcLibrary._default_libpath
        else:
            libpath = Template(pattern).substitute(bits=bits,
                                                   arch=arch,
                                                   profile=profile)

        libpath = os.path.join(self.path, libpath)

        return os.path.join(libpath, 'lib%s.%s' % (self.name, suffix))

    def _soname(self, so):
        """Get the soname of prebuilt shared library."""
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

    def _is_depended(self):
        """Does this library really be used"""
        build_targets = self.blade.get_build_targets()
        depended_targets = self.blade.get_depended_target_database()
        for key in depended_targets[self.key]:
            t = build_targets[key]
            if t.type != 'prebuilt_cc_library':
                return True
        return False

    def _rpath_link(self, dynamic):
        path = self._library_source_path('so')
        if os.path.exists(path):
            return os.path.dirname(path)
        return None

    def ninja_rules(self):
        """Generate ninja build rules for cc object/library. """
        self._check_deprecated_deps()
        # We allow a prebuilt cc_library doesn't exist if it is not used.
        # So if this library is not depended by any target, don't generate any
        # rule to avoid runtime error and also avoid unnecessary runtime cost.
        if not self._is_depended():
            return
        dynamic_source = self.data.get('dynamic_source')
        dynamic_target = self.data.get('dynamic_target')
        if dynamic_source and dynamic_target:
            self.ninja_build('copy', dynamic_target, inputs=dynamic_source)

def prebuilt_cc_library(
        name,
        deps=[],
        visibility=None,
        export_incs=[],
        hdrs=None,
        libpath_pattern=None,
        link_all_symbols=False,
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
                 link_all_symbols,
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
                optimize=[],
                extra_cppflags=[],
                extra_linkflags=[],
                kwargs=kwargs)
        self.data['install_dir'] = install_dir
        self.data['link_all_symbols'] = link_all_symbols
        self.data['deprecated'] = deprecated
        self.data['lib_dir'] = lib_dir

        if hdrs:
            hdrs = [self._target_file_path(os.path.join(install_dir, h)) for h in var_to_list(hdrs)]
            self.data['hdrs'] = hdrs
            self.data['generated_hdrs'] = hdrs
            _declare_hdrs(self, hdrs)
        else:
            hdr_dir = self._target_file_path(os.path.join(install_dir, hdr_dir))
            self.data['generated_incs'] = [hdr_dir]
            _declare_hdr_dir(self, hdr_dir)

    def _ninja_rules(self):
        lib = self._target_file_path(os.path.join(self.data['install_dir'], self.data['lib_dir'],
                                                  'lib%s.a' % self.name))
        self._add_default_target_file('a', lib)
        self._add_target_file('so', lib)

    def ninja_rules(self):
        """Generate ninja build rules for cc object/library. """
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
        link_all_symbols=False,
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
            link_all_symbols=link_all_symbols,
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
                build_targets[dep].data['generate_dynamic'] = True

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

    def _generate_cc_binary_link_flags(self, dynamic_link):
        ldflags = []
        platform = self.blade.get_build_platform()
        if (not dynamic_link and
            platform.gcc_in_use() and platform.get_cc_version() > '4.5'):
            ldflags += ['-static-libgcc', '-static-libstdc++']
        if self.data.get('export_dynamic'):
            ldflags.append('-rdynamic')
        ldflags += self._generate_link_flags()
        for rpath_link in self._get_rpath_links():
            ldflags.append('-Wl,--rpath-link=%s' % rpath_link)
        return ldflags

    def _cc_binary(self, dynamic_link):
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
        if self.data['embed_version']:
            scm = os.path.join(self.build_dir, 'scm.cc.o')
            extra_ldflags.append(scm)
            order_only_deps.append(scm)
        extra_ldflags += ['-l%s' % lib for lib in sys_libs]
        output = self._target_file_path(self.name)
        self._cc_link(output, 'link', deps=usr_libs,
                      ldflags=ldflags, extra_ldflags=extra_ldflags,
                      implicit_deps=implicit_deps,
                      order_only_deps=order_only_deps)
        self._add_default_target_file('bin', output)

    def ninja_rules(self):
        """Generate ninja build rules for cc binary/test. """
        self._check_deprecated_deps()
        self._cc_objects(self.srcs)
        self._cc_binary(self.data['dynamic_link'])


def cc_binary(name=None,
              srcs=[],
              deps=[],
              visibility=None,
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
    """cc_benchmark target. """
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
        self.data['allow_undefined'] = allow_undefined
        self.data['strip'] = strip

    def ninja_rules(self):
        """Generate ninja build rules for cc plugin. """
        self._check_deprecated_deps()
        self._cc_objects(self.srcs)
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
            if self.data['strip']:
                link_output = '%s.unstripped' % output
            else:
                link_output = output
            self._cc_link(link_output, 'solink', deps=usr_libs,
                          ldflags=ldflags, extra_ldflags=extra_ldflags,
                          implicit_deps=implicit_deps)
            if self.data['strip']:
                self.ninja_build('strip', output, inputs=link_output)
            self._add_default_target_file('so', output)


def cc_plugin(
        name,
        srcs=[],
        deps=[],
        visibility=None,
        warning='yes',
        defs=[],
        incs=[],
        optimize=[],
        prefix=None,
        suffix=None,
        extra_cppflags=[],
        extra_linkflags=[],
        allow_undefined=True,
        strip=False,
        **kwargs):
    """cc_plugin target. """
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
                self.error('heap_check can only be in %s' % HEAP_CHECK_VALUES)
                heap_check = ''

        perftools_lib = var_to_list(cc_test_config['gperftools_libs'])
        perftools_debug_lib = var_to_list(cc_test_config['gperftools_debug_libs'])
        if heap_check:
            self.data['heap_check'] = heap_check

            if heap_check_debug:
                perftools_lib_list = perftools_debug_lib
            else:
                perftools_lib_list = perftools_lib

            self._add_hardcode_library(perftools_lib_list)


def cc_test(name=None,
            srcs=[],
            deps=[],
            visibility=None,
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
