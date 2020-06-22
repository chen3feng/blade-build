# Copyright (c) 2012 iQIYI Inc.
# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Jingxu Chen <chenjingxu@qiyi.com>
#         Feng Chen <chen3feng@gmail.com>
# Date:   October 13, 2012


"""
The module defines thrift_library target to generate code in
different languages from .thrift file.

"""

from __future__ import absolute_import

import os

from blade import build_manager
from blade import build_rules
from blade import config
from blade import console
from blade.blade_util import var_to_list
from blade.cc_targets import CcTarget
from blade.thrift_helper import ThriftHelper


# TODO(chen3feng): Support java generation
class ThriftLibrary(CcTarget):
    """A thrift library target derived from CcTarget. """

    def __init__(
            self,
            name,
            srcs,
            deps,
            visibility,
            optimize,
            deprecated,
            kwargs):
        srcs = var_to_list(srcs)
        self._check_thrift_srcs_name(srcs)
        super(ThriftLibrary, self).__init__(
                name=name,
                type='thrift_library',
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                warning='',
                hdr_dep_missing_severity=None,
                defs=[],
                incs=[],
                export_incs=[],
                optimize=optimize,
                extra_cppflags=[],
                extra_linkflags=[],
                kwargs=kwargs)

        thrift_libs = config.get_item('thrift_config', 'thrift_libs')
        # Hardcode deps rule to thrift libraries.
        self._add_hardcode_library(thrift_libs)

        # Link all the symbols by default
        self.data['link_all_symbols'] = True
        self.data['deprecated'] = deprecated

        # For each thrift file initialize a ThriftHelper, which will be used
        # to get the source files generated from thrift file.
        self.thrift_helpers = {}
        for src in srcs:
            self.thrift_helpers[src] = ThriftHelper(self.path, src)

    def _check_thrift_srcs_name(self, srcs):
        """Check whether the thrift file's name ends with .thrift. """
        for src in srcs:
            if not src.endswith('.thrift'):
                self.error_exit('Invalid thrift file %s' % src)

    def _thrift_gen_cpp_files(self, src):
        """Get the c++ files generated from thrift file. """
        files = []
        for f in self.thrift_helpers[src].get_generated_cpp_files():
            files.append(self._target_file_path(f))
        return files

    def _thrift_gen_py_files(self, src):
        """Get the python files generated from thrift file. """
        files = []
        for f in self.thrift_helpers[src].get_generated_py_files():
            files.append(self._target_file_path(f))
        return files

    def _thrift_gen_java_files(self, src):
        """Get the java files generated from thrift file. """
        files = []
        for f in self.thrift_helpers[src].get_generated_java_files():
            files.append(self._target_file_path(f))
        return files

    def ninja_rules(self):
        if not self.srcs:
            return
        target_dir = os.path.join(self.build_dir, self.path)
        sources, headers = [], []
        for src in self.srcs:
            thrift_files = self._thrift_gen_cpp_files(src)
            self.ninja_build('thrift', thrift_files, inputs=self._source_file_path(src))
            headers += [h for h in thrift_files if h.endswith('.h')]
            thrift_cpp_sources = [s for s in thrift_files if s.endswith('.cpp')]
            sources += [os.path.relpath(s, target_dir) for s in thrift_cpp_sources]
        self.data['generated_hdrs'] = headers
        self._cc_objects_ninja(sources, True, generated_headers=headers)
        self._cc_library_ninja()


def thrift_library(
        name,
        srcs=[],
        deps=[],
        visibility=None,
        optimize=[],
        deprecated=False,
        **kwargs):
    """thrift_library target. """
    thrift_library_target = ThriftLibrary(
            name=name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            optimize=optimize,
            deprecated=deprecated,
            kwargs=kwargs)
    build_manager.instance.register_target(thrift_library_target)


build_rules.register_function(thrift_library)
