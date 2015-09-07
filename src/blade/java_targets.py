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

from blade_util import var_to_list
from target import Target


class JavaTargetMixIn(object):
    def _get_classes_dir(self):
        """Generated classes dir. """
        return self._target_file_path() + '.classes'

    def _get_deps(self):
        """Returns list of class paths that this targets depends on. """
        classes = []
        class_paths = []
        for dep in self.expanded_deps:
            target = self.target_database.get(dep)
            class_path = target.data.get('java_class_path')
            if class_path:
                class_paths.append(class_path)
            class_var = target.data.get('java_classes')
            if class_var:
                classes.append(class_var)
        return classes, class_paths

    def _generate_java_classes(self, var_name, srcs):
        env_name = self._env_name()
        java_test_config = configparse.blade_config.get_config('java_test_config')
        proto_library_config = configparse.blade_config.get_config('proto_library_config')

        self._write_rule('%s.Append(JAVACLASSPATH=%s)' % (
            env_name, java_test_config['junit_libs'] + proto_library_config['protobuf_java_libs']))
        dep_classes, class_paths = self._get_deps()
        if class_paths:
            self._write_rule('%s.Append(JAVACLASSPATH=%s)' % (
                env_name, class_paths))
        classes_dir = self._get_classes_dir()
        self._write_rule('%s = %s.Java(target="%s", source=%s)' % (
            var_name, env_name, classes_dir, srcs))
        if dep_classes:
            self._write_rule('%s.Depends(%s, [%s])' % (
                env_name, var_name, ', '.join(dep_classes)))
        self._write_rule('%s.Clean(%s, "%s")' % (env_name, var_name, classes_dir))
        self.data['java_class_path'] = classes_dir
        self.data['java_classes'] = var_name


class JavaTarget(Target, JavaTargetMixIn):
    """A java jar target subclass.

    This class is derived from Target and generates relates java jar
    rules.

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
        var_name = self._var_name()
        srcs = [self._source_file_path(src) for src in self.srcs]
        self._generate_java_classes(var_name, srcs)


class JavaLibrary(JavaTarget):
    """JavaLibrary"""
    def __init__(self, name, srcs, deps, prebuilt, resources, kwargs):
        type = 'java_library'
        if prebuilt:
            type = 'prebuilt_java_library'
        JavaTarget.__init__(self, name, type, srcs, deps, resources, kwargs)

    def scons_rules(self):
        if self.type != 'prebuilt_java_library':
            self._prepare_to_generate_rule()
            self._generate_classes()


class JavaBinary(JavaTarget):
    """JavaBinary"""
    def __init__(self, name, srcs, deps, resources, main_class, kwargs):
        JavaTarget.__init__(self, name, 'java_binary', srcs, deps, resources, kwargs)
        self.data['main_class'] = main_class

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._generate_classes()
        env_name = self._env_name()
        var_name = self._var_name()
        dep_classes, class_paths = self._get_deps()
        self._write_rule('%s = %s.Jar(target="%s", source=[%s] + [%s])' % (
            var_name, env_name, self._target_file_path(), self.data['java_classes'], ', '.join(dep_classes)))


class JavaTest(JavaBinary):
    """JavaTarget"""
    def __init__(self, name, srcs, deps, resources, main_class, kwargs):
        JavaBinary.__init__(self, name, srcs, deps, resources, main_class, kwargs)
        self.type = 'java_test'

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._generate_classes()


def java_library(name,
                 srcs=[],
                 deps=[],
                 resources=[],
                 prebuilt=False,
                 **kwargs):
    """Define java_jar target. """
    target = JavaLibrary(name,
                         srcs,
                         deps,
                         resources,
                         prebuilt,
                         kwargs)
    blade.blade.register_target(target)


def java_binary(name,
                main_class,
                srcs=[],
                deps=[],
                resources=[],
                **kwargs):
    """Define java_jar target. """
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
              **kwargs):
    """Define java_jar target. """
    target = JavaTest(name,
                      srcs,
                      deps,
                      resources,
                      main_class,
                      kwargs)
    blade.blade.register_target(target)


build_rules.register_function(java_binary)
build_rules.register_function(java_library)
build_rules.register_function(java_test)
