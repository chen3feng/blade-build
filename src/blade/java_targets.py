# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: CHEN Feng <phongchen@tencent.com>
# Created: Jun 26, 2013


"""
Implement java_library, java_binary, java_test and java_fat_library
"""


import os
import re
import Queue
from distutils.version import LooseVersion

import blade
import blade_util
import build_rules
import configparse
import console
import maven

from blade_util import var_to_list
from blade_util import location_re
from target import Target


class MavenJar(Target):
    """MavenJar"""
    def __init__(self, name, id, classifier, transitive):
        Target.__init__(self, name, 'maven_jar', [], [], None, blade.blade, {})
        self.data['id'] = id
        self.data['classifier'] = classifier
        self.data['transitive'] = transitive

    def _get_java_pack_deps(self):
        return [], self.data.get('maven_deps', [])

    def scons_rules(self):
        maven_cache = maven.MavenCache.instance(blade.blade.get_build_path())
        binary_jar = maven_cache.get_jar_path(self.data['id'],
                                              self.data['classifier'])
        if binary_jar:
            self.data['binary_jar'] = binary_jar
            if self.data.get('transitive'):
                deps_path = maven_cache.get_jar_deps_path(
                    self.data['id'], self.data['classifier'])
                if deps_path:
                    self.data['maven_deps'] = deps_path.split(':')


