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
from blade.cc_targets import CcTarget


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
                          None,
                          '',
                          [],
                          [],
                          [],
                          optimize,
                          extra_cppflags,
                          [],
                          blade,
                          kwargs)

    def _generate_header_files(self):
        """Whether this target generates header files during building."""
        return True

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()
        self._setup_cc_flags()

        env_name = self._env_name()
        (out_dir, res_file_index) = self._resource_library_rules_helper()
        self.data['res_srcs'] = [os.path.join(out_dir, res_file_index + '.c')]
        for src in self.srcs:
            src = os.path.normpath(src)
            src_path = os.path.join(self.path, src)
            c_src_name = '%s.c' % self._regular_variable_name(src)
            c_src_path = os.path.join(out_dir, c_src_name)
            v_src = self._var_name_of(src_path)
            self._write_rule('%s = %s.ResourceFile("%s", "%s")' % (
                         v_src, env_name, c_src_path, src_path))
            self.data['res_srcs'].append(c_src_path)

        self._resource_library_rules_objects()

        self._cc_library()

    def _resource_library_rules_objects(self):
        """Generate resource library object rules.  """
        env_name = self._env_name()
        objs_name = self._objs_name()

        objs = []
        res_srcs = self.data['res_srcs']
        res_objects = {}
        path = self.path
        for src in res_srcs:
            base_src_name = self._regular_variable_name(os.path.basename(src))
            src_name = base_src_name + '_' + self.name + '_res'
            if src_name not in res_objects:
                res_objects[src_name] = (
                        '%s_%s_object' % (
                                base_src_name,
                                self._regular_variable_name(self.name)))
                target_path = os.path.join(self.build_path,
                                           path,
                                           '%s.objs' % self.name,
                                           base_src_name)
                self._write_rule(
                        '%s = %s.SharedObject(target="%s" + top_env["OBJSUFFIX"]'
                        ', source="%s")' % (res_objects[src_name],
                                              env_name,
                                              target_path,
                                              src))
            objs.append(res_objects[src_name])
        self._write_rule('%s = [%s]' % (objs_name, ','.join(objs)))

    def _resource_library_rules_helper(self):
        """The helper method to generate scons resource rules, mainly applies builder.  """
        env_name = self._env_name()
        out_dir = os.path.join(self.build_path, self.path)
        res_index_name = self._regular_variable_name(self.name)
        res_index_source = res_index_name + '.c'
        res_index_header = res_index_name + '.h'

        src_list = []
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            src_list.append(src_path)

        v_index = self._var_name_of(self.name, 'index')
        res_index_header_path = os.path.join(out_dir, res_index_header)
        res_index_source_path = os.path.join(out_dir, res_index_source)
        self._write_rule('%s["SOURCE_PATH"] = "%s"' % (env_name, self.path))
        self._write_rule('%s["TARGET_NAME"] = "%s"' % (env_name, res_index_name))
        self._write_rule('%s = %s.ResourceIndex(["%s", "%s"], %s)' % (
                     v_index, env_name, res_index_source_path, res_index_header_path,
                     src_list))
        self.data['generated_hdrs'].append(res_index_header_path)

        return (out_dir, res_index_name)

    def ninja_rules(self):
        self._check_deprecated_deps()
        if not self.srcs:
            return

        resources = [self._source_file_path(s) for s in self.srcs]
        index = [self._target_file_path('%s.h' % self.name),
                 self._target_file_path('%s.c' % self.name)]
        self.ninja_build(index, 'resource_index', inputs=resources,
                         variables={
                             'name' : self._regular_variable_name(self.name),
                             'path' : self.path
                         })
        self.data['generated_hdrs'].append(index[0])
        sources = ['%s.c' % self.name]
        for resource in self.srcs:
            generated_source = '%s.c' % resource
            self.ninja_build(self._target_file_path(generated_source), 'resource',
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
    """scons_resource_library. """
    target = ResourceLibrary(name,
                             srcs,
                             deps,
                             optimize,
                             extra_cppflags,
                             build_manager.instance,
                             kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(resource_library)
