# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the scons_java_jar module which inherits the SconsTarget
 and generates related java jar rules.

"""


import os
import blade

import build_rules
import console
import configparse

from blade_util import relative_path
from blade_util import var_to_list
from target import Target


class JavaJarTarget(Target):
    """A java jar target subclass.

    This class is derived from Target and generates relates java jar
    rules.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 prebuilt,
                 blade,
                 kwargs):
        """Init method.

        Init the java jar target.

        """
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)

        Target.__init__(self,
                        name,
                        'java_jar',
                        srcs,
                        deps,
                        blade,
                        kwargs)

        if prebuilt:
            self.type = 'prebuilt_java_jar'
            self.data['jar_class_path'] = self._prebuilt_java_jar_src_path()
        self.data['java_jars'] = []
        self.java_jar_cmd_list = []
        self.cmd_var_list = []
        self.java_jar_after_dep_source_list = []
        self.targets_dependency_map = {}
        self.java_jar_dep_vars = {}

    def _java_jar_gen_class_root(self, path, name):
        """Gen class root. """
        return os.path.join(self.build_path, path, '%s_classes' % name)

    def _dep_is_jar_to_compile(self, dep):
        """Check the target is java_jar target or not. """
        targets = self.blade.get_build_targets()
        target_type = targets[dep].type
        return ('java_jar' in target_type and 'prebuilt' not in target_type)

    def _java_jar_rules_prepare_dep(self, new_src):
        """Prepare building java jars, make class root and other work. """
        env_name = self._env_name()

        new_dep_source_list = []
        cmd_var = '%s_cmd_dep_var_' % self.name
        dep_cmd_var = ''
        cmd_var_idx = 0
        for dep_src in self.java_jar_dep_source_list:
            dep_dir = relative_path(dep_src[0], dep_src[1])
            new_path = os.path.join(new_src, dep_dir)
            if dep_dir != '.':
                new_dep_source_list.append(new_path)
            cmd_var_id = cmd_var + str(cmd_var_idx)
            if cmd_var_idx == 0:
                dep_cmd_var = cmd_var_id
            if not new_path in self.java_jar_cmd_list:
                self._write_rule('%s = %s.Command("%s", "", [Mkdir("%s")])' % (
                        cmd_var_id,
                        env_name,
                        new_path,
                        new_path))
                self.cmd_var_list.append(cmd_var_id)
                self.java_jar_cmd_list.append(new_path)
                cmd_var_idx += 1
            cmd_var_id = cmd_var + str(cmd_var_idx)
            cmd_var_idx += 1
            cmd = 'cp %s/*.java %s' % (dep_src[0], new_path)
            if dep_dir != '.':
                src_dir = dep_src[0]
            else:
                src_dir = ''
            self._write_rule('%s = %s.Command("%s/dummy_file_%s", "%s", ["%s"])' % (
                    cmd_var_id,
                    env_name,
                    new_path,
                    cmd_var_idx,
                    src_dir,
                    cmd))
            self.cmd_var_list.append(cmd_var_id)

        targets = self.blade.get_build_targets()
        if dep_cmd_var:
            for dep in self.expanded_deps:
                explict_files_depended = targets[dep].data.get('java_sources_explict_dependency')
                if explict_files_depended:
                    self._write_rule('%s.Depends(%s, %s)' % (
                                      env_name,
                                      dep_cmd_var,
                                      explict_files_depended))

        self._generate_target_explict_dependency(self.cmd_var_list)
        self.java_jar_after_dep_source_list = new_dep_source_list

    def _java_jar_deps_list(self, deps):
        """Returns a jar list string that this targets depends on. """
        jar_list = []
        for jar in deps:
            if not jar:
                continue

            if not self._dep_is_jar_to_compile(jar):
                continue

            jar_name = '%s.jar' % jar[1]
            jar_path = os.path.join(self.build_path, jar[0], jar_name)
            jar_list.append(jar_path)
        return jar_list

    def _java_jar_rules_compile_src(self,
                                    target_source_list,
                                    new_src,
                                    pack_list,
                                    classes_var_list):
        """Compile the java sources. """
        env_name = self._env_name()
        class_root = self._java_jar_gen_class_root(self.path,
                                                   self.name)
        jar_list = self._java_jar_deps_list(self.expanded_deps)
        classpath_list = self.java_classpath_list
        classpath = ':'.join(classpath_list + jar_list)

        new_target_source_list = []
        for src_dir in target_source_list:
            rel_path = relative_path(src_dir, self.path)
            pos = rel_path.find('/')
            package = rel_path[pos + 1:]
            new_src_path = os.path.join(new_src, package)
            new_target_source_list.append(new_src_path)

            cmd_var = '%s_cmd_src_var_' % self.name
            cmd_var_idx = 0
            if not new_src_path in self.java_jar_cmd_list:
                cmd_var_id = cmd_var + str(cmd_var_idx)
                self._write_rule('%s = %s.Command("%s", "", [Mkdir("%s")])' % (
                        cmd_var_id,
                        env_name,
                        new_src_path,
                        new_src_path))
                cmd_var_idx += 1
                self.java_jar_cmd_list.append(new_src_path)
            cmd_var_id = cmd_var + str(cmd_var_idx)
            cmd_var_idx += 1
            cmd = 'cp %s/*.java %s' % (src_dir, new_src_path)
            self._write_rule('%s = %s.Command("%s/dummy_src_file_%s", "%s", ["%s"])' % (
                    cmd_var_id,
                    env_name,
                    new_src_path,
                    cmd_var_idx,
                    src_dir,
                    cmd))
            self.cmd_var_list.append(cmd_var_id)

        new_target_idx = 0
        classes_var = '%s_classes' % (
                self._generate_variable_name(self.path, self.name))

        java_config = configparse.blade_config.get_config('java_config')
        source_version = java_config['source_version']
        target_version = java_config['target_version']
        javac_cmd = 'javac'
        if source_version:
            javac_cmd += ' -source %s' % source_version
        if target_version:
            javac_cmd += ' -target %s' % target_version
        if not classpath:
            javac_class_path = ''
        else:
            javac_class_path = ' -classpath %s' % classpath
        javac_classes_out = ' -d %s' % class_root
        javac_source_path = ' -sourcepath %s' % new_src

        no_dup_source_list = []
        for dep_src in self.java_jar_after_dep_source_list:
            if not dep_src in no_dup_source_list:
                no_dup_source_list.append(dep_src)
        for src in new_target_source_list:
            if not src in no_dup_source_list:
                no_dup_source_list.append(src)

        source_files_list = []
        for src_dir in no_dup_source_list:
            srcs = os.path.join(src_dir, '*.java')
            source_files_list.append(srcs)

        cmd = javac_cmd + javac_class_path + javac_classes_out
        cmd += javac_source_path + ' ' + ' '.join(source_files_list)
        dummy_file = '%s_dummy_file_%s' % (
                self.name, str(new_target_idx))
        new_target_idx += 1
        class_root_dummy = os.path.join(class_root, dummy_file)
        self._write_rule('%s = %s.Command("%s", "", ["%s"])' % (
                classes_var,
                env_name,
                class_root_dummy,
                cmd))

        # Find out the java_jar depends
        targets = self.blade.get_build_targets()
        for dep in self.expanded_deps:
            dep_java_jar_list = targets[dep].data.get('java_jars')
            if dep_java_jar_list:
                self._write_rule('%s.Depends(%s, %s)' % (
                    env_name,
                    classes_var,
                    dep_java_jar_list))

        self._generate_target_explict_dependency(classes_var)

        for cmd in self.cmd_var_list:
            self._write_rule('%s.Depends(%s, %s)' % (
                    env_name,
                    classes_var,
                    cmd))

        self.java_classpath_list.append(class_root)
        classes_var_list.append(classes_var)
        pack_list.append(class_root)

    def _java_jar_rules_make_jar(self, pack_list, classes_var_list):
        """Make the java jar files, pack the files that the target needs. """
        env_name = self._env_name()
        target_base_dir = os.path.join(self.build_path, self.path)

        cmd_jar = '%s_cmd_jar' % self.name
        cmd_var = '%s_cmd_jar_var_' % self.name
        cmd_idx = 0
        cmd_var_id = ''
        cmd_list = []
        targets = self.blade.get_build_targets()
        build_file = os.path.join(self.blade.get_root_dir(), 'BLADE_ROOT')
        for class_path in pack_list:
            # need to place one dummy file into the source folder for user builder
            build_file_dst = os.path.join(class_path, 'BLADE_ROOT')
            if not build_file_dst in self.java_jar_cmd_list:
                self._write_rule('%s = %s.Command("%s", "%s", [Copy("%s", "%s")])' % (
                        cmd_jar,
                        env_name,
                        build_file_dst,
                        build_file,
                        build_file_dst,
                        build_file))
                cmd_list.append(cmd_jar)
                self.java_jar_cmd_list.append(build_file_dst)
            for key in self.expanded_deps:
                f = targets[key].data.get('jar_packing_files')
                if not f:
                    continue
                cmd_var_id = cmd_var + str(cmd_idx)
                f_dst = os.path.join(class_path, os.path.basename(f[0]))
                if not f_dst in self.java_jar_cmd_list:
                    self._write_rule('%s = %s.Command("%s", "%s", \
                            [Copy("$TARGET","$SOURCE")])' % (
                                    cmd_var_id,
                                    env_name,
                                    f_dst,
                                    f[0]))
                    self.java_jar_cmd_list.append(f_dst)
                    cmd_list.append(cmd_var_id)
                    cmd_idx += 1

            rel_path = relative_path(class_path, target_base_dir)
            class_path_name = rel_path.replace('/', '_')
            jar_var = '%s_%s_jar' % (
                self._generate_variable_name(self.path, self.name),
                    class_path_name)
            jar_target = '%s.jar' % self._target_file_path()
            jar_target_object = '%s.jar' % jar_target
            cmd_remove_var = 'cmd_remove_%s' % jar_var
            removed = False
            if (not jar_target in self.java_jar_cmd_list) and (
                os.path.exists(jar_target)):
                self._write_rule('%s = %s.Command("%s", "", [Delete("%s")])' % (
                        cmd_remove_var,
                        env_name,
                        jar_target_object,
                        jar_target))
                removed = True
            self._write_rule('%s = %s.BladeJar(["%s"], "%s")' % (
                    jar_var,
                    env_name,
                    jar_target,
                    build_file_dst))
            self.data['java_jars'].append(jar_target)

            for dep_classes_var in classes_var_list:
                if dep_classes_var:
                    self._write_rule('%s.Depends(%s, %s)' % (
                            env_name, jar_var, dep_classes_var))
            for cmd in cmd_list:
                self._write_rule('%s.Depends(%s, %s)' % (
                        env_name, jar_var, cmd))
            if removed:
                self._write_rule('%s.Depends(%s, %s)' % (
                        env_name, jar_var, cmd_remove_var))

    def _prebuilt_java_jar_build_path(self):
        """The build path for pre build java jar. """
        return os.path.join(self.build_path,
                            self.path,
                            '%s.jar' % self.name)

    def _prebuilt_java_jar_src_path(self):
        """The source path for pre build java jar. """
        return os.path.join(self.path, '%s.jar' % self.name)

    def _prebuilt_java_jar(self):
        """The pre build java jar rules. """
        self._write_rule(
                'Command("%s", "%s", Copy("$TARGET", "$SOURCE"))' % (
                    self._prebuilt_java_jar_build_path(),
                    self._prebuilt_java_jar_src_path()))

    def scons_rules(self):
        """scons_rules.

        Description
        -----------
        It outputs the scons rules according to user options.

        """
        self._clone_env()

        if self.type == 'prebuilt_java_jar':
            self._prebuilt_java_jar()
            return

        env_name = self._env_name()
        class_root = self._java_jar_gen_class_root(self.path,
                                                   self.name)

        targets = self.blade.get_build_targets()

        for key in self.expanded_deps:
            self.cmd_var_list += targets[key].data.get('java_dep_var', [])

        self.java_jar_dep_source_list = []
        for key in self.expanded_deps:
            dep_target = targets[key]
            sources = dep_target.data.get('java_sources')
            if sources:
                self.java_jar_dep_source_list.append(sources)

        self.java_classpath_list = []
        for key in self.expanded_deps:
            class_path = targets[key].data.get('jar_class_path')
            if class_path:
                self.java_classpath_list.append(class_path)

        # make unique
        self.java_jar_dep_source_list = list(set(self.java_jar_dep_source_list))

        if not class_root in self.java_jar_cmd_list:
            self._write_rule('%s.Command("%s", "", [Mkdir("%s")])' % (
                    env_name, class_root, class_root))
            self.java_jar_cmd_list.append(class_root)

        target_source_list = []
        for src_dir in self.srcs:
            java_src = os.path.join(self.path, src_dir)
            if not java_src in target_source_list:
                target_source_list.append(java_src)

        new_src_dir = ''
        src_dir = '%s_src' % self.name
        new_src_dir = os.path.join(self.build_path, self.path, src_dir)
        if not new_src_dir in self.java_jar_cmd_list:
            self._write_rule('%s.Command("%s", "", [Mkdir("%s")])' % (
                    env_name,
                    new_src_dir,
                    new_src_dir))
            self.java_jar_cmd_list.append(new_src_dir)

        pack_list = []
        classes_var_list = []
        if self.java_jar_dep_source_list:
            self._java_jar_rules_prepare_dep(new_src_dir)

        self._java_jar_rules_compile_src(target_source_list,
                                         new_src_dir,
                                         pack_list,
                                         classes_var_list)

        self._java_jar_rules_make_jar(pack_list, classes_var_list)


def java_jar(name,
             srcs=[],
             deps=[],
             prebuilt=False,
             pre_build=False,
             **kwargs):
    """Define java_jar target. """
    target = JavaJarTarget(name,
                           srcs,
                           deps,
                           prebuilt or pre_build,
                           blade.blade,
                           kwargs)
    if pre_build:
        console.warning('//%s:%s: "pre_build" has been deprecated, '
                        'please use "prebuilt"' % (target.path,
                                                   target.name))
    blade.blade.register_target(target)


build_rules.register_function(java_jar)
