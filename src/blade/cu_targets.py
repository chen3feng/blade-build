# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: LI Yi <sincereli@tencent.com>
# Created:   September 27, 2013


"""
This module defines cu_library, cu_binary and cu_test rules
for cuda development.
"""

from __future__ import absolute_import
from __future__ import print_function

import os

from blade import build_manager
from blade import build_rules
from blade import config
from blade import console
from blade.cc_targets import CcTarget
from blade.util import var_to_list
from blade.util import run_command


# See https://docs.nvidia.com/cuda/cuda-compiler-driver-nvcc/index.html#supported-input-file-suffixes
_SOURCE_FILE_EXTS = {'cu', 'c', 'cc', 'cxx', 'cpp', 'ptx'}


# See https://docs.nvidia.com/cuda/cuda-compiler-driver-nvcc/index.html#supported-input-file-suffixes
_SOURCE_FILE_EXTS = {'cu', 'c', 'cc', 'cxx', 'cpp', 'ptx'}


class CuTarget(CcTarget):
    """This class is derived from CcTarget and is the base class
    of cu_library, cu_binary etc.

    """

    def __init__(self,
                 name,
                 type,
                 srcs,
                 deps,
                 visibility,
                 tags,
                 warning,
                 defs,
                 incs,
                 extra_cppflags,
                 extra_linkflags,
                 kwargs):
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)
        extra_cppflags = var_to_list(extra_cppflags)
        extra_linkflags = var_to_list(extra_linkflags)

        super(CuTarget, self).__init__(
                name=name,
                type=type,
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                tags=tags,
                warning=warning,
                defs=defs,
                incs=incs,
                export_incs=[],
                optimize=None,
                linkflags=None,
                extra_cppflags=extra_cppflags,
                extra_linkflags=extra_linkflags,
                kwargs=kwargs,
                src_exts=_SOURCE_FILE_EXTS)
        self._add_tags('lang:cu')

    def _get_cu_flags(self):
        """Return the nvcc flags according to the BUILD file and other configs."""
        nvcc_flags = []

        # Warnings
        if self.attr.get('warning', '') == 'no':
            nvcc_flags.append('-w')

        # Defs
        defs = self.attr.get('defs', [])
        nvcc_flags += [('-D' + macro) for macro in defs]

        # Optimize flags
        if (self.blade.get_options().profile == 'release' or
                self.attr.get('always_optimize')):
            nvcc_flags += self._get_optimize_flags()

        nvcc_flags += self.attr.get('extra_cppflags', [])

        # Incs
        incs = self._get_incs_list()

        return nvcc_flags, incs

    @staticmethod
    def _get_cuda_include():
        include_list = []
        cuda_path = os.environ.get('CUDA_PATH')
        if cuda_path:
            include_list.append('%s/include' % cuda_path)
            include_list.append('%s/samples/common/inc' % cuda_path)
            return include_list
        returncode, stdout, _ = run_command('nvcc --version', shell=True)
        if returncode == 0:
            version_line = stdout.splitlines(True)[-2]
            version = version_line.split()[4]
            version = version.replace(',', '')
            if os.path.isdir('/usr/local/cuda-%s' % version):
                include_list.append('/usr/local/cuda-%s/include' % version)
                include_list.append('/usr/local/cuda-%s/samples/common/inc' % version)
                return include_list
        return []

    def _get_cu_vars(self):
        vars = self._get_cc_vars()
        cuda_incs = self._get_cuda_include()
        vars["includes"] = vars.get("includes", "") \
            + ' ' + ' '.join(['-I%s' % inc for inc in cuda_incs])
        return vars

    def _cuda_objects(self, expanded_srcs, generated_headers=None):
        vars = self._get_cu_vars()
        order_only_deps = []
        order_only_deps += self._cc_compile_deps()
        if generated_headers and len(generated_headers) > 1:
            order_only_deps += generated_headers
        implicit_deps = []

        objs_dir = self._target_file_path(self.name + '.objs')
        objs = []
        for src, full_src in expanded_srcs:
            obj = os.path.join(objs_dir, src + '.o')
            self.generate_build("cudacc", obj, inputs=full_src,
                                implicit_deps=implicit_deps,
                                order_only_deps=order_only_deps,
                                variables=vars, clean=[])
            objs.append(obj)
        # self._remove_on_clean(objs_dir)
        return objs, None

    def _cuda_library(self, objs, inclusion_check_result=None):
        # TODO ar command flag is different with cc, such as rcs
        self._static_cc_library(objs, inclusion_check_result)
        if self.attr.get('generate_dynamic'):
            self._dynamic_cuda_library(objs, inclusion_check_result)

    def _dynamic_cuda_library(self, objs, inclusion_check_result):
        output = self._target_file_path('lib%s.so' % self.name)
        target_linkflags = self._generate_link_flags()
        sys_libs, usr_libs, incchk_deps = self._dynamic_dependencies()
        if inclusion_check_result:
            incchk_deps.append(inclusion_check_result)
        self._cc_link(output, 'cudasolink', objs=objs, deps=usr_libs, sys_libs=sys_libs,
                      order_only_deps=incchk_deps, target_linkflags=target_linkflags)
        self._add_target_file('so', output)


