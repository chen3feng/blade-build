# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""

This is python targets module which generates python egg,
python library, python binary, python test.

"""


import os

import blade
import build_rules
import console

from blade_util import var_to_list
from target import Target


class PythonEgg(Target):
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
                        None,
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
    target = PythonEgg(name,
                       srcs,
                       deps,
                       prebuilt,
                       blade.blade,
                       kwargs)
    blade.blade.register_target(target)


build_rules.register_function(py_egg)


class PythonTarget(Target):
    """python target base class.

    """
    def __init__(self,
                 name,
                 type,
                 srcs,
                 deps,
                 base,
                 visibility,
                 kwargs):
        """Init method. """
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)

        Target.__init__(self,
                        name,
                        type,
                        srcs,
                        deps,
                        visibility,
                        blade.blade,
                        kwargs)

        if base:
            if not base.startswith('//'):
                console.error_exit('%s: Invalid base directory %s. Option base should '
                                   'be a directory starting with \'//\' from BLADE_ROOT directory.' %
                                   (self.fullname, base))
            self.data['python_base'] = base[2:]
        self.data['python_sources'] = [self._source_file_path(s) for s in srcs]

    def _prepare_to_generate_rule(self):
        self._clone_env()
        env_name = self._env_name()
        self._write_rule('%s.Replace(BUILD_DIR="%s")' % (
            env_name, self.build_path))
        self._write_rule('%s.Replace(BASE_DIR="%s")' % (
            env_name, self.data.get('python_base', '')))


class PythonLibrary(PythonTarget):
    """A python library target subclass.

    This class is derived from SconsTarget and generates python library package.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 base,
                 visibility,
                 kwargs):
        """Init method. """
        PythonTarget.__init__(self,
                              name,
                              'py_library',
                              srcs,
                              deps,
                              base,
                              visibility,
                              kwargs)

    def scons_rules(self):
        """scons_rules.

        Description
        -----------
        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()
        env_name = self._env_name()
        var_name = self._var_name()

        sources = self.data.get('python_sources', [])
        if sources:
            self._write_rule('%s = %s.PythonLibrary("%s", %s)' % (
                             var_name, env_name,
                             '%s.pylib' % self._target_file_path(),
                             sources))
            self.data['python_var'] = var_name
            dep_var_list = []
            targets = self.blade.get_build_targets()
            for dep in self.deps:
                var = targets[dep].data.get('python_var')
                if var:
                    dep_var_list.append(var)

            for dep_var in dep_var_list:
                self._write_rule('%s.Depends(%s, %s)' % (
                                 env_name, var_name, dep_var))


def py_library(name,
               srcs=[],
               deps=[],
               base=None,
               visibility=None,
               **kwargs):
    """python library. """
    target = PythonLibrary(name,
                           srcs,
                           deps,
                           base,
                           visibility,
                           kwargs)
    blade.blade.register_target(target)


build_rules.register_function(py_library)


class PythonBinary(PythonTarget):
    """A python binary target subclass.

    This class is derived from SconsTarget and generates python binary package.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 main,
                 base,
                 kwargs):
        """Init method. """
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)

        PythonTarget.__init__(self,
                              name,
                              'py_binary',
                              srcs,
                              deps,
                              base,
                              None,
                              kwargs)

        self.data['run_in_shell'] = True
        if main:
            self.data['main'] = main
        else:
            if len(srcs) == 1:
                self.data['main'] = srcs[0]
            else:
                console.error_exit(
                    '%s: The entry file must be specified by the "main" '
                    'argument if there are more than one srcs' % self.fullname)

    def _get_entry(self):
        main = self.data['main']
        full_path = os.path.normpath(os.path.join(self.path, main))[:-3]
        base_path = self.data.get('python_base', '')
        rel_path = os.path.relpath(full_path, base_path)
        return rel_path.replace('/', '.')

    def scons_rules(self):
        """scons_rules.

        Description
        -----------
        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()
        env_name = self._env_name()
        var_name = self._var_name()

        self._write_rule('%s.Append(ENTRY="%s")' % (env_name, self._get_entry()))
        targets = self.blade.get_build_targets()
        sources = self.data.get('python_sources', [])
        dep_var_list = []
        for dep in self.expanded_deps:
            python_var = targets[dep].data.get('python_var')
            if python_var:
                dep_var_list.append(python_var)

        self._write_rule('%s = %s.PythonBinary("%s", %s + [%s])' % (
                         var_name,
                         env_name,
                         self._target_file_path(),
                         sources, ','.join(dep_var_list)))


def py_binary(name,
              srcs=[],
              deps=[],
              main=None,
              base=None,
              **kwargs):
    """python binary. """
    target = PythonBinary(name,
                          srcs,
                          deps,
                          main,
                          base,
                          kwargs)
    blade.blade.register_target(target)


build_rules.register_function(py_binary)


class PythonTest(PythonBinary):
    """A python test target subclass.

    This class is derived from SconsTarget and generates python test.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 main,
                 base,
                 testdata,
                 kwargs):
        """Init method. """
        PythonBinary.__init__(self,
                              name,
                              srcs,
                              deps,
                              main,
                              base,
                              kwargs)
        self.type = 'py_test'
        self.data['testdata'] = testdata


def py_test(name,
            srcs=[],
            deps=[],
            main=None,
            base=None,
            testdata=[],
            **kwargs):
    """python test. """
    target = PythonTest(name,
                        srcs,
                        deps,
                        main,
                        base,
                        testdata,
                        kwargs)
    blade.blade.register_target(target)


build_rules.register_function(py_test)
