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
import console

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
                 source_encoding,
                 warnings,
                 kwargs):
        """Init method.

        Init the scala target.

        """
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)
        resources = var_to_list(resources)

        Target.__init__(self,
                        name,
                        type,
                        srcs,
                        deps,
                        None,
                        blade.blade,
                        kwargs)
        self._process_resources(resources)
        if source_encoding:
            self.data['source_encoding'] = source_encoding
        if warnings:
            self.data['warnings'] = warnings

    def _generate_scala_target_platform(self):
        config = configparse.blade_config.get_config('scala_config')
        target_platform = config['target_platform']
        if target_platform:
            self._write_rule('%s.Append(SCALACFLAGS=["-target:%s"])' % (
                self._env_name(), target_platform))

    def _generate_scala_source_encoding(self):
        source_encoding = self.data.get('source_encoding')
        if not source_encoding:
            config = configparse.blade_config.get_config('scala_config')
            source_encoding = config['source_encoding']
        if source_encoding:
            self._write_rule('%s.Append(SCALACFLAGS=["-encoding %s"])' % (
                self._env_name(), source_encoding))

    def _generate_scala_warnings(self):
        warnings = self.data.get('warnings')
        if not warnings:
            config = configparse.blade_config.get_config('scala_config')
            warnings = config['warnings']
            if not warnings:
                warnings = '-nowarn'
        self._write_rule('%s.Append(SCALACFLAGS=["%s"])' % (
            self._env_name(), warnings))

    def _prepare_to_generate_rule(self):
        """Do some preparation before generating scons rule. """
        self._clone_env()
        self._generate_scala_target_platform()
        self._generate_scala_source_encoding()
        self._generate_scala_warnings()

    def _get_java_pack_deps(self):
        return self._get_pack_deps()

    def _generate_jar(self):
        sources = [self._source_file_path(src) for src in self.srcs]
        # Do not generate jar when there is no source
        if not sources:
            return ''
        env_name = self._env_name()
        var_name = self._var_name('jar')
        dep_jar_vars, dep_jars = self._get_compile_deps()
        self._generate_java_classpath(dep_jar_vars, dep_jars)
        resources_var, resources_path_var = self._generate_resources()
        self._write_rule('%s = %s.ScalaJar(target="%s", source=%s + [%s])' % (
            var_name, env_name,
            self._target_file_path() + '.jar', sources, resources_var))
        self._generate_java_depends(var_name, dep_jar_vars, dep_jars,
                                    resources_var, resources_path_var)
        self._add_target_var('jar', var_name)
        return var_name


class ScalaLibrary(ScalaTarget):
    """ScalaLibrary"""
    def __init__(self, name, srcs, deps, resources, source_encoding, warnings,
                 exported_deps, provided_deps, kwargs):
        exported_deps = var_to_list(exported_deps)
        provided_deps = var_to_list(provided_deps)
        all_deps = var_to_list(deps) + exported_deps + provided_deps
        ScalaTarget.__init__(self, name, 'scala_library', srcs, all_deps,
                             resources, source_encoding, warnings, kwargs)
        self.data['exported_deps'] = self._unify_deps(exported_deps)
        self.data['provided_deps'] = self._unify_deps(provided_deps)

    def scons_rules(self):
        self._prepare_to_generate_rule()
        jar_var = self._generate_jar()
        if jar_var:
            self._add_default_target_var('jar', jar_var)


class ScalaFatLibrary(ScalaTarget):
    """ScalaFatLibrary"""
    def __init__(self, name, srcs, deps, resources, source_encoding, warnings,
                 exclusions, kwargs):
        ScalaTarget.__init__(self, name, 'scala_fat_library', srcs, deps,
                             resources, source_encoding, warnings, kwargs)
        if exclusions:
            self._set_pack_exclusions(exclusions)

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._generate_jar()
        dep_jar_vars, dep_jars = self._get_pack_deps()
        dep_jars = self._detect_maven_conflicted_deps('package', dep_jars)
        fatjar_var = self._generate_fat_jar(dep_jar_vars, dep_jars)
        self._add_default_target_var('fatjar', fatjar_var)


class ScalaTest(ScalaFatLibrary):
    """ScalaTest"""
    def __init__(self, name, srcs, deps, resources, source_encoding, warnings,
                 testdata, kwargs):
        ScalaFatLibrary.__init__(self, name, srcs, deps, resources, source_encoding,
                                 warnings, [], kwargs)
        self.type = 'scala_test'
        self.data['testdata'] = var_to_list(testdata)
        config = configparse.blade_config.get_config('scala_test_config')
        scalatest_libs = config['scalatest_libs']
        if scalatest_libs:
            self._add_hardcode_java_library(scalatest_libs)
        else:
            console.warning('scalatest jar was not configured')

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._generate_jar()
        dep_jar_vars, dep_jars = self._get_test_deps()
        self._generate_test(dep_jar_vars, dep_jars)

    def _generate_test(self, dep_jar_vars, dep_jars):
        var_name = self._var_name()
        jar_var = self._get_target_var('jar')
        if jar_var:
            self._write_rule('%s = %s.ScalaTest(target="%s", '
                             'source=[%s] + [%s] + %s)' % (
                    var_name, self._env_name(), self._target_file_path(),
                    jar_var, ','.join(dep_jar_vars), dep_jars))


def scala_library(name,
                  srcs=[],
                  deps=[],
                  resources=[],
                  source_encoding=None,
                  warnings=None,
                  exported_deps=[],
                  provided_deps=[],
                  **kwargs):
    """Define scala_library target. """
    target = ScalaLibrary(name,
                          srcs,
                          deps,
                          resources,
                          source_encoding,
                          warnings,
                          exported_deps,
                          provided_deps,
                          kwargs)
    blade.blade.register_target(target)


def scala_fat_library(name,
                      srcs=[],
                      deps=[],
                      resources=[],
                      source_encoding=None,
                      warnings=None,
                      exclusions=[],
                      **kwargs):
    """Define scala_fat_library target. """
    target = ScalaFatLibrary(name,
                             srcs,
                             deps,
                             resources,
                             source_encoding,
                             warnings,
                             exclusions,
                             kwargs)
    blade.blade.register_target(target)


def scala_test(name,
               srcs,
               deps=[],
               resources=[],
               source_encoding=None,
               warnings=None,
               testdata=[],
               **kwargs):
    """Define scala_test target. """
    target = ScalaTest(name,
                       srcs,
                       deps,
                       resources,
                       source_encoding,
                       warnings,
                       testdata,
                       kwargs)
    blade.blade.register_target(target)


build_rules.register_function(scala_library)
build_rules.register_function(scala_fat_library)
build_rules.register_function(scala_test)