class CuLibrary(CuTarget):
    """This class is derived from CuTarget and generates the cu_library
    rules according to user options.

    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 tags,
                 warning,
                 defs,
                 incs,
                 link_all_symbols,
                 extra_cppflags,
                 extra_linkflags,
                 kwargs):
        super(CuLibrary, self).__init__(
            name=name,
            type='cu_library',
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            tags=tags,
            warning=warning,
            defs=defs,
            incs=incs,
            extra_cppflags=extra_cppflags,
            extra_linkflags=extra_linkflags,
            kwargs=kwargs)
        self.attr['link_all_symbols'] = link_all_symbols
        self._add_tags('type:library')

    def generate(self):
        self._check_deprecated_deps()
        objs, inclusion_check_result = self._cuda_objects(self.attr['expanded_srcs'])
        # Don't generate library file for header only library.
        if objs:
            self._cuda_library(objs, inclusion_check_result)


def cu_library(name=None,
               srcs=[],
               deps=[],
               visibility=None,
               tags=[],
               warning='yes',
               defs=[],
               incs=[],
               link_all_symbols=False,
               extra_cppflags=[],
               extra_linkflags=[],
               **kwargs):
    target = CuLibrary(
        name,
        srcs=srcs,
        deps=deps,
        visibility=visibility,
        tags=tags,
        warning=warning,
        defs=defs,
        incs=incs,
        link_all_symbols=link_all_symbols,
        extra_cppflags=extra_cppflags,
        extra_linkflags=extra_linkflags,
        kwargs=kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(cu_library)


class CuBinary(CuTarget):
    """This class is derived from CuTarget and generates the cu_binary
    rules according to user options.

    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 tags,
                 warning,
                 defs,
                 incs,
                 extra_cppflags,
                 extra_linkflags,
                 kwargs):
        super(CuBinary, self).__init__(
            name=name,
            type='cu_binary',
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            tags=tags,
            warning=warning,
            defs=defs,
            incs=incs,
            extra_cppflags=extra_cppflags,
            extra_linkflags=extra_linkflags,
            kwargs=kwargs)
        self._add_tags('type:binary')

    def generate(self):
        self._check_deprecated_deps()
        objs, inclusion_check_result = self._cuda_objects(self.attr['expanded_srcs'])
        # Don't generate library file for header only library.
        self._cuda_binary(objs, inclusion_check_result, self.attr.get('dynamic_link', False))

    def _generate_cuda_binary_link_flags(self, dynamic_link):
        # TODO to be implemented
        return []

    def _static_dependencies(self):
        """
        Find static dependencies for ninja build, including system libraries
        and user libraries.
        User libraries consist of normal libraries and libraries which should
        be linked all symbols within them using whole-archive option of gnu linker.
        """
        targets = self.blade.get_build_targets()
        sys_libs, usr_libs, link_all_symbols_libs = [], [], []
        incchk_deps = []
        for key in self.expanded_deps:
            dep = targets[key]
            if dep.path == '#':
                sys_libs.append(dep.name)
                continue

            lib = dep._get_target_file('a')
            if lib:
                if dep.attr.get('link_all_symbols'):
                    link_all_symbols_libs.append(lib)
                else:
                    usr_libs.append(lib)
                continue

            # '.a' file is not generated for header only libraries, use this file as implicit dep.
            incchk_result = dep._get_target_file('incchk.result')
            if incchk_result:
                incchk_deps.append(incchk_result)

        return sys_libs, usr_libs, link_all_symbols_libs, incchk_deps

    def _cuda_binary(self, objs, inclusion_check_result, dynamic_link):
        implicit_deps = None
        target_linkflags = self._generate_cuda_binary_link_flags(dynamic_link)
        if dynamic_link:
            sys_libs, usr_libs, incchk_deps = self._dynamic_dependencies()
        else:
            sys_libs, usr_libs, link_all_symbols_libs, incchk_deps = self._static_dependencies()
            if link_all_symbols_libs:
                target_linkflags += self._generate_link_all_symbols_link_flags(link_all_symbols_libs)
                implicit_deps = link_all_symbols_libs

        # Using incchk as order_only_deps to avoid relink when only inclusion check is done.
        order_only_deps = incchk_deps
        if inclusion_check_result:
            order_only_deps.append(inclusion_check_result)

        output = self._target_file_path(self.name)
        self._cuda_link(output, 'cudalink', objs=objs, deps=usr_libs,
                        sys_libs=sys_libs,
                        linker_scripts=self.attr.get('lds_fullpath'),
                        version_scripts=self.attr.get('vers_fullpath'),
                        target_linkflags=target_linkflags,
                        implicit_deps=implicit_deps,
                        order_only_deps=order_only_deps)
        self._add_default_target_file('bin', output)
        self._remove_on_clean(self._target_file_path(self.name + '.runfiles'))

    def _cuda_link(self, output, rule, objs, deps, sys_libs, linker_scripts=None, version_scripts=None,
                   target_linkflags=None, implicit_deps=None, order_only_deps=None):
        vars = {}
        linkflags = self.attr.get('linkflags')
        if linkflags is not None:
            vars['linkflags'] = ' '.join(linkflags)
        if target_linkflags:
            vars['target_linkflags'] = ' '.join(target_linkflags)
        extra_linkflags = ['-l%s' % lib for lib in sys_libs]
        extra_linkflags += self.attr.get('extra_linkflags')
        if implicit_deps is None:
            implicit_deps = []
        if linker_scripts:
            extra_linkflags += ['-T %s' % lds for lds in linker_scripts]
            implicit_deps += linker_scripts
        if version_scripts:
            extra_linkflags += ['-Wl,--version-script=%s' % ver for ver in version_scripts]
            implicit_deps += version_scripts
        if extra_linkflags:
            vars['extra_linkflags'] = ' '.join(extra_linkflags)
        self.generate_build(rule, output,
                            inputs=objs + deps,
                            implicit_deps=implicit_deps,
                            order_only_deps=order_only_deps,
                            variables=vars)