class JavaTargetMixIn(object):
    """
    This mixin includes common java methods
    """
    def _add_hardcode_java_library(self, deps):
        """Add hardcode dep list to key's deps. """
        for dep in deps:
            dkey = self._unify_dep(dep)
            if dkey not in self.deps:
                self.deps.append(dkey)
            if dkey not in self.expanded_deps:
                self.expanded_deps.append(dkey)

    def _get_maven_dep_ids(self):
        maven_dep_ids = set()
        for dkey in self.deps:
            dep = self.target_database[dkey]
            if dep.type == 'maven_jar':
                id = dep.data.get('id')
                if id:
                    maven_dep_ids.add(id)
        return maven_dep_ids

    def _unify_deps(self, deps):
        dkeys = []
        for dep in deps:
            dkey = self._unify_dep(dep)
            dkeys.append(dkey)
        return dkeys

    def __is_valid_maven_id_with_wildcards(self, id):
        wildcard = False
        for part in id.split(':'):
            if wildcard and part != '*':
                return False
            if part == '*':
                wildcard = True
        return True

    def _set_pack_exclusions(self, exclusions):
        exclusions = var_to_list(exclusions)
        self.data['exclusions'] = []
        for exclusion in exclusions:
            if maven.is_valid_id(exclusion):
                if '*' in exclusion:
                    if not self.__is_valid_maven_id_with_wildcards(exclusion):
                        console.warning('%s: Invalid maven id with wildcards %s. '
                                        'Ignored. The valid id could be: '
                                        'group:artifact:*, group:*:*, *:*:*' %
                                        (self.fullname, exclusion))
                        continue
                self.data['exclusions'].append(exclusion)
            else:
                console.warning('%s: Exclusions only support maven id '
                                'group:artifact:version. Ignore %s' % (
                                self.fullname, exclusion))

    def _process_pack_exclusions(self, jars):
        """Exclude jars specified by exclusions from input jars. """
        exclusions = self.data.get('exclusions', [])
        if exclusions:
            jars = set(jars)
            jars_excluded = set()
            for exclusion in exclusions:
                group, artifact, version = exclusion.split(':')
                group = group.replace('.', '/')
                jar_path = '.m2/repository'
                for part in (group, artifact, version):
                    if part == '*':
                        break
                    jar_path = os.path.join(jar_path, part)
                for jar in jars:
                    if jar_path in jar:
                        jars_excluded.add(jar)

            jars -= jars_excluded

        return jars

    def _process_resources(self, resources):
        """
        Process resources which could be regular files/directories or
        location references.
        """
        self.data['resources'], self.data['location_resources'] = [], []
        for resource in resources:
            if isinstance(resource, tuple):
                src, dst = resource
            elif isinstance(resource, str):
                src, dst = resource, ''
            else:
                console.error_exit('%s: Invalid resource %s. Resource should '
                                   'be either str or tuple.' % (self.fullname, resource))

            m = location_re.search(src)
            if m:
                key, type = self._add_location_reference_target(m)
                self.data['location_resources'].append((key, type, dst))
            else:
                self.data['resources'].append((src, dst))

    def _get_classes_dir(self):
        """Return path of classes dir. """
        return self._target_file_path() + '.classes'

    def _get_sources_dir(self):
        """Return path of sources dir. """
        return self._target_file_path() + '.sources'

    def __extract_dep_jars(self, dkey, dep_jar_vars, dep_jars):
        dep = self.target_database[dkey]
        jar = dep._get_target_var('jar')
        if jar:
            dep_jar_vars.append(jar)
        else:
            jar = dep.data.get('binary_jar')
            if jar:
                dep_jars.append(jar)

    def __get_deps(self, deps):
        """
        Return a tuple of (scons vars, jars)
        """
        dep_jar_vars = []
        dep_jars = []
        for d in deps:
            self.__extract_dep_jars(d, dep_jar_vars, dep_jars)
        return dep_jar_vars, dep_jars

    def __get_exported_deps(self, deps):
        """
        Recursively get exported dependencies and return a tuple of (scons vars, jars)
        """
        dep_jar_vars, dep_jars = [], []
        q = Queue.Queue(0)
        for key in deps:
            q.put(key)

        keys = set()
        while not q.empty():
            key = q.get()
            if key not in keys:
                keys.add(key)
                dep = self.target_database[key]
                exported_deps = dep.data.get('exported_deps', [])
                for edkey in exported_deps:
                    self.__extract_dep_jars(edkey, dep_jar_vars, dep_jars)
                    q.put(edkey)

        return list(set(dep_jar_vars)), list(set(dep_jars))

    def __get_maven_transitive_deps(self, deps):
        """
        Return a list of maven jars stored within local repository.
        These jars are transitive dependencies of maven_jar target.
        """
        maven_jars = []
        for key in deps:
            dep = self.target_database[key]
            if dep.type == 'maven_jar':
                maven_jars += dep.data.get('maven_deps', [])
        return maven_jars

    def _detect_maven_conflicted_deps(self, scope, dep_jars):
        """
        Maven dependencies might have conflict: same group and artifact
        but different version. Select higher version by default unless
        a specific version of maven dependency is specified as a direct
        dependency of the target
        """
        dep_jars, conflicted_jars = set(dep_jars), set()
        maven_dep_ids = self._get_maven_dep_ids()
        maven_jar_dict = {}  # (group, artifact) -> (version, set(jar))
        maven_repo = '.m2/repository/'
        for dep_jar in dep_jars:
            if maven_repo not in dep_jar:
                continue
            parts = dep_jar[dep_jar.find(maven_repo) + len(maven_repo):].split('/')
            if len(parts) < 4:
                continue
            name, version, artifact, group = (parts[-1], parts[-2],
                                              parts[-3], '.'.join(parts[:-3]))
            key = (group, artifact)
            id = ':'.join((group, artifact, version))
            if key in maven_jar_dict:
                old_value = maven_jar_dict[key]
                if version == old_value[0]:
                    # jar must be different because dep_jars is a set
                    old_value[1].add(dep_jar)
                    continue
                old_id = ':'.join((group, artifact, old_value[0]))
                if old_id in maven_dep_ids:
                    conflicted_jars.add(dep_jar)
                elif id in maven_dep_ids or LooseVersion(version) > LooseVersion(old_value[0]):
                    conflicted_jars |= old_value[1]
                    maven_jar_dict[key] = (version, set([dep_jar]))
                else:
                    conflicted_jars.add(dep_jar)
                value = maven_jar_dict[key]
                console.debug('%s: Maven dependency version conflict '
                              '%s:%s:{%s, %s} during %s. Use %s' % (
                              self.fullname, key[0], key[1],
                              version, old_value[0], scope, value[0]))
            else:
                maven_jar_dict[key] = (version, set([dep_jar]))

        dep_jars -= conflicted_jars
        return sorted(list(dep_jars))

    def _get_compile_deps(self):
        dep_jar_vars, dep_jars = self.__get_deps(self.deps)
        exported_dep_jar_vars, exported_dep_jars = self.__get_exported_deps(self.deps)
        dep_jars += self.__get_maven_transitive_deps(self.deps)
        dep_jar_vars = sorted(list(set(dep_jar_vars + exported_dep_jar_vars)))
        dep_jars = self._detect_maven_conflicted_deps('compile',
            dep_jars + exported_dep_jars)
        return dep_jar_vars, dep_jars

    def _get_test_deps(self):
        dep_jar_vars, dep_jars = self.__get_deps(self.expanded_deps)
        dep_jars += self.__get_maven_transitive_deps(self.expanded_deps)
        dep_jar_vars = sorted(list(set(dep_jar_vars)))
        dep_jars = self._process_pack_exclusions(dep_jars)
        dep_jars = self._detect_maven_conflicted_deps('test', dep_jars)
        return dep_jar_vars, dep_jars

    def _get_pack_deps(self):
        """
        Recursively scan direct dependencies and exclude provided dependencies.
        """
        deps = set(self.deps)
        provided_deps = self.data.get('provided_deps', [])
        for provided_dep in provided_deps:
            deps.discard(provided_dep)
        dep_jar_vars, dep_jars = self.__get_deps(deps)

        for dep in deps:
            dep = self.target_database[dep]
            jar_vars, jars = dep._get_java_pack_deps()
            dep_jar_vars += jar_vars
            dep_jars += jars

        dep_jar_vars, dep_jars = set(dep_jar_vars), set(dep_jars)
        dep_jars = self._process_pack_exclusions(dep_jars)

        return sorted(list(dep_jar_vars)), sorted(list(dep_jars))

    def _get_java_package_name(self):
        """
        Get java package name. Usually all the sources are within the same package.
        However, there are cases where BUILD is in the parent directory and sources
        are located in subdirectories each of which defines its own package.
        """
        if not self.srcs:
            return []
        packages = set()
        for src in self.srcs:
            package = self._get_source_package_name(self._source_file_path(src))
            if package:
                packages.add(package)
        return sorted(list(packages))

    def _get_source_package_name(self, file_name):
        """Get the java package name from source file if it is specified. """
        if not os.path.isfile(file_name):
            return ''
        package_pattern = '^\s*package\s+([\w.]+)'
        content = open(file_name).read()
        m = re.search(package_pattern, content, re.MULTILINE)
        if m:
            return m.group(1)

        return ''

    def _get_resource_path(self, resource):
        """
        Given a resource return its full path within the workspace
        and mapping path in the jar.
        """
        full_path, res_path, jar_path = '', resource[0], resource[1]
        if '..' in res_path:
            console.error_exit('%s: Invalid resource %s. Relative path is not allowed.'
                               % (self.fullname, res_path))
        elif res_path.startswith('//'):
            res_path = res_path[2:]
            full_path = res_path
            if not jar_path:
                jar_path = res_path
        else:
            full_path = self._source_file_path(res_path)
            if not jar_path:
                # Mapping rules from maven standard layout
                jar_path = self._java_resource_path(res_path)

        return full_path, jar_path

    def _process_regular_resources(self, resources):
        results = set()
        for resource in resources:
            full_path, jar_path = self._get_resource_path(resource)
            if not os.path.exists(full_path):
                console.error_exit('%s: Resource %s does not exist.' % (
                                   self.fullname, full_path))
            elif os.path.isfile(full_path):
                results.add((full_path, jar_path))
            else:
                for dir, subdirs, files in os.walk(full_path):
                    # Skip over subdirs starting with '.', such as .svn
                    subdirs[:] = [d for d in subdirs if not d.startswith('.')]
                    for f in files:
                        f = os.path.join(dir, f)
                        rel_path = os.path.relpath(f, full_path)
                        results.add((f, os.path.join(jar_path, rel_path)))

        return sorted(results)

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
                    continue
            package = self._get_source_package_name(src)
            if package:
                package = package.replace('.', '/') + '/'
                pos = src.find(package)
                if pos > 0:
                    path.add(src[:pos])
                    continue

        return list(path)

    def _java_resource_path(self, resource):
        """
        Resource path mapping rules from local directory to jar entry. See
        https://maven.apache.org/guides/introduction/introduction-to-the-standard-directory-layout.html
        for maven rules.
        """
        segs = [
            'src/main/resources',
            'src/test/resources',
            'resources',
        ]
        for seg in segs:
            pos = resource.find(seg)
            if pos != -1:
                return resource[pos + len(seg) + 1:]  # skip separator '/'
        return resource

    def _generate_java_versions(self):
        java_config = configparse.blade_config.get_config('java_config')
        version = java_config['version']
        source_version = java_config.get('source_version', version)
        target_version = java_config.get('target_version', version)
        # JAVAVERSION must be set because scons need it to deduce class names
        # from java source, and the default value '1.5' is too low.
        blade_java_version = version or '1.6'
        self._write_rule('%s.Replace(JAVAVERSION="%s")' % (
            self._env_name(), blade_java_version))
        if source_version:
            self._write_rule('%s.Append(JAVACFLAGS="-source %s")' % (
                self._env_name(), source_version))
        if target_version:
            self._write_rule('%s.Append(JAVACFLAGS="-target %s")' % (
                self._env_name(), target_version))

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

    def _generate_java_depends(self, var_name, dep_jar_vars, dep_jars,
                               resources_var, resources_path_var):
        env_name = self._env_name()
        if dep_jar_vars:
            self._write_rule('%s.Depends(%s, [%s])' % (
                    env_name, var_name, ','.join(dep_jar_vars)))
        if dep_jars:
            self._write_rule('%s.Depends(%s, %s.Value(%s))' % (
                    env_name, var_name, env_name, sorted(dep_jars)))
        if resources_var:
            self._write_rule('%s.Depends(%s, %s.Value(%s))' % (
                    env_name, var_name, env_name, resources_path_var))
        locations = self.data.get('location_resources')
        if locations:
            self._write_rule('%s.Depends(%s, %s.Value("%s"))' % (
                env_name, var_name, env_name, sorted(set(locations))))

    def _generate_java_classes(self, var_name, srcs):
        env_name = self._env_name()

        self._generate_java_sources_paths(srcs)
        dep_jar_vars, dep_jars = self._get_compile_deps()
        self._generate_java_classpath(dep_jar_vars, dep_jars)
        classes_dir = self._get_classes_dir()
        self._write_rule('%s = %s.Java(target="%s", source=%s)' % (
                var_name, env_name, classes_dir, srcs))
        self._generate_java_depends(var_name, dep_jar_vars, dep_jars, '', '')
        self._write_rule('%s.Clean(%s, "%s")' % (env_name, var_name, classes_dir))
        return var_name

    def _generate_sources(self):
        """
        Generate java sources in the build directory for the subsequent
        code coverage. The layout is based on the package parsed from sources.
        Note that the classes are still compiled from the sources in the
        source directory.
        """
        env_name = self._env_name()
        sources_dir = self._get_sources_dir()
        for source in self.srcs:
            src = self._source_file_path(source)
            package = self._get_source_package_name(src)
            dst = os.path.join(sources_dir, package.replace('.', '/'),
                               os.path.basename(source))
            self._write_rule('%s.JavaSource(target = "%s", source = "%s")' %
                             (env_name, dst, src))

    def _generate_regular_resources(self, resources,
                                    resources_var, resources_path_var):
        env_name = self._env_name()
        resources_dir = self._target_file_path() + '.resources'
        resources = self._process_regular_resources(resources)
        for i, resource in enumerate(resources):
            src, dst = resource[0], os.path.join(resources_dir, resource[1])
            res_var = self._var_name('resources__%s' % i)
            self._write_rule('%s = %s.JavaResource(target = "%s", source = "%s")' %
                             (res_var, env_name, dst, src))
            self._write_rule('%s.append(%s)' % (resources_var, res_var))
            self._write_rule('%s.append("%s")' % (resources_path_var, dst))

    def _generate_location_resources(self, resources, resources_var):
        env_name = self._env_name()
        resources_dir = self._target_file_path() + '.resources'
        targets = self.blade.get_build_targets()
        for i, resource in enumerate(resources):
            key, type, dst = resource
            target = targets[key]
            target_var = target._get_target_var(type)
            if not target_var:
                console.warning('%s: Location %s %s is missing. Ignored.' %
                                (self.fullname, key, type))
                continue
            if dst:
                dst_path = os.path.join(resources_dir, dst)
            else:
                dst_path = os.path.join(resources_dir, '${SOURCE.file}')
            res_var = self._var_name('location_resources__%s' % i)
            self._write_rule('%s = %s.JavaResource(target = "%s", source = %s)' %
                             (res_var, env_name, dst_path, target_var))
            self._write_rule('%s.append(%s)' % (resources_var, res_var))

    def _generate_resources(self):
        resources = self.data['resources']
        locations = self.data['location_resources']
        if not resources and not locations:
            return '', ''
        env_name = self._env_name()
        resources_var_name = self._var_name('resources')
        resources_path_var_name = self._var_name('resources_path')
        resources_dir = self._target_file_path() + '.resources'
        self._write_rule('%s, %s = [], []' % (
            resources_var_name, resources_path_var_name))
        self._generate_regular_resources(resources, resources_var_name,
                                         resources_path_var_name)
        self._generate_location_resources(locations, resources_var_name)
        self._write_rule('%s.Clean(%s, "%s")' % (
            env_name, resources_var_name, resources_dir))
        return resources_var_name, resources_path_var_name

    def _generate_generated_java_jar(self, var_name, srcs):
        env_name = self._env_name()
        self._write_rule('%s = %s.GeneratedJavaJar(target="%s" + top_env["JARSUFFIX"], source=[%s])' % (
            var_name, env_name, self._target_file_path(), ','.join(srcs)))

    def _generate_java_jar(self, srcs, resources_var):
        env_name = self._env_name()
        var_name = self._var_name('jar')
        self._write_rule('%s = %s.BladeJavaJar(target="%s", source=%s + [%s])' % (
                var_name, env_name, self._target_file_path() + '.jar',
                srcs, resources_var))
        # BladeJavaJar builder puts the generated classes
        # into .class directory during jar building
        classes_dir = self._get_classes_dir()
        self._write_rule('%s.Clean(%s, "%s")' % (env_name, var_name, classes_dir))
        return var_name

    def _generate_fat_jar(self, dep_jar_vars, dep_jars):
        var_name = self._var_name('fatjar')
        jar_vars = []
        if self._get_target_var('jar'):
            jar_vars = [self._get_target_var('jar')]
        jar_vars.extend(dep_jar_vars)
        self._write_rule('%s = %s.FatJar(target="%s", source=[%s] + %s)' % (
            var_name, self._env_name(),
            self._target_file_path() + '.fat.jar',
            ','.join(jar_vars), dep_jars))
        return var_name


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
        self.data['source_encoding'] = source_encoding
        if warnings is not None:
            self.data['warnings'] = var_to_list(warnings)

    def _clone_env(self):
        self._write_rule('%s = env_java.Clone()' % self._env_name())

    def _prepare_to_generate_rule(self):
        """Should be overridden. """
        self._check_deprecated_deps()
        self._clone_env()
        self._generate_java_source_encoding()
        warnings = self.data.get('warnings')
        if warnings is None:
            config = configparse.blade_config.get_config('java_config')
            warnings = config['warnings']
        if warnings:
            self._write_rule('%s.Append(JAVACFLAGS=%s)' % (
                self._env_name(), warnings))

    def _get_java_pack_deps(self):
        return self._get_pack_deps()

    def _generate_classes(self):
        if not self.srcs:
            return None
        var_name = self._var_name('classes')
        srcs = [self._source_file_path(src) for src in self.srcs]
        return self._generate_java_classes(var_name, srcs)

    def _generate_jar(self):
        self._generate_sources()
        dep_jar_vars, dep_jars = [], []
        srcs = [self._source_file_path(s) for s in self.srcs]
        if srcs:
            dep_jar_vars, dep_jars = self._get_compile_deps()
            self._generate_java_classpath(dep_jar_vars, dep_jars)
        resources_var, resources_path_var = self._generate_resources()
        if srcs or resources_var:
            var_name = self._generate_java_jar(srcs, resources_var)
            self._generate_java_depends(var_name, dep_jar_vars, dep_jars,
                                        resources_var, resources_path_var)
            self._add_target_var('jar', var_name)
            return var_name
        return ''


