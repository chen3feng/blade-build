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
import build_rules
import configparse
import maven

from blade_util import var_to_list
from target import Target


class JavaTargetMixIn(object):
    """
    This mixin includes common java methods
    """
    def _get_classes_dir(self):
        """Return path of classes dir. """
        return self._target_file_path() + '.classes'

    def __get_deps(self, deps):
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

    def _get_deps(self):
        return self.__get_deps(self.deps)

    def _get_all_deps(self):
        return self.__get_deps(self.expanded_deps)

    def _generate_java_classes(self, var_name, srcs):
        env_name = self._env_name()
        proto_library_config = configparse.blade_config.get_config('proto_library_config')

        dep_jar_vars, dep_jars = self._get_deps()
        for dep_jar_var in dep_jar_vars:
            # Can only append one by one here, maybe a scons bug.
            # Can only append as string under scons 2.1.0, maybe another bug or defect.
            self._write_rule('%s.Append(JAVACLASSPATH=str(%s[0]))' % (
                env_name, dep_jar_var))
        if dep_jars:
            self._write_rule('%s.Append(JAVACLASSPATH=%s)' % (env_name, dep_jars))
        classes_dir = self._get_classes_dir()
        self._write_rule('%s = %s.Java(target="%s", source=%s)' % (
            var_name, env_name, classes_dir, srcs))
        self._write_rule('%s.Depends(%s, [%s])' % (
            env_name, var_name, ','.join(dep_jar_vars)))
        self._write_rule('%s.Clean(%s, "%s")' % (env_name, var_name, classes_dir))
        return var_name

    def _generate_java_jar(self, var_name, classes_var):
        env_name = self._env_name()
        self._write_rule('%s = %s.Jar(target="%s", source=[%s])' % (
            var_name, env_name, self._target_file_path(), classes_var))
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
                 kwargs):
        """Init method.

        Init the java jar target.

        """
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)
        resources = var_to_list(resources)

        Target.__init__(self,
                        name,
                        type,
                        srcs,
                        deps,
                        blade.blade,
                        kwargs)
        self.data['resources'] = resources

    def _prepare_to_generate_rule(self):
        """Should be overridden. """
        self._check_deprecated_deps()
        self._clone_env()

    def _generate_classes(self):
        var_name = self._var_name('classes')
        srcs = [self._source_file_path(src) for src in self.srcs]
        return self._generate_java_classes(var_name, srcs)

    def _generate_jar(self, classes_var):
        var_name = self._var_name('jar')
        self._generate_java_jar(var_name, classes_var)


class JavaLibrary(JavaTarget):
    """JavaLibrary"""
    def __init__(self, name, srcs, deps, resources, prebuilt, binary_jar, kwargs):
        type = 'java_library'
        if prebuilt:
            type = 'prebuilt_java_library'
        JavaTarget.__init__(self, name, type, srcs, deps, resources, kwargs)
        if prebuilt:
            if not binary_jar:
                self.data['binary_jar'] = name + '.jar'
            self.data['binary_jar'] = self._source_file_path(binary_jar)

    def scons_rules(self):
        if self.type != 'prebuilt_java_library':
            self._prepare_to_generate_rule()
            self._generate_jar(self._generate_classes())


class JavaBinary(JavaTarget):
    """JavaBinary"""
    def __init__(self, name, srcs, deps, resources, main_class, kwargs):
        JavaTarget.__init__(self, name, 'java_binary', srcs, deps, resources, kwargs)
        self.data['main_class'] = main_class
        self.data['run_in_shell'] = True

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._generate_jar(self._generate_classes())
        dep_jar_vars, dep_jars = self._get_all_deps()
        self._generate_wrapper(self._generate_one_jar(dep_jar_vars, dep_jars))

    def _get_all_depended_jars(self):
        return []

    def _generate_one_jar(self, dep_jar_vars, dep_jars):
        var_name = self._var_name('onejar')
        dep_jar_vars, dep_jars = self._get_all_deps()
        self._write_rule('%s = %s.OneJar(target="%s", source=[Value("%s")] + [%s] + [%s] + %s)' % (
            var_name, self._env_name(),
            self._target_file_path() + '.one.jar', self.data['main_class'],
            self.data['java_jar_var'], ','.join(dep_jar_vars), dep_jars))
        return var_name

    def _generate_wrapper(self, onejar):
        var_name = self._var_name()
        self._write_rule('%s = %s.JavaBinary(target="%s", source=%s)' % (
            var_name, self._env_name(), self._target_file_path(), onejar))


class JavaTest(JavaBinary):
    """JavaTarget"""
    def __init__(self, name, srcs, deps, resources, main_class, testdata, kwargs):
        java_test_config = configparse.blade_config.get_config('java_test_config')
        JavaBinary.__init__(self, name, srcs, deps, resources, main_class, kwargs)
        self.type = 'java_test'
        self.data['testdata'] = var_to_list(testdata)

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._generate_jar(self._generate_classes())
        dep_jar_vars, dep_jars = self._get_all_deps()
        self._generate_wrapper(self._generate_one_jar(dep_jar_vars, dep_jars),
                               dep_jar_vars)
    def _generate_wrapper(self, onejar, dep_jar_vars):
        var_name = self._var_name()
        self._write_rule('%s = %s.JavaTest(target="%s", source=[%s, %s] + [%s])' % (
            var_name, self._env_name(), self._target_file_path(),
            onejar, self.data['java_jar_var'], ','.join(dep_jar_vars)))


def java_library(name,
                 srcs=[],
                 deps=[],
                 resources=[],
                 prebuilt=False,
                 binary_jar='',
                 **kwargs):
    """Define java_library target. """
    target = JavaLibrary(name,
                         srcs,
                         deps,
                         resources,
                         prebuilt,
                         binary_jar,
                         kwargs)
    blade.blade.register_target(target)


def java_binary(name,
                main_class,
                srcs=[],
                deps=[],
                resources=[],
                **kwargs):
    """Define java_binary target. """
    target = JavaBinary(name,
                        srcs,
                        deps,
                        resources,
                        main_class,
                        kwargs)
    blade.blade.register_target(target)


def java_test(name,
              srcs=[],
              deps=[],
              resources=[],
              main_class = 'org.junit.runner.JUnitCore',
              testdata=[],
              **kwargs):
    """Define java_test target. """
    target = JavaTest(name,
                      srcs,
                      deps,
                      resources,
                      main_class,
                      testdata,
                      kwargs)
    blade.blade.register_target(target)


build_rules.register_function(java_binary)
build_rules.register_function(java_library)
build_rules.register_function(java_test)
