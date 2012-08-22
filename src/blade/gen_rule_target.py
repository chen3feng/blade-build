"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the scons_gen_rule module which inherits the SconsTarget
 and generates related gen rule rules.

"""


import os
import blade
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
        return ','.join(["'%s'" % os.path.join(self.build_path, path, src) for src in srcs])

    def _clone_env(self):
        """override _clone_env. """
        env_name = self._env_name()
        self._write_rule("%s = env.Clone()" % env_name)

    def scons_rules(self):
        """scons_rules.

        Parameters
        -----------
        None

        Returns
        -----------
        None

        Description
        -----------
        It outputs the scons rules according to user options.

        """
        self._clone_env()

        # Build java source according to its option
        env_name = self._env_name()
        var_name = self._generate_variable_name(self.data['path'], self.data['name'])

        srcs_str = ""
        if not self.data['srcs']:
            srcs_str = 'time_value'
        else:
            srcs_str = self._srcs_list(self.data['path'], self.data['srcs'])
        cmd = self.data['cmd']
        cmd = cmd.replace("$SRCS", '$SOURCES')
        cmd = cmd.replace("$OUTS", '$TARGETS')
        cmd = cmd.replace("$FIRST_SRC", '$SOURCE')
        cmd = cmd.replace("$FIRST_OUT", '$TARGET')
        cmd = cmd.replace("$BUILD_DIR", self.build_path)
        self._write_rule('%s = %s.Command([%s], [%s], "%s")' % (
                var_name,
                env_name,
                self._srcs_list(self.data['path'], self.data['outs']),
                srcs_str,
                cmd))

        gen_rule_files_map = self.blade.get_gen_rule_files_map()
        gen_rule_files_map[(self.data['path'], self.data['name'])] = var_name
        self._generate_target_explict_dependency(var_name)

        self.targets = self.blade.get_all_targets_expanded()
        self.java_jars_map = self.blade.get_java_jars_map()
        dep_var_list = []
        dep_skip_list = ['system_library', 'prebuilt_cc_library']
        for i in self.data['deps']:
            dep_target = self.targets[i]
            if dep_target['type'] in dep_skip_list:
                continue
            elif dep_target['type'] == 'swig_library':
                dep_var_name = self._generate_variable_name(
                        dep_target['path'], dep_target['name'], 'dynamic_py')
                dep_var_list.append(dep_var_name)
                dep_var_name = self._generate_variable_name(
                        dep_target['path'], dep_target['name'], 'dynamic_java')
                dep_var_list.append(dep_var_name)
            elif dep_target['type'] == 'java_jar':
                dep_var_list += self.java_jars_map.get(dep_target['name'], [])
            else:
                dep_var_name = self._generate_variable_name(
                        dep_target['path'], dep_target['name'])
                dep_var_list.append(dep_var_name)

        for dep_var_name in dep_var_list:
            self._write_rule("%s.Depends(%s, %s)" % (env_name,
                                                     var_name,
                                                     dep_var_name))


def gen_rule(name,
             srcs=[],
             deps=[],
             outs=[],
             cmd="",
             **kwargs):
   """scons_gen_rule. """
   gen_rule_target = GenRuleTarget(name,
                                   srcs,
                                   deps,
                                   outs,
                                   cmd,
                                   blade.blade,
                                   kwargs)
   blade.blade.register_scons_target(gen_rule_target.key, gen_rule_target)