def cu_binary(name=None,
              srcs=[],
              deps=[],
              visibility=None,
              tags=[],
              warning='yes',
              defs=[],
              incs=[],
              extra_cppflags=[],
              extra_linkflags=[],
              **kwargs):
    target = CuBinary(
        name=name,
        srcs=srcs,
        deps=deps,
        visibility=visibility,
        tags=tags,
        warning=warning,
        defs=defs,
        incs=incs,
        extra_cppflags=extra_cppflags,
        extra_linkflags=extra_linkflags,
        kwargs=kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(cu_binary)


class CuTest(CuBinary):
    """This class is derived from CuBinary and generates the cu_test
    rules according to user options.

    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 tags,
                 warning,
                 defs,
                 incs,
                 extra_cppflags,
                 extra_linkflags,
                 testdata,
                 always_run,
                 exclusive,
                 kwargs):
        # pylint: disable=too-many-locals
        super(CuTest, self).__init__(
            name=name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            tags=tags,
            warning=warning,
            defs=defs,
            incs=incs,
            extra_cppflags=extra_cppflags,
            extra_linkflags=extra_linkflags,
            kwargs=kwargs)
        self._add_tags('lang:cu')
        self.type = 'cu_test'
        self.attr['testdata'] = var_to_list(testdata)
        self.attr['always_run'] = always_run
        self.attr['exclusive'] = exclusive

        cc_test_config = config.get_section('cc_test_config')
        gtest_lib = var_to_list(cc_test_config['gtest_libs'])
        gtest_main_lib = var_to_list(cc_test_config['gtest_main_libs'])

        # Hardcode deps rule to thirdparty gtest main lib.
        self._add_implicit_library(gtest_lib)
        self._add_implicit_library(gtest_main_lib)


def cu_test(
        name,
        srcs=[],
        deps=[],
        visibility=None,
        tags=[],
        warning='yes',
        defs=[],
        incs=[],
        extra_cppflags=[],
        extra_linkflags=[],
        testdata=[],
        always_run=False,
        exclusive=False,
        **kwargs):
    target = CuTest(
        name=name,
        srcs=srcs,
        deps=deps,
        visibility=visibility,
        tags=tags,
        warning=warning,
        defs=defs,
        incs=incs,
        extra_cppflags=extra_cppflags,
        extra_linkflags=extra_linkflags,
        testdata=testdata,
        always_run=always_run,
        exclusive=exclusive,
        kwargs=kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(cu_test)
