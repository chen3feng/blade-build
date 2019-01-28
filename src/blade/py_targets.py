# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""

This is python targets module which generates python egg,
python library, python binary, python test.

"""

from __future__ import absolute_import

import os

from blade import build_manager
from blade import build_rules
from blade import console
from blade.blade_util import var_to_list
from blade.target import Target


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
                       build_manager.instance,
                       kwargs)
    build_manager.instance.register_target(target)


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
                        build_manager.instance,
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

    def _expand_deps_generation(self):
        build_targets = self.blade.get_build_targets()
        for dep in self.expanded_deps:
            d = build_targets[dep]
            d.data['generate_python'] = True

    def ninja_vars(self):
        vars = {}
        basedir = self.data.get('python_base')
        if basedir:
            vars['pythonbasedir'] = basedir
        return vars


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

    def _scons_pylib(self):
        env_name = self._env_name()
        var_name = self._var_name('pylib')

        sources = self.data.get('python_sources', [])
        if not sources:
            return ''
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
        return var_name

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._scons_pylib()

    def _ninja_pylib(self):
        if not self.srcs:
            return ''
        output = self._target_file_path() + '.pylib'
        inputs = [self._source_file_path(s) for s in self.srcs]
        vars = self.ninja_vars()
        self.ninja_build(output, 'pythonlibrary', inputs=inputs, variables=vars)
        self._add_target_file('pylib', output)
        return output

    def ninja_rules(self):
        self._ninja_pylib()


class PrebuiltPythonLibrary(PythonTarget):
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
                              'prebuilt_py_library',
                              srcs,
                              deps,
                              base,
                              visibility,
                              kwargs)
        if base:
            console.error_exit("%s: Prebuilt py_library doesn't support base" %
                               self.fullname)
        if len(self.srcs) != 1:
            console.error_exit('%s: There can only be 1 file in prebuilt py_library' %
                               self.fullname)
        src = self.srcs[0]
        if not src.endswith('.egg') and not src.endswith('.whl'):
            console.error_exit(
                '%s: Invalid file %s in srcs, prebuilt py_library only support egg and whl' %
                (self.fullname, src))

    def scons_rules(self):
        self._prepare_to_generate_rule()
        env_name = self._env_name()
        var_name = self._var_name('pylib')

        self._write_rule('%s = %s.File("%s")' % (
                         var_name, env_name,
                         self._source_file_path(self.srcs[0])))
        self.data['python_var'] = var_name

    def ninja_rules(self):
        self._add_target_file('pylib', self._source_file_path(self.srcs[0]))


def py_library(name,
               srcs=[],
               deps=[],
               base=None,
               prebuilt=None,
               visibility=None,
               **kwargs):
    """python library. """
    # pylint: disable=redefined-variable-type
    if prebuilt:
        target = PrebuiltPythonLibrary(name,
                                       srcs,
                                       deps,
                                       base,
                                       visibility,
                                       kwargs)
    else:
        target = PythonLibrary(name,
                               srcs,
                               deps,
                               base,
                               visibility,
                               kwargs)

    build_manager.instance.register_target(target)


build_rules.register_function(py_library)


class PythonBinary(PythonLibrary):
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

        PythonLibrary.__init__(self,
                               name,
                               srcs,
                               deps,
                               base,
                               None,
                               kwargs)

        self.type = 'py_binary'
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
        self._prepare_to_generate_rule()
        env_name = self._env_name()
        var_name = self._var_name()

        self_pylib = self._scons_pylib()
        dep_var_list = [self_pylib] if self_pylib else []

        self._write_rule('%s.Append(ENTRY="%s")' % (env_name, self._get_entry()))
        targets = self.blade.get_build_targets()
        for dep in self.expanded_deps:
            python_var = targets[dep].data.get('python_var')
            if python_var:
                dep_var_list.append(python_var)

        self._write_rule('%s = %s.PythonBinary("%s", [%s])' % (
                         var_name,
                         env_name,
                         self._target_file_path(),
                         ','.join(dep_var_list)))

    def ninja_rules(self):
        output = self._target_file_path()
        pylib = self._ninja_pylib()
        inputs = [pylib] if pylib else []
        targets = self.blade.get_build_targets()
        for key in self.expanded_deps:
            dep = targets[key]
            pylib = dep._get_target_file('pylib')
            if pylib:
                inputs.append(pylib)
            # TODO(wentingli): Add other dependencies if needed
        vars = self.ninja_vars()
        vars['mainentry'] = self._get_entry()
        self.ninja_build(output, 'pythonbinary', inputs=inputs, variables=vars)
        self._add_default_target_file('bin', output)


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
    build_manager.instance.register_target(target)


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
    build_manager.instance.register_target(target)


build_rules.register_function(py_test)
