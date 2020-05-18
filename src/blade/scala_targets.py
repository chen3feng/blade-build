# Copyright (c) 2015 Tencent Inc.
# All rights reserved.
#
# Author: Li Wenting <wentingli@tencent.com>
# Date:   November 25, 2015

"""
Implement scala_library, scala_fat_library and scala_test
"""

from __future__ import absolute_import

from blade import build_manager
from blade import build_rules
from blade import config
from blade import console
from blade.blade_util import var_to_list
from blade.java_targets import JavaTargetMixIn
from blade.target import Target


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
                        build_manager.instance,
                        kwargs)
        self._process_resources(resources)
        if source_encoding:
            self.data['source_encoding'] = source_encoding
        if warnings:
            self.data['warnings'] = warnings

    def _expand_deps_generation(self):
        self._expand_deps_java_generation()

    def _get_java_pack_deps(self):
        return self._get_pack_deps()

    def scalac_flags(self):
        flags = []
        scala_config = config.get_section('scala_config')
        target_platform = scala_config['target_platform']
        if target_platform:
            flags.append('-target:%s' % target_platform)
        warnings = self.data.get('warnings')
        if warnings:
            flags.append(warnings)
        global_warnings = scala_config['warnings']
        if global_warnings:
            flags.append(global_warnings)
        return flags

    def ninja_generate_jar(self):
        srcs = [self._source_file_path(s) for s in self.srcs]
        resources = self.ninja_generate_resources()
        jar = self._target_file_path() + '.jar'
        if srcs and resources:
            classes_jar = self._target_file_path() + '__classes__.jar'
            scalacflags = self.scalac_flags()
            self.ninja_build_jar(classes_jar, inputs=srcs, scala=True, scalacflags=scalacflags)
            self.ninja_build('javajar', jar, inputs=[classes_jar] + resources)
        elif srcs:
            scalacflags = self.scalac_flags()
            self.ninja_build_jar(jar, inputs=srcs, scala=True, scalacflags=scalacflags)
        elif resources:
            self.ninja_build('javajar', jar, inputs=resources)
        else:
            jar = ''
        if jar:
            self._add_target_file('jar', jar)
        return jar


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

    def ninja_rules(self):
        jar = self.ninja_generate_jar()
        if jar:
            self._add_default_target_file('jar', jar)


class ScalaFatLibrary(ScalaTarget):
    """ScalaFatLibrary"""

    def __init__(self, name, srcs, deps, resources, source_encoding, warnings,
                 exclusions, kwargs):
        ScalaTarget.__init__(self, name, 'scala_fat_library', srcs, deps,
                             resources, source_encoding, warnings, kwargs)
        if exclusions:
            self._set_pack_exclusions(exclusions)

    def ninja_rules(self):
        jar = self.ninja_generate_fat_jar()
        self._add_default_target_file('fatjar', jar)


class ScalaTest(ScalaFatLibrary):
    """ScalaTest"""

    def __init__(self, name, srcs, deps, resources, source_encoding,
                 warnings, exclusions, testdata, kwargs):
        ScalaFatLibrary.__init__(self, name, srcs, deps, resources, source_encoding,
                                 warnings, exclusions, kwargs)
        self.type = 'scala_test'
        self.data['testdata'] = var_to_list(testdata)
        scalatest_libs = config.get_item('scala_test_config', 'scalatest_libs')
        if scalatest_libs:
            self._add_hardcode_java_library(scalatest_libs)
        else:
            console.warning('scalatest jar was not configured')

    def ninja_rules(self):
        if not self.srcs:
            self.warning('Empty scala test sources.')
            return
        jar = self.ninja_generate_jar()
        output = self._target_file_path()
        dep_jars, maven_jars = self._get_test_deps()
        self.ninja_build('scalatest', output, inputs=[jar] + dep_jars + maven_jars)


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
    build_manager.instance.register_target(target)


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
    build_manager.instance.register_target(target)


def scala_test(name,
               srcs,
               deps=[],
               resources=[],
               source_encoding=None,
               warnings=None,
               exclusions=[],
               testdata=[],
               **kwargs):
    """Define scala_test target. """
    target = ScalaTest(name,
                       srcs,
                       deps,
                       resources,
                       source_encoding,
                       warnings,
                       exclusions,
                       testdata,
                       kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(scala_library)
build_rules.register_function(scala_fat_library)
build_rules.register_function(scala_test)
