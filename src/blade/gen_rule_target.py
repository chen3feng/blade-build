# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""General Build Rule
Allow users defining their custom build rules.
"""

from __future__ import absolute_import

import os

from blade import build_manager
from blade import build_rules
from blade import console
from blade.blade_util import regular_variable_name
from blade.blade_util import var_to_list
from blade.target import Target, LOCATION_RE


class GenRuleTarget(Target):
    """General Rule Target"""

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 outs,
                 cmd,
                 cmd_name,
                 generate_hdrs,
                 heavy,
                 kwargs):
        """Init method.
        Init the gen rule target.
        """
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)
        outs = var_to_list(outs)

        super(GenRuleTarget, self).__init__(
                name=name,
                type='gen_rule',
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                kwargs=kwargs)

        self.data['outs'] = outs
        self.data['locations'] = []
        self.data['cmd'] = LOCATION_RE.sub(self._process_location_reference, cmd)
        self.data['cmd_name'] = cmd_name
        if generate_hdrs is not None:
            self.data['generate_hdrs'] = generate_hdrs
        self.data['heavy'] = heavy

    def _srcs_list(self, path, srcs):
        """Returns srcs list. """
        return ','.join(['"%s"' % os.path.join(self.build_dir, path, src)
                         for src in srcs])

    def _process_location_reference(self, m):
        """Process target location reference in the command. """
        key, type = self._add_location_reference_target(m)
        self.data['locations'].append((key, type))
        return '%s'

    def _allow_duplicate_source(self):
        return True

    def ninja_command(self):
        cmd = self.data['cmd']
        cmd = cmd.replace('$SRCS', '${in}')
        cmd = cmd.replace('$OUTS', '${out}')
        cmd = cmd.replace('$FIRST_SRC', '${_in_1}')
        cmd = cmd.replace('$FIRST_OUT', '${_out_1}')
        cmd = cmd.replace('$SRC_DIR', self.path)
        cmd = cmd.replace('$OUT_DIR', os.path.join(self.build_dir, self.path))
        cmd = cmd.replace('$BUILD_DIR', self.build_dir)
        locations = self.data['locations']
        if locations:
            targets = self.blade.get_build_targets()
            locations_paths = []
            for key, label in locations:
                path = targets[key]._get_target_file(label)
                if not path:
                    self.error_exit('Invalid location reference %s %s' % (':'.join(key), label))
                locations_paths.append(path)
            cmd = cmd % tuple(locations_paths)
        return cmd

    def implicit_dependencies(self):
        targets = self.blade.get_build_targets()
        implicit_deps = []
        for dep in self.expanded_deps:
            implicit_deps += targets[dep]._get_target_files()
        return implicit_deps

    def _expand_srcs(self):
        result = []
        for s in self.srcs:
            src = self._source_file_path(s)
            if os.path.exists(src):
                result.append(src)
            else:
                result.append(self._target_file_path(s))
        return result

    def ninja_rules(self):
        rule = '%s__rule__' % regular_variable_name(self._source_file_path(self.name))
        cmd = self.ninja_command()
        description = console.colored('%s //%s' % (self.data['cmd_name'], self.fullname), 'dimpurple')
        self._write_rule('''rule %s
  command = %s && cd %s && ls ${out} > /dev/null
  description = %s
''' % (rule, cmd, self.blade.get_root_dir(), description))
        outputs = [self._target_file_path(o) for o in self.data['outs']]
        inputs = self._expand_srcs()
        vars = {}
        if '${_in_1}' in cmd:
            vars['_in_1'] = inputs[0]
        if '${_out_1}' in cmd:
            vars['_out_1'] = outputs[0]
        if self.data['heavy']:
            vars['pool'] = 'heavy_pool'
        self.ninja_build(rule, outputs, inputs=inputs, implicit_deps=self.implicit_dependencies(),
                         variables=vars)
        for i, out in enumerate(outputs):
            self._add_target_file(str(i), out)
        self.data['generated_hdrs'] = [o for o in outputs if o.endswith('.h')]


def gen_rule(
        name,
        srcs=[],
        deps=[],
        visibility=None,
        outs=[],
        cmd='',
        cmd_name='COMMAND',
        generate_hdrs=None,
        heavy=False,
        **kwargs):
    """General Build Rule
    Args:
        generate_hdrs: Optional[bool]:
            Specify whether this target will generate c/c++ header files.
            Defaultly, gen_rule will calculate a generated header files list automatically
            according to the names in the |outs|`
            But if they are not specified in the outs, and we sure know this target will generate
            some headers, we should set this argument to True.
        heavy: bool: Whether this target is a heavy target, which means it will cost many cpu/memory
    """
    gen_rule_target = GenRuleTarget(
            name=name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            outs=outs,
            cmd=cmd,
            cmd_name=cmd_name,
            generate_hdrs=generate_hdrs,
            heavy=heavy,
            kwargs=kwargs)
    build_manager.instance.register_target(gen_rule_target)


build_rules.register_function(gen_rule)
