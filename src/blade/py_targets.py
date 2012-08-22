"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is python egg target which generates python egg for user.

"""


import os
import blade
import blade_util
from blade_util import error_exit
from blade_util import var_to_list
from target import Target


class PythonBinaryTarget(Target):
    """A python egg target subclass.

    This class is derived from SconsTarget and generates python egg package.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 prebuilt,
                 blade,
                 kwargs):
        """Init method. """
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)

        Target.__init__(self,
                        name,
                        'py_binary',
                        srcs,
                        deps,
                        blade,
                        kwargs)

        if prebuilt:
            self.data['type'] = 'prebuilt_py_binary'

    def _clone_env(self):
        """override _clone_env(). """
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

        if self.data['type'] == 'prebuilt_py_binary':
            return

        env_name = self._env_name()

        setup_file = os.path.join(self.data['path'], "setup.py")
        python_package = os.path.join(self.data['path'], self.data['name'])
        init_file = os.path.join(python_package, '__init__.py')

        binary_files = []
        if os.path.exists(setup_file):
            binary_files.append(setup_file)

        if not os.path.exists(init_file):
            error_exit("The __init__.py not existed in %s" % python_package)
        binary_files.append(init_file)

        dep_var_list = []
        self.targets = self.blade.get_all_targets_expanded()
        for dep in self.targets[self.key]['deps']:
            if dep in self.blade.python_binary_dep_source_map.keys():
                for f in self.blade.python_binary_dep_source_map[dep]:
                    binary_files.append(f)
                for cmd in self.blade.python_binary_dep_source_cmd[dep]:
                    dep_var_list.append(cmd)

        target_egg_file = "%s.egg" % self._target_file_path()
        python_binary_var = "%s_python_binary_var" % (
            self._generate_variable_name(self.data['path'], self.data['name']))
        self._write_rule("%s = %s.PythonBinary(['%s'], %s)" % (
                          python_binary_var,
                          env_name,
                          target_egg_file,
                          binary_files))
        for var in dep_var_list:
            self._write_rule("%s.Depends(%s, %s)" % (
                             env_name, python_binary_var, var))

def py_binary(name,
              srcs=[],
              deps=[],
              prebuilt=False,
              **kwargs):
    """python binary - aka, python egg. """
    target = PythonBinaryTarget(name,
                                srcs,
                                deps,
                                prebuilt,
                                blade.blade,
                                kwargs)
    blade.blade.register_scons_target(target.key, target)
