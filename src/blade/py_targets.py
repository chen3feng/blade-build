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

        super(PythonTarget, self).__init__(
            name=name,
            type=type,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            kwargs=kwargs)

        if base:
            if not base.startswith('//'):
                self.error_exit('Invalid base directory %s. Option base should be a directory '
                                'starting with \'//\' from BLADE_ROOT directory.' % base)
            self.data['python_base'] = base[2:]
        self.data['python_sources'] = [self._source_file_path(s) for s in srcs]

    def _expand_deps_generation(self):
        build_targets = self.blade.get_build_targets()
        for dep in self.expanded_deps:
            d = build_targets[dep]
            d.data['generate_python'] = True

    def ninja_vars(self):
        vars = {}
        basedir = self.data.get('python_base')
        if basedir:
            vars['basedir'] = basedir
        return vars


class PythonLibrary(PythonTarget):
    """A python library target subclass.
    This class generates python library package.
    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 base,
                 visibility,
                 kwargs):
        """Init method. """
        super(PythonLibrary, self).__init__(
                name=name,
                type='py_library',
                srcs=srcs,
                deps=deps,
                base=base,
                visibility=visibility,
                kwargs=kwargs)

    def _ninja_pylib(self):
        if not self.srcs:
            return ''
        output = self._target_file_path(self.name + '.pylib')
        inputs = [self._source_file_path(s) for s in self.srcs]
        vars = self.ninja_vars()
        self.ninja_build('pythonlibrary', output, inputs=inputs, variables=vars)
        self._add_target_file('pylib', output)
        return output

    def ninja_rules(self):
        self._ninja_pylib()


class PrebuiltPythonLibrary(PythonTarget):
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 base,
                 kwargs):
        """Init method. """
        super(PrebuiltPythonLibrary, self).__init__(
                name=name,
                type='prebuilt_py_library',
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                base=base,
                kwargs=kwargs)
        if base:
            self.error_exit("Prebuilt py_library doesn't support base")
        if len(self.srcs) != 1:
            self.error_exit('There can only be 1 file in prebuilt py_library')
        src = self.srcs[0]
        if not src.endswith('.egg') and not src.endswith('.whl'):
            console.error_exit(
                '%s: Invalid file "%s" in srcs, prebuilt py_library only support egg and whl' %
                (self.fullname, src))

    def ninja_rules(self):
        self._add_target_file('pylib', self._source_file_path(self.srcs[0]))


def py_library(name,
               srcs=[],
               deps=[],
               visibility=None,
               base=None,
               prebuilt=None,
               **kwargs):
    """python library. """
    # pylint: disable=redefined-variable-type
    if prebuilt:
        target = PrebuiltPythonLibrary(
                name=name,
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                base=base,
                kwargs=kwargs)
    else:
        target = PythonLibrary(
                name=name,
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                base=base,
                kwargs=kwargs)

    build_manager.instance.register_target(target)


build_rules.register_function(py_library)


class PythonBinary(PythonLibrary):
    """A python binary target subclass.
    This class generates python binary package.
    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 main,
                 base,
                 kwargs):
        """Init method. """
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)

        super(PythonBinary, self).__init__(
                name=name,
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                base=base,
                kwargs=kwargs)

        self.type = 'py_binary'
        self.data['run_in_shell'] = True
        if main:
            self.data['main'] = main
        else:
            if len(srcs) == 1:
                self.data['main'] = srcs[0]
            else:
                self.error_exit(
                    'The entry file must be specified by the "main" '
                    'argument if there are more than one srcs')

    def _get_entry(self):
        main = self.data['main']
        full_path = os.path.normpath(os.path.join(self.path, main))[:-3]
        base_path = self.data.get('python_base', '')
        rel_path = os.path.relpath(full_path, base_path)
        return rel_path.replace('/', '.')

    def ninja_rules(self):
        output = self._target_file_path(self.name)
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
        self.ninja_build('pythonbinary', output, inputs=inputs, variables=vars)
        self._add_default_target_file('bin', output)


def py_binary(name,
              srcs=[],
              deps=[],
              visibility=None,
              main=None,
              base=None,
              **kwargs):
    """python binary. """
    target = PythonBinary(
            name=name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            main=main,
            base=base,
            kwargs=kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(py_binary)


class PythonTest(PythonBinary):
    """A python test target subclass.
    This class generates python test.
    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 main,
                 base,
                 testdata,
                 kwargs):
        """Init method. """
        super(PythonTest, self).__init__(
                name=name,
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                main=main,
                base=base,
                kwargs=kwargs)
        self.type = 'py_test'
        self.data['testdata'] = testdata


def py_test(name,
            srcs=[],
            deps=[],
            visibility=None,
            main=None,
            base=None,
            testdata=[],
            **kwargs):
    """python test. """
    target = PythonTest(
            name=name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            main=main,
            base=base,
            testdata=testdata,
            kwargs=kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(py_test)
