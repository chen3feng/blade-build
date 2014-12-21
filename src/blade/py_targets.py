# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is python egg target which generates python egg for user.

"""


import os

import blade
import build_rules
import console

from blade_util import var_to_list
from target import Target


class PythonEggTarget(Target):
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
                        'py_egg',
                        srcs,
                        deps,
                        blade,
                        kwargs)

        if prebuilt:
            self.type = 'prebuilt_py_egg'

    def scons_rules(self):
        """scons_rules.

        Description
        -----------
        It outputs the scons rules according to user options.

        """
        self._clone_env()

        if self.type == 'prebuilt_py_egg':
            return

        env_name = self._env_name()

        setup_file = os.path.join(self.path, 'setup.py')
        python_package = os.path.join(self.path, self.name)
        init_file = os.path.join(python_package, '__init__.py')

        binary_files = []
        if os.path.exists(setup_file):
            binary_files.append(setup_file)

        if not os.path.exists(init_file):
            console.error_exit('The __init__.py not existed in %s' % python_package)
        binary_files.append(init_file)

        dep_var_list = []
        targets = self.blade.get_build_targets()
        for dep in self.expanded_deps:
            binary_files += targets[dep].data.get('python_sources', [])
            dep_var_list += targets[dep].data.get('python_vars', [])

        target_egg_file = '%s.egg' % self._target_file_path()
        python_binary_var = '%s_python_binary_var' % (self._var_name())
        self._write_rule('%s = %s.PythonEgg(["%s"], %s)' % (
                          python_binary_var,
                          env_name,
                          target_egg_file,
                          binary_files))
        for var in dep_var_list:
            self._write_rule('%s.Depends(%s, %s)' % (
                             env_name, python_binary_var, var))


def py_egg(name,
           srcs=[],
           deps=[],
           prebuilt=False,
           **kwargs):
    """python egg. """
    target = PythonEggTarget(name,
                             srcs,
                             deps,
                             prebuilt,
                             blade.blade,
                             kwargs)
    blade.blade.register_target(target)


build_rules.register_function(py_egg)


class PythonLibraryTarget(Target):
    """A python library target subclass.

    This class is derived from SconsTarget and generates python library package.

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
                        'py_library',
                        srcs,
                        deps,
                        blade,
                        kwargs)

        if prebuilt:
            self.type = 'prebuilt_py_library'

    def scons_rules(self):
        """scons_rules.

        Description
        -----------
        It outputs the scons rules according to user options.

        """
        self._clone_env()

        if self.type == 'prebuilt_py_library':
            return

        env_name = self._env_name()

        dep_var_list = []
        self.targets = self.blade.get_build_targets()
        for dep in self.expanded_deps:
            binary_files += targets[dep].data.get('python_sources', [])
            dep_var_list += targets[dep].data.get('python_vars', [])

        target_library_file = '%s.library' % self._target_file_path()
        python_binary_var = '%s_python_binary_var' % (self._var_name())
        self._write_rule('%s = %s.PythonLibrary(["%s"], %s)' % (
                          python_binary_var,
                          env_name,
                          target_library_file,
                          binary_files))
        for var in dep_var_list:
            self._write_rule('%s.Depends(%s, %s)' % (
                             env_name, python_binary_var, var))


def py_library(name,
               srcs=[],
               deps=[],
               prebuilt=False,
               **kwargs):
    """python library. """
    target = PythonLibraryTarget(name,
                                 srcs,
                                 deps,
                                 prebuilt,
                                 blade.blade,
                                 kwargs)
    blade.blade.register_target(target)


build_rules.register_function(py_library)
