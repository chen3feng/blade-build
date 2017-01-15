# Copyright (c) 2016 Tencent Inc.
# All rights reserved.
#
# Author: Li Wenting <wentingli@tencent.com>
# Date:   July 12, 2016

"""
Implement go_library, go_binary and go_test
"""

import os
import subprocess

import blade
import build_rules
import configparse
import console

from target import Target
from blade_util import var_to_list


class GoTarget(Target):
    """This class is the base of all go targets. """

    _go_os = None
    _go_arch = None

    def __init__(self,
                 name,
                 type,
                 srcs,
                 deps,
                 kwargs):
        """Init the go target. """
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)

        Target.__init__(self,
                        name,
                        type,
                        srcs,
                        deps,
                        None,
                        blade.blade,
                        kwargs)

        self._set_go_package()
        self._init_go_environment()

    def _set_go_package(self):
        """
        Set the package path from the source path inside the workspace
        specified by GOPATH. All the go sources of the same package
        should be in the same directory.
        """
        srcs = [self._source_file_path(s) for s in self.srcs]
        dirs = set([os.path.dirname(s) for s in srcs])
        if len(dirs) != 1:
            console.error_exit('%s: Go sources belonging to the same package '
                               'should be in the same directory. Sources: %s' %
                               (self.fullname, ', '.join(self.srcs)))
        path = dirs.pop()
        go_home = configparse.blade_config.get_config('go_config')['go_home']
        self.data['go_package'] = os.path.relpath(path, os.path.join(go_home, 'src'))

    def _init_go_environment(self):
        if GoTarget._go_os is None and GoTarget._go_arch is None:
            go = configparse.blade_config.get_config('go_config')['go']
            p = subprocess.Popen('%s env' % go,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 shell=True,
                                 universal_newlines=True)
            stdout, stderr = p.communicate()
            if p.returncode:
                console.error_exit('%s: Failed to initialize go environment: %s' %
                                   (self.fullname, stderr))
            for line in stdout.splitlines():
                if line.startswith('GOOS='):
                    GoTarget._go_os = line.replace('GOOS=', '').strip('"')
                elif line.startswith('GOARCH='):
                    GoTarget._go_arch = line.replace('GOARCH=', '').strip('"')

    def _prepare_to_generate_rule(self):
        self._clone_env()
        env_name = self._env_name()
        self._write_rule('%s.Replace(GOPACKAGE="%s")' % (
            env_name, self.data['go_package']))

    def _generate_go_dependencies(self):
        env_name = self._env_name()
        var_name = self._var_name()
        targets = self.blade.get_build_targets()
        for dep in self.deps:
            var = targets[dep]._get_target_var('go')
            if var:
                self._write_rule('%s.Depends(%s, %s)' % (env_name, var_name, var))

class GoLibrary(GoTarget):
    """GoLibrary generates scons rules for a go package. """
    def __init__(self, name, srcs, deps, kwargs):
        GoTarget.__init__(self, name, 'go_library', srcs, deps, kwargs)

    def _target_file_path(self):
        """Return package object path according to the standard go directory layout. """
        go_home = configparse.blade_config.get_config('go_config')['go_home']
        return os.path.join(go_home, 'pkg',
                            '%s_%s' % (GoTarget._go_os, GoTarget._go_arch),
                            '%s.a' % self.data['go_package'])

    def scons_rules(self):
        self._prepare_to_generate_rule()
        env_name = self._env_name()
        var_name = self._var_name()
        srcs = [self._source_file_path(s) for s in self.srcs]
        self._write_rule('%s = %s.GoLibrary(target = "%s", source = %s)' % (
                         var_name, env_name,
                         self._target_file_path(), srcs))
        self._add_target_var('go', var_name)
        self._generate_go_dependencies()


class GoBinary(GoTarget):
    """GoBinary generates scons rules for a go command executable. """
    def __init__(self, name, srcs, deps, kwargs):
        GoTarget.__init__(self, name, 'go_binary', srcs, deps, kwargs)

    def _target_file_path(self):
        """Return command executable path according to the standard go directory layout. """
        go_home = configparse.blade_config.get_config('go_config')['go_home']
        return os.path.join(go_home, 'bin',
                            os.path.basename(self.data['go_package']))

    def scons_rules(self):
        self._prepare_to_generate_rule()
        env_name = self._env_name()
        var_name = self._var_name()
        srcs = [self._source_file_path(s) for s in self.srcs]
        self._write_rule('%s = %s.GoBinary(target = "%s", source = %s)' % (
                         var_name, env_name,
                         self._target_file_path(), srcs))
        self._add_target_var('bin', var_name)
        self._generate_go_dependencies()


class GoTest(GoTarget):
    """GoTest generates scons rules for a go test binary. """
    def __init__(self, name, srcs, deps, testdata, kwargs):
        GoTarget.__init__(self, name, 'go_test', srcs, deps, kwargs)
        self.data['testdata'] = var_to_list(testdata)

    def scons_rules(self):
        self._prepare_to_generate_rule()
        env_name = self._env_name()
        var_name = self._var_name()
        srcs = [self._source_file_path(s) for s in self.srcs]
        self._write_rule('%s = %s.GoTest(target = "%s", source = %s)' % (
                         var_name, env_name,
                         self._target_file_path(), srcs))
        self._generate_go_dependencies()


def go_library(name,
               srcs,
               deps=[],
               **kwargs):
    blade.blade.register_target(GoLibrary(name,
                                          srcs,
                                          deps,
                                          kwargs))


def go_binary(name,
              srcs,
              deps=[],
              **kwargs):
    blade.blade.register_target(GoBinary(name,
                                         srcs,
                                         deps,
                                         kwargs))


def go_test(name,
            srcs,
            deps=[],
            testdata=[],
            **kwargs):
    blade.blade.register_target(GoTest(name,
                                       srcs,
                                       deps,
                                       testdata,
                                       kwargs))


build_rules.register_function(go_library)
build_rules.register_function(go_binary)
build_rules.register_function(go_test)