class JavaLibrary(JavaTarget):
    """JavaLibrary"""
    def __init__(self, name, srcs, deps, resources, source_encoding, warnings,
                 prebuilt, binary_jar, exported_deps, provided_deps, kwargs):
        type = 'java_library'
        if prebuilt:
            type = 'prebuilt_java_library'
        exported_deps = var_to_list(exported_deps)
        provided_deps = var_to_list(provided_deps)
        all_deps = var_to_list(deps) + exported_deps + provided_deps
        JavaTarget.__init__(self, name, type, srcs, all_deps, resources,
                            source_encoding, warnings, kwargs)
        self.data['exported_deps'] = self._unify_deps(exported_deps)
        self.data['provided_deps'] = self._unify_deps(provided_deps)
        if prebuilt:
            if not binary_jar:
                binary_jar = name + '.jar'
            self.data['binary_jar'] = self._source_file_path(binary_jar)

    def _generate_prebuilt_jar(self):
        var_name = self._var_name('jar')
        self._write_rule('%s = top_env.File(["%s"])' % (
                         var_name, self.data['binary_jar']))
        return var_name

    def scons_rules(self):
        if self.type == 'prebuilt_java_library':
            jar_var = self._generate_prebuilt_jar()
        else:
            self._prepare_to_generate_rule()
            jar_var = self._generate_jar()

        if jar_var:
            self._add_default_target_var('jar', jar_var)


