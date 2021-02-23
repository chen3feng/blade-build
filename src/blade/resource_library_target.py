# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""
Define resource_library target.
"""

from __future__ import absolute_import
from __future__ import print_function

from blade import build_manager
from blade import build_rules
from blade import cc_targets
from blade.util import regular_variable_name


class ResourceLibrary(cc_targets.CcTarget):
    """This class is used to generate C/C++ resource library rules."""

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
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
                src_exts=None,
                deps=deps,
                visibility=visibility,
                warning='',
                defs=[],
                incs=[],
                export_incs=[],
                optimize=optimize,
                extra_cppflags=extra_cppflags,
                extra_linkflags=[],
                kwargs=kwargs)
        hdr = '%s.h' % self.name
        self.attr['generated_hdrs'] = [self._target_file_path(hdr)]
        self._set_hdrs([hdr])

    def generate(self):
        self._check_deprecated_deps()
        if not self.srcs:
            return

        resources = [self._source_file_path(s) for s in self.srcs]
        index = [self._target_file_path('%s.h' % self.name),
                 self._target_file_path('%s.c' % self.name)]
        self.generate_build('resource_index', index, inputs=resources,
                            variables={
                                'name': regular_variable_name(self.name),
                                'path': self.path
                            })
        sources = ['%s.c' % self.name]
        for resource in self.srcs:
            generated_source = '%s.c' % resource
            self.generate_build('resource', self._target_file_path(generated_source),
                                inputs=self._source_file_path(resource))
            sources.append(generated_source)
        objs = self._generated_cc_objects(sources)
        self._cc_library(objs)


def resource_library(name=None,
                     srcs=[],
                     deps=[],
                     visibility=None,
                     optimize=None,
                     extra_cppflags=[],
                     **kwargs):
    """resource_library."""
    target = ResourceLibrary(
            name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            optimize=optimize,
            extra_cppflags=extra_cppflags,
            kwargs=kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(resource_library)
