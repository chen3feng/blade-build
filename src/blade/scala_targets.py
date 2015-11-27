# Copyright (c) 2015 Tencent Inc.
# All rights reserved.
#
# Author: Li Wenting <wentingli@tencent.com>
# Date:   November 25, 2015

"""
Implement scala_library, scala_fat_library and scala_test
"""


import blade
import build_rules
import configparse

from target import Target
from java_targets import JavaTargetMixIn
from blade_util import var_to_list


class ScalaTarget(Target, JavaTargetMixIn):
    """A scala target subclass.

    This class is the base of all scala targets.

    """
    def __init__(self,
                 name,
                 type,
                 srcs,
                 deps,
                 resources,
                 warnings,
                 kwargs):
        """Init method.

        Init the scala target.

        """
        srcs = var_to_list(srcs)
        deps, mvn_deps = self._filter_deps(var_to_list(deps))
        resources = var_to_list(resources)

        Target.__init__(self,
                        name,
                        type,
                        srcs,
                        deps,
                        blade.blade,
                        kwargs)
        self.data['resources'] = resources
        if warnings:
            self.data['warnings'] = warnings
        for dep in mvn_deps:
            self._add_maven_dep(dep)

    def _generate_scala_warnings(self):
        warnings = self.data.get('warnings')
        if not warnings:
            config = configparse.blade_config.get_config('scala_config')
            warnings = config['warnings']
            if not warnings:
                warnings = '-nowarn'
        self._write_rule('%s.Append(SCALACFLAGS="%s")' % (
            self._env_name(), warnings))

    def _prepare_to_generate_rule(self):
        """Do some preparation before generating scons rule. """
        self._clone_env()
        self._generate_scala_warnings()

    def _get_java_pack_deps(self):
        return self._get_pack_deps()

    def _generate_resources(self):
        resources = self.data['resources']
        if not resources:
            return ''
        resources = [self._source_file_path(res) for res in resources]
        env_name = self._env_name()
        var_name = self._var_name('resources')
        resources_dir = self._target_file_path() + '.resources'
        self._write_rule('%s = %s.JavaResource(target="%s", source=%s)' % (
            var_name, env_name, resources_dir, resources))
        self._write_rule('%s.Clean(%s, "%s")' % (env_name, var_name, resources_dir))
        return var_name

    def _generate_jar(self):
        sources = [self._source_file_path(src) for src in self.srcs]
        # Do not generate jar when there is no source
        if not sources:
            return
        var_name = self._var_name('jar')
        dep_jar_vars, dep_jars = self._get_compile_deps()
        self._generate_java_classpath(dep_jar_vars, dep_jars)
        resources_var = self._generate_resources()
        self._write_rule('%s = %s.ScalaJar(target="%s", source=%s + [%s])' % (
            var_name, self._env_name(),
            self._target_file_path() + '.jar', sources, resources_var))
        self._generate_java_depends(var_name, dep_jar_vars, dep_jars)
        self.data['jar_var'] = var_name


class ScalaLibrary(ScalaTarget):
    """ScalaLibrary"""
    def __init__(self, name, srcs, deps, resources, warnings, kwargs):
        ScalaTarget.__init__(self, name, 'scala_library', srcs, deps,
                             resources, warnings, kwargs)

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._generate_jar()


class ScalaFatLibrary(ScalaTarget):
    """ScalaFatLibrary"""
    def __init__(self, name, srcs, deps, resources, warnings, kwargs):
        ScalaTarget.__init__(self, name, 'scala_fat_library', srcs, deps,
                             resources, warnings, kwargs)

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._generate_jar()
        dep_jar_vars, dep_jars = self._get_pack_deps()
        self._generate_fat_jar(dep_jar_vars, dep_jars)

    def _generate_fat_jar(self, dep_jar_vars, dep_jars):
        var_name = self._var_name('fatjar')
        jar_vars = []
        if self.data.get('jar_var'):
            jar_vars = [self.data.get('jar_var')]
        jar_vars.extend(dep_jar_vars)
        self._write_rule('%s = %s.FatJar(target="%s", source=[%s] + %s)' % (
            var_name, self._env_name(),
            self._target_file_path() + '.fat.jar',
            ','.join(jar_vars), dep_jars))
        return var_name


class ScalaTest(ScalaFatLibrary):
    """ScalaTest"""
    def __init__(self, name, srcs, deps, resources, warnings,
                 testdata, kwargs):
        ScalaFatLibrary.__init__(self, name, srcs, deps, resources,
                                 warnings, kwargs)
        self.type = 'scala_test'
        self.data['testdata'] = var_to_list(testdata)
        self._add_hardcode_java_library(['org.scalatest:scalatest_2.11:2.2.4'])

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._generate_jar()
        dep_jar_vars, dep_jars = self._get_test_deps()
        self._generate_test(self._generate_fat_jar(dep_jar_vars, dep_jars))

    def _generate_test(self, fat_jar_var):
        var_name = self._var_name()
        self._write_rule('%s = %s.ScalaTest(target="%s", source=[%s, %s])' % (
            var_name, self._env_name(), self._target_file_path(),
            fat_jar_var, self.data['jar_var']))


def scala_library(name,
                  srcs=[],
                  deps=[],
                  resources=[],
                  warnings=None,
                  **kwargs):
    """Define scala_library target. """
    target = ScalaLibrary(name,
                          srcs,
                          deps,
                          resources,
                          warnings,
                          kwargs)
    blade.blade.register_target(target)


def scala_fat_library(name,
                      srcs=[],
                      deps=[],
                      resources=[],
                      warnings=None,
                      **kwargs):
    """Define scala_fat_library target. """
    target = ScalaFatLibrary(name,
                             srcs,
                             deps,
                             resources,
                             warnings,
                             kwargs)
    blade.blade.register_target(target)


def scala_test(name,
               srcs,
               deps=[],
               resources=[],
               warnings=None,
               testdata=[],
               **kwargs):
    """Define scala_test target. """
    target = ScalaTest(name,
                       srcs,
                       deps,
                       resources,
                       warnings,
                       testdata,
                       kwargs)
    blade.blade.register_target(target)


build_rules.register_function(scala_library)
build_rules.register_function(scala_fat_library)
build_rules.register_function(scala_test)