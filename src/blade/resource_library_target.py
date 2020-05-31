# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""Define resource_library target
"""

from __future__ import absolute_import

import os

from blade import build_manager
from blade import build_rules
from blade.blade_util import regular_variable_name
from blade.cc_targets import CcTarget

class ResourceLibrary(CcTarget):
    """This class is used to generate C/C++ resource library rules."""

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 optimize,
                 extra_cppflags,
                 kwargs):
        """Init method.

        Init the cc target.

        """
        super(ResourceLibrary, self).__init__(
                name=name,
                type='resource_library',
                srcs=srcs,
                deps=deps,
                visibility=None,
                warning='',
                defs=[],
                incs=[],
                export_incs=[],
                optimize=optimize,
                extra_cppflags=extra_cppflags,
                extra_linkflags=[],
                kwargs=kwargs)

    def ninja_rules(self):
        self._check_deprecated_deps()
        if not self.srcs:
            return

        resources = [self._source_file_path(s) for s in self.srcs]
        index = [self._target_file_path('%s.h' % self.name),
                 self._target_file_path('%s.c' % self.name)]
        self.ninja_build('resource_index', index, inputs=resources,
                         variables={
                             'name': regular_variable_name(self.name),
                             'path': self.path
                         })
        self.data['generated_hdrs'].append(index[0])
        sources = ['%s.c' % self.name]
        for resource in self.srcs:
            generated_source = '%s.c' % resource
            self.ninja_build('resource', self._target_file_path(generated_source),
                             inputs=self._source_file_path(resource))
            sources.append(generated_source)
        self._cc_objects_ninja(sources, True)
        self._cc_library_ninja()


def resource_library(name,
                     srcs=[],
                     deps=[],
                     optimize=[],
                     extra_cppflags=[],
                     **kwargs):
    """resource_library. """
    target = ResourceLibrary(
            name,
            srcs=srcs,
            deps=deps,
            optimize=optimize,
            extra_cppflags=extra_cppflags,
            kwargs=kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(resource_library)
