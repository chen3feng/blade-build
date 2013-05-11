"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the target module which is the super class
 of all of the scons targets.

"""


import os
import string

import console
from blade_util import var_to_list


class Target(object):
    """A scons target father class.

    This class should be derived by subclass like cc_library cc_binary
    targets, etc.

    """
    def __init__(self,
                 name,
                 target_type,
                 srcs,
                 deps,
                 blade,
                 kwargs):
        """Init method.

        Init the target.

        """
        self.blade = blade
        self.build_path = self.blade.get_build_path()
        self.current_source_path = self.blade.get_current_source_path()
        self.target_database = self.blade.get_target_database()
        srcs_list = srcs

        self._check_deps_in_build_file(name, deps)

        self.key = (self.current_source_path, name)
        self.data = {
                     'name' : name,
                     'path' : self.current_source_path,
                     'type' : target_type,
                     'srcs' : srcs_list,
                     'deps' : [],
                     'options' : {},
                     'direct_deps' : []
                    }
        self.target_database[self.key] = self.data

        self._check_name()
        self._check_kwargs(kwargs)
        self._check_srcs()
        self._init_target_deps(deps)
        self.scons_rule_buf = []

    def _clone_env(self):
        """Clone target's environment. """
        self._write_rule("%s = top_env.Clone()" % self._env_name())

    def _prepare_to_generate_rule(self):
        """Should be overridden. """
        console.error_exit("_prepare_to_generate_rule should be overridden in subclasses")

    def _check_name(self):
        if '/' in self.data.get('name', ''):
            console.error_exit('//%s:%s: Invalid target name, should not contain dir part.' % (
                self.data['path'], self.data['name']))

    def _check_kwargs(self, kwargs):
        if kwargs:
            console.warning("//%s:%s: unrecognized options %s"  % (
                    self.data['path'], self.data['name'], kwargs))

    def _check_srcs(self):
        """Check source files.

        Parameters
        -----------
        None

        Returns
        -----------
        None

        Description
        -----------
        It will warn if one file belongs to two different targets.

        """
        target_srcs_map = self.blade.get_target_srcs_map()
        allow_dup_src_type_list = ['cc_binary', 'cc_test', 'dynamic_cc_binary']
        for s in self.data['srcs']:
            if '..' in s or s.startswith('/'):
                raise Exception, (
                    'Invalid source file path: %s. '
                    'can only be relative path, and must in current directory or '
                    'subdirectories') % s

            src_key = os.path.normpath('%s/%s' % (self.data['path'], s))
            src_value = '%s %s:%s' % (
                    self.data['type'], self.current_source_path, self.data['name'])
            if src_key in target_srcs_map:
                value_existed = target_srcs_map[src_key]
                if not (value_existed.split(': ')[0] in allow_dup_src_type_list and
                       self.data['type'] in allow_dup_src_type_list):
                    # Just warn here, not raising exception
                    console.warning( 'Source file %s belongs to both %s and %s' % (
                            s, target_srcs_map[src_key], src_value))
            target_srcs_map[src_key] = src_value

    def _add_hardcode_library(self, hardcode_dep_list):
        """Add hardcode dep list to key's deps. """
        for dep in hardcode_dep_list:
            dkey = self._convert_string_to_target_helper(dep)
            if dkey[0] == '#':
                self._add_system_library(dkey, dep)
            if dkey not in self.target_database[self.key]['deps']:
                self.target_database[self.key]['deps'].append(dkey)

    def _add_system_library(self, key, name):
        """Add system library entry to database. """
        if key not in self.target_database:
            self.target_database[key] = {
                                         'type' : 'system_library',
                                         'srcs' : '',
                                         'deps' : [],
                                         'path' : self.current_source_path,
                                         'name' : name,
                                         'options': {}
                                        }

    def _init_target_deps(self, deps):
        """Init the target deps.

        Parameters
        -----------
        deps: the deps list in BUILD file.

        Returns
        -----------
        None

        Description
        -----------
        Add target into target database and init the deps list.

        """
        for d in deps:
            if d[0] == ':':
                # Depend on library in current directory
                dkey = (os.path.normpath(self.current_source_path), d[1:])
            elif d.startswith('//'):
                # Depend on library in remote directory
                if not ':' in d:
                    raise Exception, 'Wrong format in %s:%s' % (
                            self.current_source_path, self.data['name'])
                (path, lib) = d[2:].rsplit(':', 1)
                dkey = (os.path.normpath(path), lib)
            elif d.startswith('#'):
                # System libaray, they don't have entry in BUILD so we need
                # to add deps manually.
                dkey = ('#', d[1:])
                self._add_system_library(dkey, d)
            else:
                # Depend on library in relative subdirectory
                if not ':' in d:
                    raise Exception, 'Wrong format in %s:%s' % (
                            self.current_source_path, self.data['name'])
                (path, lib) = d.rsplit(':', 1)
                if '..' in path:
                    raise Exception, "Don't use '..' in path"
                dkey = (os.path.normpath('%s/%s' % (
                                          self.current_source_path, path)), lib)

            if dkey not in self.target_database[self.key]['deps']:
                self.target_database[self.key]['deps'].append(dkey)

            if dkey not in self.target_database[self.key]['direct_deps']:
                self.target_database[self.key]['direct_deps'].append(dkey)


    def _check_deps_in_build_file(self, name, deps):
        """_check_deps_in_build_file.

        Parameters
        -----------
        name: the target's name
        deps: the deps list in BUILD file

        Returns
        -----------
        None

        Description
        -----------
        Checks that whether users' build file is consistent with
        blade's rule.

        """
        for dep in deps:
            if not (dep.startswith(':') or dep.startswith('#') or
                dep.startswith('//') or dep.startswith('./')):
                console.error_exit('%s/%s: Invalid dep in %s.' % (
                    self.current_source_path, name, dep))
            if dep.count(':') > 1:
                console.error_exit('%s/%s: Invalid dep %s, missing \',\' between 2 deps?' %
                            (self.current_source_path, name, dep))

    def _check_deprecated_deps(self):
        """check that whether it depends upon deprecated target.

        It should be overridden in subclass.

        """
        pass

    def _regular_variable_name(self, var):
        """_regular_variable_name.

        Parameters
        -----------
        var: the variable to be modified

        Returns
        -----------
        s: the variable modified

        Description
        -----------
        Replace the chars that scons doesn't regconize.

        """
        return var.translate(string.maketrans(",-/.+*", "______"))

    def _generate_variable_name(self, path='', name='', suffix=''):
        """_generate_variable_name.

        Parameters
        -----------
        path: the target's path
        name: the target's name
        suffix: the suffix to be appened to the variable

        Returns
        -----------
        The variable that contains target path, target name and suffix

        Description
        -----------
        Concatinating target path, target name and suffix and returns.

        """
        suffix_str = ""
        if suffix:
            suffix_str = "_suFFix_%s" % suffix
        return "v_%s_mAgIc_%s%s" % (self._regular_variable_name(path),
                                    self._regular_variable_name(name),
                                    suffix_str)

    def _env_name(self):
        """_env_name.

        Parameters
        -----------
        None

        Returns
        -----------
        The environment variable

        Description
        -----------
        Concatinating target path, target name to be environment var and returns.

        """
        return "env_%s" % self._generate_variable_name(self.data['path'],
                                                       self.data['name'])

    def __fill_path_name(self, path, name):
        """fill the path and name to make them not None. """
        if not path:
            path = self.data['path']
        if not name:
            name = self.data['name']
        return path, name

    def _target_file_path(self, path='', name=''):
        """_target_file_path.

        Parameters
        -----------
        path: the target's path
        name: the target's name

        Returns
        -----------
        The target's path below building path

        Description
        -----------
        Concatinating building path, target path and target name to be full
        file path.

        """
        new_path, new_name = self.__fill_path_name(path, name)
        return os.path.join(self.build_path, new_path, new_name)

    def _generate_target_explict_dependency(self, target_files):
        """_generate_target_explict_dependency.

        Description
        -----------
        Generates dependency relationship that two targets have no dependency
        but it really needs when user specify it in BUILD file.

        1. gen_rule target should be needed by other targets

        """
        if not target_files:
            return
        env_name = self._env_name()
        files = var_to_list(target_files)
        files_str = ",".join(["%s" % f for f in files])
        if not self.blade.get_expanded():
            console.error_exit("logic error in Blade, error in _generate_target_explict_dependency")
        targets = self.blade.get_all_targets_expanded()
        files_map = self.blade.get_gen_rule_files_map()
        deps = targets[self.key]['deps']
        for d in deps:
            dep_target = targets[d]
            if dep_target['type'] == 'gen_rule':
                srcs_list = files_map[(dep_target['path'], dep_target['name'])]
                if srcs_list:
                    self._write_rule("%s.Depends([%s], [%s])" % (
                        env_name,
                        files_str,
                        srcs_list))

    def _write_rule(self, rule):
        """_write_rule.

        Parameters
        -----------
        rule: the rule generated by certain target

        Returns
        -----------
        None

        Description
        -----------
        Append the rule to the buffer at first.

        """
        self.scons_rule_buf.append('%s\n' % rule)

    def get_rules(self):
        """get_rules.

        Parameters
        -----------
        None.

        Returns
        -----------
        The scons rules buffer

        Description
        -----------
        Returns the buffer.

        """
        return self.scons_rule_buf

    def get(self, key=''):
        """get.

        Parameters
        -----------
        key: the key of the target's data

        Returns
        -----------
        The item(value) in target's data

        Description
        -----------
        Returns the target's data value when the key is in target's data map.

        """
        return self.data.get(key, None)

    def _convert_string_to_target_helper(self, target_string):
        """
        Converting a string like thirdparty/gtest:gtest to tuple
        (target_path, target_name)
        """
        bad_format = False
        if target_string:
            if target_string.startswith('#'):
                return ("#", target_string[1:])
            elif target_string.find(":") != -1:
                path, name = target_string.split(":")
                path = path.strip()
                if path.startswith("//"):
                    path = path[2:]
                return (path, name.strip())
            else:
                bad_format = True
        else:
            bad_format = True

        if bad_format:
            console.error_exit("invalid target lib format: %s, "
                       "should be #lib_name or lib_path:lib_name" % target_string)
