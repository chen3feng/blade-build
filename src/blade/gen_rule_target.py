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
import console
from blade_util import var_to_list
from blade_util import location_re
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
                        None,
                        blade,
                        kwargs)

        self.data['outs'] = outs
        self.data['locations'] = []
        self.data['cmd'] = location_re.sub(self._process_location_reference, cmd)

    def _srcs_list(self, path, srcs):
        """Returns srcs list. """
        return ','.join(['"%s"' % os.path.join(self.build_path, path, src)
            for src in srcs])

    def _process_location_reference(self, m):
        """Process target location reference in the command. """
        key, type = self._add_location_reference_target(m)
        self.data['locations'].append((key, type))
        return '%s'

    def _generate_header_files(self):
        """Whether this target generates header files during building."""
        # Be conservative: Assume gen_rule always generates header files.
        return True

    def _allow_duplicate_source(self):
        return True

    def scons_rules(self):
        """scons_rules.

        Description
        -----------
        It outputs the scons rules according to user options.

        """
        self._clone_env()

        env_name = self._env_name()
        var_name = self._var_name()
        targets = self.blade.get_build_targets()

        srcs_str = ''
        if self.srcs:
            srcs_str = self._srcs_list(self.path, self.srcs)
        elif self.expanded_deps:
            srcs_str = ''
        else:
            srcs_str = 'time_value'
        cmd = self.data['cmd']
        cmd = cmd.replace('$SRCS', '$SOURCES')
        cmd = cmd.replace('$OUTS', '$TARGETS')
        cmd = cmd.replace('$FIRST_SRC', '$SOURCE')
        cmd = cmd.replace('$FIRST_OUT', '$TARGET')
        cmd = cmd.replace('$BUILD_DIR', self.build_path)
        locations = self.data['locations']
        if locations:
            target_vars = []
            for key, type in locations:
                target_var = targets[key]._get_target_var(type)
                if not target_var:
                    console.error_exit('%s: Invalid location reference %s %s' %
                            (self.fullname, ':'.join(key), type))
                target_vars.append(target_var)
            cmd = '"%s" %% (%s)' % (cmd, ','.join(['str(%s[0])' % v for v in target_vars]))
        else:
            cmd = '"%s"' % cmd
        self._write_rule('%s = %s.Command([%s], [%s], '
                         '[%s, "@ls $TARGETS > /dev/null"])' % (
                         var_name,
                         env_name,
                         self._srcs_list(self.path, self.data['outs']),
                         srcs_str,
                         cmd))
        for i in range(len(self.data['outs'])):
            self._add_target_var('%s' % i, '%s[%s]' % (var_name, i))

        # TODO(phongchen): add Target.get_all_vars
        dep_var_list = []
        dep_skip_list = ['system_library', 'prebuilt_cc_library']
        for i in self.expanded_deps:
            dep = targets[i]
            if dep.type in dep_skip_list:
                continue

            if dep.type == 'swig_library':
                dep_var_name = dep._var_name('dynamic_py')
                dep_var_list.append(dep_var_name)
                dep_var_name = dep._var_name('dynamic_java')
                dep_var_list.append(dep_var_name)
            else:
                dep_var_list += dep._get_target_vars()

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
