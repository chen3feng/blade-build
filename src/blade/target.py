# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the target module which is the super class
 of all of the scons targets.

"""

from __future__ import absolute_import

import os
import string

from blade import config
from blade import console
from blade.blade_util import var_to_list, iteritems


def _normalize_one(target, working_dir):
    """Normalize target from command line form into canonical form.

    Target canonical form: dir:name
        dir: relative to blade_root_dir, use '.' for blade_root_dir
        name: name  if target is dir:name
              '*'   if target is dir
              '...' if target is dir/...
    """
    if target.startswith('//'):
        target = target[2:]
    elif target.startswith('/'):
        console.error_exit('Invalid target "%s" starting from root path.' % target)
    else:
        if working_dir != '.':
            target = os.path.join(working_dir, target)

    if ':' in target:
        path, name = target.rsplit(':', 1)
    else:
        if target.endswith('...'):
            path = target[:-3]
            name = '...'
        else:
            path = target
            name = '*'
    path = os.path.normpath(path)
    return '%s:%s' % (path, name)


def normalize(targets, working_dir):
    """Normalize target list from command line form into canonical form."""
    return [_normalize_one(target, working_dir) for target in targets]


class Target(object):
    """Abstract target class.

    This class should be derived by subclass like CcLibrary CcBinary
    targets, etc.

    """

    def __init__(self,
                 name,
                 target_type,
                 srcs,
                 deps,
                 visibility,
                 blade,
                 kwargs):
        """Init method.

        Init the target.

        """
        self.blade = blade
        self.build_path = self.blade.get_build_path()
        current_source_path = self.blade.get_current_source_path()
        self.target_database = self.blade.get_target_database()

        self.key = (current_source_path, name)
        self.fullname = '%s:%s' % self.key
        self.name = name
        self.path = current_source_path
        self.type = target_type
        self.srcs = srcs
        self.deps = []
        self.expanded_deps = []
        self.visibility = 'PUBLIC'
        self.env_name = None
        self.data = {}
        self.data['test_timeout'] = config.get_item('global_config', 'test_timeout')
        # Keep track of scons variables defined by scons rules
        # generated by this target. Note that one blade target
        # may correspond to several scons variables:
        # proto_library: static lib/shared lib/jar variables
        self.data['targets'] = {}
        self.data['default_target'] = ''

        self._check_name()
        self._check_kwargs(kwargs)
        self._check_srcs()
        self._check_deps(deps)
        self._init_target_deps(deps)
        self._init_visibility(visibility)
        self.build_rules = []
        self.data['generated_hdrs'] = []

    def dump(self):
        """Dump to a dict"""
        target = {
            'type': self.type,
            'path': self.path,
            'name': self.name,
            'srcs': self.srcs,
            'deps': self.deps,
            'visibility': self.visibility,
        }
        target.update(self.data)
        return target

    def _clone_env(self):
        """Clone target's environment. """
        self._write_rule('%s = top_env.Clone()' % self._env_name())

    def _prepare_to_generate_rule(self):
        """Should be overridden. """
        console.error_exit('_prepare_to_generate_rule should be overridden in subclasses')

    def _check_name(self):
        if '/' in self.name:
            console.error_exit('//%s: Invalid target name, should not contain dir part.'
                               % self.fullname)

    def _check_kwargs(self, kwargs):
        if kwargs:
            console.error_exit('//%s: unrecognized options %s' % (
                self.fullname, kwargs))

    def _allow_duplicate_source(self):
        """Whether the target allows duplicate source file with other targets. """
        return False

    # Keep the relationship of all src -> target.
    # Used by build rules to ensure that a source file occurs in
    # exactly one target(only library target).
    __src_target_map = {}

    def _check_srcs(self):
        """Check source files.

        """
        dups = []
        srcset = set()
        for s in self.srcs:
            if s in srcset:
                dups.append(s)
            else:
                srcset.add(s)
        if dups:
            console.error_exit('%s Duplicate source file paths: %s ' % (
                self.fullname, dups))

        # Check if one file belongs to two different targets.
        action = config.get_item('global_config', 'duplicated_source_action')
        for s in self.srcs:
            if '..' in s or s.startswith('/'):
                console.error_exit('%s Invalid source file path: %s. '
                                   'can only be relative path, and must in current directory '
                                   'or subdirectories.' % (self.fullname, s))

            src = os.path.normpath(os.path.join(self.path, s))
            target = self.fullname, self._allow_duplicate_source()
            if src not in Target.__src_target_map:
                Target.__src_target_map[src] = target
            else:
                target_existed = Target.__src_target_map[src]
                if target_existed != target:
                    # Always preserve the target which disallows
                    # duplicate source files in the map
                    if target_existed[1]:
                        Target.__src_target_map[src] = target
                    elif target[1]:
                        pass
                    else:
                        message = 'Source file %s belongs to {%s, %s}' % (
                            s, target_existed[0], target[0])
                        if action == 'error':
                            console.error_exit(message)
                        elif action == 'warning':
                            console.warning(message)

    def _add_hardcode_library(self, hardcode_dep_list):
        """Add hardcode dep list to key's deps. """
        for dep in hardcode_dep_list:
            dkey = self._convert_string_to_target_helper(dep)
            if dkey[0] == '#':
                self._add_system_library(dkey, dep)
            if dkey not in self.expanded_deps:
                self.expanded_deps.append(dkey)

    def _add_system_library(self, key, name):
        """Add system library entry to database. """
        if key not in self.target_database:
            lib = SystemLibrary(name, self.blade)
            self.blade.register_target(lib)

    def _add_location_reference_target(self, m):
        """

        Parameters
        -----------
        m: A match object capturing the key and type of the referred target

        Returns
        -----------
        (key, type): the key and type of the referred target

        Description
        -----------
        Location reference makes it possible to refer to the build output of
        another target in the code base.

        General form:
            $(location //path/to:target)

        Some target types may produce more than one output according to the
        build options. Then each output can be referenced by an additional
        type tag:
            $(location //path:name)         # default target output
            $(location //path:name jar)     # jar output
            $(location //path:name so)      # so output

        Note that this method accepts a match object instead of a simple str.
        You could match/search/sub location references in a string with functions
        or RegexObject in re module. For example:

            m = {location regular expression}.search(s)
            if m:
                key, type = self._add_location_reference_target(m)
            else:
                # Not a location reference

        """
        if m:
            key, type = m.groups()
            if not type:
                type = ''
            type = type.strip()
            key = self._unify_dep(key)
            if key not in self.expanded_deps:
                self.expanded_deps.append(key)
            if key not in self.deps:
                self.deps.append(key)
            return key, type

    def _unify_dep(self, dep):
        """Unify dep to key"""
        if dep[0] == ':':
            # Depend on library in current directory
            dkey = (os.path.normpath(self.path), dep[1:])
        elif dep.startswith('//'):
            # Depend on library in remote directory
            if not ':' in dep:
                raise Exception('Wrong format in %s' % self.fullname)
            (path, lib) = dep[2:].rsplit(':', 1)
            dkey = (os.path.normpath(path), lib)
        elif dep.startswith('#'):
            # System libaray, they don't have entry in BUILD so we need
            # to add deps manually.
            dkey = ('#', dep[1:])
            self._add_system_library(dkey, dep)
        else:
            # Depend on library in relative subdirectory
            if not ':' in dep:
                raise Exception('Wrong format in %s' % self.fullname)
            (path, lib) = dep.rsplit(':', 1)
            if '..' in path:
                raise Exception("Don't use '..' in path")
            dkey = (os.path.normpath('%s/%s' % (
                self.path, path)), lib)

        return dkey

    def _init_target_deps(self, deps):
        """Init the target deps.

        Parameters
        -----------
        deps: the deps list in BUILD file.

        Description
        -----------
        Add target into target database and init the deps list.

        """
        for d in deps:
            dkey = self._unify_dep(d)
            if dkey not in self.expanded_deps:
                self.expanded_deps.append(dkey)
            if dkey not in self.deps:
                self.deps.append(dkey)

    def _check_format(self, t):
        """

        Parameters
        -----------
        t: could be a dep or visibility specified in BUILD file

        Description
        -----------
        Do some basic format check.

        """
        if not (t.startswith(':') or t.startswith('#') or
                t.startswith('//') or t.startswith('./')):
            console.error_exit('%s: Invalid %s.' % (self.fullname, t))
        if t.count(':') > 1:
            console.error_exit('%s: Invalid %s, missing \',\' between?' %
                               (self.fullname, t))

    def _check_deps(self, deps):
        """_check_deps

        Parameters
        -----------
        deps: the deps list in BUILD file

        Description
        -----------
        Check whether deps are in valid format.

        """
        for dep in deps:
            self._check_format(dep)

    def _init_visibility(self, visibility):
        """

        Parameters
        -----------
        visibility: the visibility list in BUILD file

        Description
        -----------
        Visibility determines whether another target is able to depend
        on this target.

        Visibility specify a list of targets in the same form as deps,
        i.e. //path/to:target. The default value of visibility is PUBLIC,
        which means this target is visible globally within the code base.
        Note that targets inside the same BUILD file are always visible
        to each other.

        """
        if visibility is None:
            return

        visibility = var_to_list(visibility)
        if visibility == ['PUBLIC']:
            return

        self.visibility = []
        for v in visibility:
            self._check_format(v)
            key = self._unify_dep(v)
            if key not in self.visibility:
                self.visibility.append(key)

    def _check_deprecated_deps(self):
        """check that whether it depends upon deprecated target.

        It should be overridden in subclass.

        """
        pass

    def _expand_deps_generation(self):
        """Expand the generation process and generated rules of dependencies.

        Such as, given a proto_library target, it should generate Java rules
        in addition to C++ rules once it's depended by a java_library target.
        """
        pass

    def _get_java_pack_deps(self):
        """_get_java_pack_deps

        Returns
        -----------
        A tuple of (target jars, maven jars)

        Description
        -----------
        Return java package dependencies excluding provided dependencies

        target jars represent either a scons var or a path to jar archive
        depending on the underlying build system in use. Each jar is built
        by java_library(prebuilt)/scala_library/proto_library.

        maven jars represent maven artifacts within local repository built
        by maven_jar(...).
        """
        return [], []

    def _regular_variable_name(self, var):
        """Replace the chars of var that scons doesn't recognize. """
        return var.translate(string.maketrans(',-/.+*', '______'))

    def _generate_variable_name(self, path, name, suffix=''):
        """_generate_variable_name.

        Parameters
        -----------
        path: the target's path
        name: the target's name
        suffix: the suffix to be appended to the variable

        Returns
        -----------
        The variable that contains target path, target name and suffix

        Description
        -----------
        Concatenating target path, target name and suffix and returns.

        """
        suffix_str = ''
        if suffix:
            suffix_str = '_suFFix_%s' % suffix
        return 'v_%s_mAgIc_%s%s' % (self._regular_variable_name(path),
                                    self._regular_variable_name(name),
                                    suffix_str)

    def _env_name(self):
        """_env_name.

        Returns
        -----------
        The environment variable

        Description
        -----------
        Concatenating target path, target name to be environment var and returns.

        """
        if self.env_name is None:
            self.env_name = 'env_%s' % self._generate_variable_name(self.path,
                                                                    self.name)
        return self.env_name

    def _var_name(self, suffix=''):
        """_var_name.

        Returns
        -----------
        The scons variable name

        """
        return self._generate_variable_name(self.path, self.name, suffix)

    def _var_name_of(self, name, suffix=''):
        """_var_name_of.

        Returns
        -----------
        The scons variable name

        """
        return self._generate_variable_name(self.path, name, suffix)

    def _source_file_path(self, name):
        """_source_file_path.

        Parameters
        -----------
        name: the source's name

        Returns
        -----------
        The source's full path in full blade dir tree

        """
        return os.path.normpath(os.path.join(self.path, name))

    def _target_file_path(self, name=''):
        """_target_file_path.

        Parameters
        -----------
        name: the target's name

        Returns
        -----------
        The target's path below building path

        Description
        -----------
        Concatenating building path, target path and target name to be full
        file path.

        """
        if not name:
            name = self.name
        return os.path.join(self.build_path, self.path, name)

    def _add_target_var(self, target_type, scons_var):
        """

        Parameters
        -----------
        target_type: type of the scons variable as key in the dictionary
        scons_var: the scons variable name as value in the dictionary

        Description
        -----------
        Keep track of the scons variable built by scons rules.
        Set the default target if needed.

        """
        self.data['targets'][target_type] = scons_var
        if not self.data['default_target']:
            self.data['default_target'] = scons_var

    def _add_default_target_var(self, target_type, scons_var):
        """

        Parameters
        -----------
        target_type: type of the scons variable as key in the dictionary
        scons_var: the scons variable name as value in the dictionary

        Description
        -----------
        Keep track of the default scons variable which could be referenced
        later without specifying type

        """
        self.data['default_target'] = scons_var
        self._add_target_var(target_type, scons_var)

    def _get_target_var(self, target_type=''):
        """

        Parameters
        -----------
        target_type: type of the scons variable

        Returns
        -----------
        The scons variable name

        Description
        -----------
        Return the scons variable corresponding to the type passed in,
        return empty if type doesn't exist in the dictionary

        """
        if target_type:
            return self.data['targets'].get(target_type, '')
        return self.data['default_target']

    def _get_target_vars(self):
        """

        Returns
        -----------
        All the scons variable names built by scons rules

        """
        return self.data['targets'].values()

    def _add_target_file(self, label, path):
        """

        Parameters
        -----------
        label: label of the target file as key in the dictionary
        path: the path of target file as value in the dictionary

        Description
        -----------
        Keep track of the output files built by the target itself.
        Set the default target if needed.

        """
        self.data['targets'][label] = path
        if not self.data['default_target']:
            self.data['default_target'] = path

    def _add_default_target_file(self, label, path):
        """

        Parameters
        -----------
        label: label of the target file as key in the dictionary
        path: the path of target file as value in the dictionary

        Description
        -----------
        Keep track of the default target file which could be referenced
        later without specifying label

        """
        self.data['default_target'] = path
        self._add_target_file(label, path)

    def _get_target_file(self, label=''):
        """

        Parameters
        -----------
        label: label of the file built by the target

        Returns
        -----------
        The target file path or list of file paths

        Description
        -----------
        Return the target file path corresponding to the specified label,
        return empty if label doesn't exist in the dictionary

        """
        if label:
            return self.data['targets'].get(label, '')
        return self.data['default_target']

    def _get_target_files(self):
        """

        Returns
        -----------
        All the target files built by the target itself

        """
        results = set()
        for _, v in iteritems(self.data['targets']):
            if isinstance(v, list):
                results.update(v)
            else:
                results.add(v)
        return sorted(results)

    def _generate_header_files(self):
        """Whether this target generates header files during building. """
        return False

    def _write_rule(self, rule):
        """_write_rule.

        Parameters
        -----------
        rule: the rule generated by certain target

        Description
        -----------
        Append the rule to the buffer at first.

        """
        self.build_rules.append('%s\n' % rule)

    def scons_rules(self):
        """scons_rules.

        This method should be implemented in subclass.

        """
        console.error_exit('%s: should be subclassing' % self.type)

    def ninja_rules(self):
        """Generate ninja rules for specific target. """
        raise NotImplementedError(self.fullname)

    def ninja_build(self, outputs, rule, inputs=None,
                    implicit_deps=None, order_only_deps=None,
                    variables=None, implicit_outputs=None):
        """Generate a ninja build statement with specified parameters. """
        outs = var_to_list(outputs)
        if implicit_outputs:
            outs.append('|')
            outs += implicit_outputs
        ins = []
        if inputs:
            ins = var_to_list(inputs)
        if implicit_deps:
            ins.append('|')
            ins += implicit_deps
        if order_only_deps:
            ins.append('||')
            ins += order_only_deps
        self._write_rule('build %s: %s %s' % (' '.join(outs), rule, ' '.join(ins)))

        if variables:
            assert isinstance(variables, dict)
            for name, v in iteritems(variables):
                if v:
                    self._write_rule('  %s = %s' % (name, v))
                else:
                    self._write_rule('  %s =' % name)

    def get_rules(self):
        """Return build rules. """
        return self.build_rules

    def _convert_string_to_target_helper(self, target_string):
        """
        Converting a string like thirdparty/gtest:gtest to tuple
        (target_path, target_name)
        """
        if target_string:
            if target_string.startswith('#'):
                return ('#', target_string[1:])
            elif target_string.find(':') != -1:
                path, name = target_string.split(':')
                path = path.strip()
                if path.startswith('//'):
                    path = path[2:]
                return (path, name.strip())

        console.error_exit('invalid target lib format: %s, '
                           'should be #lib_name or lib_path:lib_name' %
                           target_string)


class SystemLibrary(Target):
    def __init__(self, name, blade):
        name = name[1:]
        Target.__init__(self, name, 'system_library', [], [], None, blade, {})
        self.key = ('#', name)
        self.fullname = '%s:%s' % self.key
        self.path = '#'
