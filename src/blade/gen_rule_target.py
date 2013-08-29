# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the scons_gen_rule module which inherits the SconsTarget
 and generates related gen rule rules.

"""


import os

import blade
import build_rules
import java_jar_target
from blade_util import var_to_list
from target import Target


class GenRuleTarget(Target):
    """A scons gen rule target subclass.

    This class is derived from Target.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 outs,
                 cmd,
                 blade,
                 kwargs):
        """Init method.

        Init the gen rule target.

        """
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)
        outs = var_to_list(outs)

        Target.__init__(self,
                        name,
                        'gen_rule',
                        srcs,
                        deps,
                        blade,
                        kwargs)

        self.data['outs'] = outs
        self.data['cmd'] = cmd

    def _srcs_list(self, path, srcs):
        """Returns srcs list. """
        return ','.join(['"%s"' % os.path.join(self.build_path, path, src)
            for src in srcs])

    def scons_rules(self):
        """scons_rules.

        Description
        -----------
        It outputs the scons rules according to user options.

        """
        self._clone_env()

        # Build java source according to its option
        env_name = self._env_name()
        var_name = self._generate_variable_name(self.path, self.name)

        srcs_str = ''
        if not self.srcs:
            srcs_str = 'time_value'
        else:
            srcs_str = self._srcs_list(self.path, self.srcs)
        cmd = self.data['cmd']
        cmd = cmd.replace('$SRCS', '$SOURCES')
        cmd = cmd.replace('$OUTS', '$TARGETS')
        cmd = cmd.replace('$FIRST_SRC', '$SOURCE')
        cmd = cmd.replace('$FIRST_OUT', '$TARGET')
        cmd = cmd.replace('$BUILD_DIR', self.build_path)
        self._write_rule('%s = %s.Command([%s], [%s], "%s")' % (
                var_name,
                env_name,
                self._srcs_list(self.path, self.data['outs']),
                srcs_str,
                cmd))

        self.var_name = var_name
        self._generate_target_explict_dependency(var_name)

        targets = self.blade.get_build_targets()
        dep_var_list = []
        dep_skip_list = ['system_library', 'prebuilt_cc_library']
        for i in self.expanded_deps:
            dep_target = targets[i]
            if dep_target.type in dep_skip_list:
                continue
            elif dep_target.type == 'swig_library':
                dep_var_name = self._generate_variable_name(
                        dep_target.path, dep_target.name, 'dynamic_py')
                dep_var_list.append(dep_var_name)
                dep_var_name = self._generate_variable_name(
                        dep_target.path, dep_target.name, 'dynamic_java')
                dep_var_list.append(dep_var_name)
            elif dep_target.type == 'java_jar':
                dep_var_list += dep_target.data.get('java_jars', [])
            else:
                dep_var_name = self._generate_variable_name(
                        dep_target.path, dep_target.name)
                dep_var_list.append(dep_var_name)

        for dep_var_name in dep_var_list:
            self._write_rule('%s.Depends(%s, %s)' % (env_name,
                                                     var_name,
                                                     dep_var_name))


def gen_rule(name,
             srcs=[],
             deps=[],
             outs=[],
             cmd='',
             **kwargs):
    """scons_gen_rule. """
    gen_rule_target = GenRuleTarget(name,
                                    srcs,
                                    deps,
                                    outs,
                                    cmd,
                                    blade.blade,
                                    kwargs)
    blade.blade.register_target(gen_rule_target)


build_rules.register_function(gen_rule)
