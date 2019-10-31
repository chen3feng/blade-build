# Copyright (c) 2016 Tencent Inc.
# All rights reserved.
#
# Author: Li Wenting <wentingli@tencent.com>
# Date:   July 12, 2016

"""
Implement go_library, go_binary and go_test. In addition, provide
a simple wrapper function go_package wrapping all sorts of go tar-
gets totally.
"""

from __future__ import absolute_import

import os
import re
import subprocess

from blade import build_manager
from blade import build_rules
from blade import config
from blade import console
from blade.blade_util import var_to_list
from blade.target import Target

_package_re = re.compile(r'^\s*package\s+(\w+)\s*$')


class GoTarget(Target):
    """This class is the base of all go targets. """

    _go_os = None
    _go_arch = None

    def __init__(self,
                 name,
                 type,
                 srcs,
                 deps,
                 extra_goflags,
                 kwargs):
        """Init the go target. """
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)
        extra_goflags = ' '.join(var_to_list(extra_goflags))

        Target.__init__(self,
                        name,
                        type,
                        srcs,
                        deps,
                        None,
                        build_manager.instance,
                        kwargs)

        self._set_go_package()
        self._init_go_environment()
        self.data['extra_goflags'] = extra_goflags

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
        go_home = config.get_item('go_config', 'go_home')
        go_module_enabled = config.get_item('go_config', 'go_module_enabled')
        if go_module_enabled:
            self.data['go_package'] = os.path.join("./", self.path)
        else:
            self.data['go_package'] = os.path.relpath(self.path, os.path.join(go_home, 'src'))


    def _init_go_environment(self):
        if GoTarget._go_os is None and GoTarget._go_arch is None:
            go = config.get_item('go_config', 'go')
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

    def _expand_deps_generation(self):
        build_targets = self.blade.get_build_targets()
        for dep in self.expanded_deps:
            d = build_targets[dep]
            d.data['generate_go'] = True

    def _generate_go_dependencies(self):
        env_name = self._env_name()
        var_name = self._var_name()
        targets = self.blade.get_build_targets()
        for dep in self.deps:
            var = targets[dep]._get_target_var('go')
            if var:
                self._write_rule('%s.Depends(%s, %s)' % (env_name, var_name, var))

    def ninja_go_dependencies(self):
        targets = self.blade.get_build_targets()
        srcs = [self._source_file_path(s) for s in self.srcs]
        implicit_deps = []
        for key in self.deps:
            path = targets[key]._get_target_file('gopkg')
            if path:
                # There are two cases for go package(gopkg)
                #
                #   - gopkg produced by another go_library,
                #     the target file here is a path to the
                #     generated lib
                #
                #   - gopkg produced by a proto_library, the
                #     target file is a list of pb.go files
                implicit_deps += var_to_list(path)
        return srcs + implicit_deps

    def ninja_rules(self):
        implicit_deps = self.ninja_go_dependencies()
        output = self._target_file_path()
        variables = {'package': self.data['go_package']}
        if self.data['extra_goflags']:
            variables['extra_goflags'] = self.data['extra_goflags']
        self.ninja_build(output, self.data['go_rule'],
                         implicit_deps=implicit_deps,
                         variables=variables)
        label = self.data.get('go_label')
        if label:
            self._add_target_file(label, output)


class GoLibrary(GoTarget):
    """GoLibrary generates build rules for a go package. """

    def __init__(self, name, srcs, deps, extra_goflags, kwargs):
        GoTarget.__init__(self, name, 'go_library', srcs, deps, extra_goflags, kwargs)
        self.data['go_rule'] = 'gopackage'
        self.data['go_label'] = 'gopkg'

    def _target_file_path(self):
        """Return package object path according to the standard go directory layout. """
        go_home = config.get_item('go_config', 'go_home')
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
    """GoBinary generates build rules for a go command executable. """

    def __init__(self, name, srcs, deps, extra_goflags, kwargs):
        GoTarget.__init__(self, name, 'go_binary', srcs, deps, extra_goflags, kwargs)
        self.data['go_rule'] = 'gocommand'
        self.data['go_label'] = 'bin'

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
    """GoTest generates build rules for a go test binary. """

    def __init__(self, name, srcs, deps, testdata, extra_goflags, kwargs):
        GoTarget.__init__(self, name, 'go_test', srcs, deps, extra_goflags, kwargs)
        self.data['go_rule'] = 'gotest'
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
               extra_goflags=None,
               **kwargs):
    build_manager.instance.register_target(GoLibrary(name,
                                                     srcs,
                                                     deps,
                                                     extra_goflags,
                                                     kwargs))


def go_binary(name,
              srcs,
              deps=[],
              extra_goflags=None,
              **kwargs):
    build_manager.instance.register_target(GoBinary(name,
                                                    srcs,
                                                    deps,
                                                    extra_goflags,
                                                    kwargs))


def go_test(name,
            srcs,
            deps=[],
            testdata=[],
            extra_goflags=None,
            **kwargs):
    build_manager.instance.register_target(GoTest(name,
                                                  srcs,
                                                  deps,
                                                  testdata,
                                                  extra_goflags,
                                                  kwargs))


def find_go_srcs(path):
    srcs, tests = [], []
    for name in os.listdir(path):
        if name.startswith('.') or not name.endswith('.go'):
            continue
        if os.path.isfile(os.path.join(path, name)):
            if name.endswith('_test.go'):
                tests.append(name)
            else:
                srcs.append(name)
    return srcs, tests


def extract_go_package(path):
    with open(path) as f:
        for line in f:
            m = _package_re.match(line)
            if m:
                return m.group(1)
    raise Exception('Failed to find package in %s' % path)


def go_package(name,
               deps=[],
               testdata=[],
               extra_goflags = None):
    path = build_manager.instance.get_current_source_path()
    srcs, tests = find_go_srcs(path)
    if not srcs and not tests:
        console.error_exit('Empty go sources in %s' % path)
    if srcs:
        main = False
        for src in srcs:
            package = extract_go_package(os.path.join(path, src))
            if package == 'main':
                main = True
                break
        if main:
            go_binary(name=name, srcs=srcs, deps=deps, extra_goflags=extra_goflags)
        else:
            go_library(name=name, srcs=srcs, deps=deps, extra_goflags=extra_goflags)
    if tests:
        go_test(name='%s_test' % name,
                srcs=tests,
                deps=deps,
                testdata=testdata,
                extra_goflags=extra_goflags)


build_rules.register_function(go_library)
build_rules.register_function(go_binary)
build_rules.register_function(go_test)
build_rules.register_function(go_package)