class JavaBinary(JavaTarget):
    """JavaBinary"""
    def __init__(self, name, srcs, deps, resources, source_encoding,
                 warnings, main_class, exclusions, kwargs):
        JavaTarget.__init__(self, name, 'java_binary', srcs, deps, resources,
                            source_encoding, warnings, kwargs)
        self.data['main_class'] = main_class
        self.data['run_in_shell'] = True
        if exclusions:
            self._set_pack_exclusions(exclusions)

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._generate_jar()
        dep_jar_vars, dep_jars = self._get_pack_deps()
        dep_jars = self._detect_maven_conflicted_deps('package', dep_jars)
        self._generate_wrapper(self._generate_one_jar(dep_jar_vars, dep_jars))

    def _get_all_depended_jars(self):
        return []

    def _generate_one_jar(self, dep_jar_vars, dep_jars):
        var_name = self._var_name('onejar')
        jar_vars = []
        if self._get_target_var('jar'):
            jar_vars = [self._get_target_var('jar')]
        jar_vars.extend(dep_jar_vars)
        self._write_rule('%s = %s.OneJar(target="%s", source=[Value("%s")] + [%s] + %s)' % (
            var_name, self._env_name(),
            self._target_file_path() + '.one.jar', self.data['main_class'],
            ','.join(jar_vars), dep_jars))
        self._add_target_var('onejar', var_name)
        return var_name

    def _generate_wrapper(self, onejar):
        var_name = self._var_name()
        self._write_rule('%s = %s.JavaBinary(target="%s", source=%s)' % (
            var_name, self._env_name(), self._target_file_path(), onejar))
        self._add_default_target_var('bin', var_name)


