# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""Define resource_library target
"""


import os
import blade

import build_rules
import java_jar_target
import py_targets
from cc_targets import CcTarget


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
                          '',
                          [],
                          [],
                          [],
                          optimize,
                          extra_cppflags,
                          [],
                          blade,
                          kwargs)

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        env_name = self._env_name()
        (out_dir, res_file_name) = self._resource_library_rules_helper()

        self.data['res_srcs'] = []
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            src_base = os.path.basename(src_path)
            src_base_name = '%s.c' % self._regular_variable_name(src_base)
            new_src_path = os.path.join(out_dir, src_base_name)
            cmd_bld = '%s_bld' % self._regular_variable_name(new_src_path)
            self._write_rule('%s = %s.ResourceFile("%s", "%s")' % (
                         cmd_bld, env_name, new_src_path, src_path))
            self.data['res_srcs'].append(new_src_path)

        self._resource_library_rules_objects()

        self._cc_library()

        options = self.blade.get_options()
        if (getattr(options, 'generate_dynamic', False) or
            self.data.get('build_dynamic')):
            self._dynamic_cc_library()

    def _resource_library_rules_objects(self):
        """Generate resource library object rules.  """
        env_name = self._env_name()
        objs_name = self._objs_name()

        self._setup_cc_flags()

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
        res_name = self._regular_variable_name(self.name)
        res_file_name = res_name
        res_file_header = res_file_name + '.h'
        res_header_path = os.path.join(out_dir, res_file_header)

        src_list = []
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            src_list.append(src_path)

        cmd_bld = '%s_header_cmd_bld' % res_name
        self._write_rule('%s = %s.ResourceHeader("%s", %s)' % (
                     cmd_bld, env_name, res_header_path, src_list))

        return (out_dir, res_file_name)


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
                             blade.blade,
                             kwargs)
    blade.blade.register_target(target)


build_rules.register_function(resource_library)
