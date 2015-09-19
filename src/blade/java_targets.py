# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: CHEN Feng <phongchen@tencent.com>
# Created: Jun 26, 2013


"""
Implement java_library, java_binary and java_test
"""


import os

import blade
import blade_util
import build_rules
import configparse
import maven

from blade_util import var_to_list
from target import Target


class MavenJar(Target):
    """MavenJar"""
    def __init__(self, name, id, is_implicit_added):
        Target.__init__(self, name, 'maven_jar', [], [], blade.blade, {})
        self.data['id'] = id
        if is_implicit_added:
            self.key = ('#', name)
            self.fullname = '%s:%s' % self.key
            self.path = '#'

    def scons_rules(self):
        maven_cache = maven.MavenCache.instance()
        self.data['binary_jar'] = maven_cache.get_jar_path(self.data['id'])


class JavaTargetMixIn(object):
    """
    This mixin includes common java methods
    """
    def _add_hardcode_java_library(self, deps):
        """Add hardcode dep list to key's deps. """
        for dep in deps:
            if maven.is_valid_id(dep):
                self._add_maven_dep(dep)
                continue
            dkey = self._convert_string_to_target_helper(dep)
            if dkey not in self.deps:
                self.deps.append(dkey)
            if dkey not in self.expanded_deps:
                self.expanded_deps.append(dkey)

    def _add_maven_dep(self, id):
        name = blade_util.regular_variable_name(id).replace(':', '_')
        key = ('#', name)
        if not key in self.target_database:
            target = MavenJar(name, id, is_implicit_added=True)
            blade.blade.register_target(target)
        self.deps.append(key)
        self.expanded_deps.append(key)

    def _filter_deps(self, deps):
        filtered_deps = []
        filterouted_deps = []
        for dep in deps:
            if maven.is_valid_id(dep):
                filterouted_deps.append(dep)
            else:
                filtered_deps.append(dep)
        return filtered_deps, filterouted_deps

    def _get_classes_dir(self):
        """Return path of classes dir. """
        return self._target_file_path() + '.classes'

    def __get_deps(self, deps):
        """
        Return a tuple of (scons vars, jars)
        """
        dep_jar_vars = []
        dep_jars = []
        for d in deps:
            dep = self.target_database[d]
            jar = dep.data.get('java_jar_var')
            if jar:
                dep_jar_vars.append(jar)
            else:
                jar = dep.data.get('binary_jar')
                if jar:
                    dep_jars.append(jar)
        return dep_jar_vars, dep_jars

    def _get_compile_deps(self):
        return self.__get_deps(self.deps)

    def _get_pack_deps(self):
        return self.__get_deps(self.expanded_deps)

    def _java_sources_paths(self, srcs):
        path = set()
        segs = [
            'src/main/java',
            'src/test/java',
            'src/java/',
        ]
        for src in srcs:
            for seg in segs:
                pos = src.find(seg)
                if pos > 0:
                    path.add(src[:pos + len(seg)])
        return list(path)

    def _generate_java_source_encoding(self):
        source_encoding = self.data.get('source_encoding')
        if source_encoding is None:
            config = configparse.blade_config.get_config('java_config')
            source_encoding = config['source_encoding']
        if source_encoding:
            self._write_rule('%s.Append(JAVACFLAGS="-encoding %s")' % (
                self._env_name(), source_encoding))

    def _generate_java_sources_paths(self, srcs):
        path = self._java_sources_paths(srcs)
        if path:
            env_name = self._env_name()
            self._write_rule('%s.Append(JAVASOURCEPATH=%s)' % (env_name, path))

    def _generate_java_classpath(self, dep_jar_vars, dep_jars):
        env_name = self._env_name()
        for dep_jar_var in dep_jar_vars:
            # Can only append one by one here, maybe a scons bug.
            # Can only append as string under scons 2.1.0, maybe another bug or defect.
            self._write_rule('%s.Append(JAVACLASSPATH=str(%s[0]))' % (
                env_name, dep_jar_var))
        if dep_jars:
            self._write_rule('%s.Append(JAVACLASSPATH=%s)' % (env_name, dep_jars))

    def _generate_java_depends(self, var_name, dep_jar_vars, dep_jars):
        self._write_rule('%s.Depends(%s, [%s])' % (
            self._env_name(), var_name, ','.join(dep_jar_vars)))

    def _generate_java_classes(self, var_name, srcs):
        env_name = self._env_name()

        self._generate_java_sources_paths(srcs)
        dep_jar_vars, dep_jars = self._get_compile_deps()
        self._generate_java_classpath(dep_jar_vars, dep_jars)
        classes_dir = self._get_classes_dir()
        self._write_rule('%s = %s.Java(target="%s", source=%s)' % (
                var_name, env_name, classes_dir, srcs))
        self._generate_java_depends(var_name, dep_jar_vars, dep_jars)
        self._write_rule('%s.Clean(%s, "%s")' % (env_name, var_name, classes_dir))
        return var_name

    def _generate_generated_java_jar(self, var_name, srcs):
        env_name = self._env_name()
        self._write_rule('%s = %s.GeneratedJavaJar(target="%s" + top_env["JARSUFFIX"], source=[%s])' % (
            var_name, env_name, self._target_file_path(), ','.join(srcs)))
        self.data['java_jar_var'] = var_name

    def _generate_java_jar(self, var_name, classes_var, resources_var):
        env_name = self._env_name()
        sources = []
        if classes_var:
            sources.append(classes_var)
        if resources_var:
            sources.append(resources_var)
        if sources:
            self._write_rule('%s = %s.Jar(target="%s", source=[%s])' % (
                var_name, env_name, self._target_file_path(), ','.join(sources)))
            self.data['java_jar_var'] = var_name