class JavaFatLibrary(JavaTarget):
    """JavaFatLibrary"""
    def __init__(self, name, srcs, deps, resources, source_encoding,
                 warnings, exclusions, kwargs):
        JavaTarget.__init__(self, name, 'java_fat_library', srcs, deps,
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


class JavaTest(JavaBinary):
    """JavaTest"""
    def __init__(self, name, srcs, deps, resources, source_encoding,
                 warnings, main_class, exclusions,
                 testdata, target_under_test, kwargs):
        java_test_config = configparse.blade_config.get_config('java_test_config')
        JavaBinary.__init__(self, name, srcs, deps, resources,
                            source_encoding, warnings, main_class, exclusions, kwargs)
        self.type = 'java_test'
        self.data['testdata'] = var_to_list(testdata)
        if target_under_test:
            self.data['target_under_test'] = self._unify_dep(target_under_test)

    def scons_rules(self):
        self._prepare_to_generate_rule()
        self._generate_jar()
        dep_jar_vars, dep_jars = self._get_test_deps()
        self._generate_java_test(dep_jar_vars, dep_jars)

    def _prepare_to_generate_rule(self):
        JavaBinary._prepare_to_generate_rule(self)
        self._generate_target_under_test_package()

    def _generate_target_under_test_package(self):
        target_under_test = self.data.get('target_under_test')
        if target_under_test:
            target = self.target_database[target_under_test]
            self._write_rule('%s.Append(JAVATARGETUNDERTESTPKG=%s)' % (
                self._env_name(), target._get_java_package_name()))

    def _generate_java_test(self, dep_jar_vars, dep_jars):
        var_name = self._var_name()
        jar_var = self._get_target_var('jar')
        if jar_var:
            self._write_rule('%s = %s.JavaTest(target="%s", '
                             'source=[Value("%s")] + [%s] + [%s] + %s)' % (
                var_name, self._env_name(), self._target_file_path(),
                self.data['main_class'], jar_var,
                ','.join(dep_jar_vars), dep_jars))


def maven_jar(name, id, classifier='', transitive=True):
    target = MavenJar(name, id, classifier, transitive)
    blade.blade.register_target(target)


def java_library(name,
                 srcs=[],
                 deps=[],
                 resources=[],
                 source_encoding=None,
                 warnings=None,
                 prebuilt=False,
                 binary_jar='',
                 exported_deps=[],
                 provided_deps=[],
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
                         exported_deps,
                         provided_deps,
                         kwargs)
    blade.blade.register_target(target)


def java_binary(name,
                main_class,
                srcs=[],
                deps=[],
                resources=[],
                source_encoding=None,
                warnings=None,
                exclusions=[],
                **kwargs):
    """Define java_binary target. """
    target = JavaBinary(name,
                        srcs,
                        deps,
                        resources,
                        source_encoding,
                        warnings,
                        main_class,
                        exclusions,
                        kwargs)
    blade.blade.register_target(target)


def java_test(name,
              srcs,
              deps=[],
              resources=[],
              source_encoding=None,
              warnings=None,
              main_class = 'org.junit.runner.JUnitCore',
              exclusions=[],
              testdata=[],
              target_under_test='',
              **kwargs):
    """Define java_test target. """
    target = JavaTest(name,
                      srcs,
                      deps,
                      resources,
                      source_encoding,
                      warnings,
                      main_class,
                      exclusions,
                      testdata,
                      target_under_test,
                      kwargs)
    blade.blade.register_target(target)


def java_fat_library(name,
                     srcs=[],
                     deps=[],
                     resources=[],
                     source_encoding=None,
                     warnings=None,
                     exclusions=[],
                     **kwargs):
    """Define java_fat_library target. """
    target = JavaFatLibrary(name,
                            srcs,
                            deps,
                            resources,
                            source_encoding,
                            warnings,
                            exclusions,
                            kwargs)
    blade.blade.register_target(target)


build_rules.register_function(maven_jar)
build_rules.register_function(java_binary)
build_rules.register_function(java_library)
build_rules.register_function(java_test)
build_rules.register_function(java_fat_library)