class JavaTarget(Target, JavaTargetMixIn):
    """A java jar target subclass.

    This class is the base of all java targets.

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

        Init the java jar target.

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
        self.data['source_encoding'] = source_encoding
        self.data['warnings'] = warnings
        for dep in mvn_deps:
            self._add_maven_dep(dep)

    def _prepare_to_generate_rule(self):
        """Should be overridden. """
        self._check_deprecated_deps()
        self._clone_env()
        self._generate_java_source_encoding()
        warnings = self.data['warnings']
        if warnings is None:
            config = configparse.blade_config.get_config('java_config')
            warnings = config['warnings']
        if warnings:
            self._write_rule('%s.Append(JAVACFLAGS=%s)' % (
                self._env_name(), warnings))


    def _generate_resources(self):
        resources = self.data['resources']
        if not resources:
            return None
        srcs = []
        for src in resources:
            srcs.append(self._source_file_path(src))
        var_name = self._var_name('resources')
        env_name = self._env_name()
        resources_dir = self._target_file_path() + '.resources'
        self._write_rule('%s = %s.JavaResource(target="%s", source=%s)' % (
            var_name, env_name, resources_dir, srcs))
        self._write_rule('%s.Clean(%s, "%s")' % (env_name, var_name, resources_dir))
        return var_name

    def _generate_classes(self):
        if not self.srcs:
            return None
        var_name = self._var_name('classes')
        srcs = [self._source_file_path(src) for src in self.srcs]
        return self._generate_java_classes(var_name, srcs)

    def _generate_jar(self):
        var_name = self._var_name('jar')
        classes_var = self._generate_classes()
        resources_var = self._generate_resources()
        self._generate_java_jar(var_name, classes_var, resources_var)


class JavaLibrary(JavaTarget):
    """JavaLibrary"""
    def __init__(self, name, srcs, deps, resources, source_encoding,
                 warnings,
                 prebuilt,
                 binary_jar, kwargs):
        type = 'java_library'
        if prebuilt:
            type = 'prebuilt_java_library'
        JavaTarget.__init__(self, name, type, srcs, deps, resources,
                            source_encoding, warnings, kwargs)
        if prebuilt:
            if not binary_jar:
                self.data['binary_jar'] = name + '.jar'
            self.data['binary_jar'] = self._source_file_path(binary_jar)

    def scons_rules(self):
        if self.type != 'prebuilt_java_library':
            self._prepare_to_generate_rule()
            self._generate_jar()


class JavaBinary(JavaTarget):
    """JavaBinary"""
    def __init__(self, name, srcs, deps, resources, source_encoding, warnings, main_class, kwargs):
        JavaTarget.__init__(self, name, 'java_binary', srcs, deps, resources,
                            source_encoding, warnings, kwargs)
        self.data['main_class'] = main_class
        self.data['run_in_shell'] = True

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._generate_jar()
        dep_jar_vars, dep_jars = self._get_pack_deps()
        self._generate_wrapper(self._generate_one_jar(dep_jar_vars, dep_jars))

    def _get_all_depended_jars(self):
        return []

    def _generate_one_jar(self, dep_jar_vars, dep_jars):
        var_name = self._var_name('onejar')
        jar_vars = []
        if self.data.get('java_jar_var'):
            jar_vars = [self.data.get('java_jar_var')]
        jar_vars.extend(dep_jar_vars)
        self._write_rule('%s = %s.OneJar(target="%s", source=[Value("%s")] + [%s] + %s)' % (
            var_name, self._env_name(),
            self._target_file_path() + '.one.jar', self.data['main_class'],
            ','.join(jar_vars), dep_jars))
        return var_name

    def _generate_wrapper(self, onejar):
        var_name = self._var_name()
        self._write_rule('%s = %s.JavaBinary(target="%s", source=%s)' % (
            var_name, self._env_name(), self._target_file_path(), onejar))


class JavaTest(JavaBinary):
    """JavaTarget"""
    def __init__(self, name, srcs, deps, resources, source_encoding,
                 warnings, main_class, testdata, kwargs):
        java_test_config = configparse.blade_config.get_config('java_test_config')
        JavaBinary.__init__(self, name, srcs, deps, resources,
                            source_encoding, warnings, main_class, kwargs)
        self.type = 'java_test'
        self.data['testdata'] = var_to_list(testdata)

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._generate_jar()
        dep_jar_vars, dep_jars = self._get_pack_deps()
        self._generate_wrapper(self._generate_one_jar(dep_jar_vars, dep_jars),
                               dep_jar_vars)

    def _generate_wrapper(self, onejar, dep_jar_vars):
        var_name = self._var_name()
        self._write_rule('%s = %s.JavaTest(target="%s", source=[%s, %s] + [%s])' % (
            var_name, self._env_name(), self._target_file_path(),
            onejar, self.data['java_jar_var'], ','.join(dep_jar_vars)))


def maven_jar(name, id):
    target = MavenJar(name, id, is_implicit_added=False)
    blade.blade.register_target(target)


def java_library(name,
                 srcs=[],
                 deps=[],
                 resources=[],
                 source_encoding='',
                 warnings=None,
                 prebuilt=False,
                 binary_jar='',
                 **kwargs):
    """Define java_library target. """
    target = JavaLibrary(name,
                         srcs,
                         deps,
                         resources,
                         source_encoding,
                         warnings,
                         prebuilt,
                         binary_jar,
                         kwargs)
    blade.blade.register_target(target)


def java_binary(name,
                main_class,
                srcs=[],
                deps=[],
                resources=[],
                source_encoding='',
                warnings=None,
                **kwargs):
    """Define java_binary target. """
    target = JavaBinary(name,
                        srcs,
                        deps,
                        resources,
                        source_encoding,
                        warnings,
                        main_class,
                        kwargs)
    blade.blade.register_target(target)


def java_test(name,
              srcs=[],
              deps=[],
              resources=[],
              source_encoding='',
              warnings=None,
              main_class = 'org.junit.runner.JUnitCore',
              testdata=[],
              **kwargs):
    """Define java_test target. """
    target = JavaTest(name,
                      srcs,
                      deps,
                      resources,
                      source_encoding,
                      warnings,
                      main_class,
                      testdata,
                      kwargs)
    blade.blade.register_target(target)


build_rules.register_function(maven_jar)
build_rules.register_function(java_binary)
build_rules.register_function(java_library)
build_rules.register_function(java_test)
