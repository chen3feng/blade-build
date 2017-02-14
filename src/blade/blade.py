# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the blade module which mainly holds the global database and
 do the coordination work between classes.

"""


import os

import configparse
import console

from blade_util import relative_path, cpu_count
from dependency_analyzer import analyze_deps
from load_build_files import load_targets
from blade_platform import SconsPlatform
from build_environment import BuildEnvironment
from rules_generator import SconsRulesGenerator
from binary_runner import BinaryRunner
from test_runner import TestRunner


# Global blade manager
blade = None


class Blade(object):
    """Blade. A blade manager class. """
    def __init__(self,
                 command_targets,
                 blade_path,
                 working_dir,
                 build_path,
                 blade_root_dir,
                 blade_options,
                 command):
        """init method.

        """
        self.__command_targets = command_targets
        self.__blade_path = blade_path
        self.__working_dir = working_dir
        self.__build_path = build_path
        self.__root_dir = blade_root_dir
        self.__options = blade_options
        self.__command = command

        # Source dir of current loading BUILD file
        self.__current_source_path = blade_root_dir

        # The direct targets that are used for analyzing
        self.__direct_targets = []

        # All command targets, make sure that all targets specified with ...
        # are all in the list now
        self.__all_command_targets = []

        # Given some targets specified in the command line, Blade will load
        # BUILD files containing these command line targets; global target
        # functions, i.e., cc_libarary, cc_binary and etc, in these BUILD
        # files will register targets into target_database, which then becomes
        # the input to dependency analyzer and SCons rules generator.  It is
        # notable that not all targets in target_database are dependencies of
        # command line targets.
        self.__target_database = {}

        # targets to build after loading the build files.
        self.__build_targets = {}

        # The targets keys list after sorting by topological sorting method.
        # Used to generate build rules in correct order.
        self.__sorted_targets_keys = []

        # The depended targets dict after topological sorting
        self.__depended_targets = {}

        # Inidcating that whether the deps list is expanded by expander or not
        self.__targets_expanded = False

        self.__scons_platform = SconsPlatform()
        self.build_environment = BuildEnvironment(self.__root_dir)

        self.svn_root_dirs = []

    def _get_normpath_target(self, command_target):
        """returns a tuple (path, name).

        path is a full path from BLADE_ROOT

        """
        target_path = relative_path(self.__working_dir, self.__root_dir)
        path, name = command_target.split(':')
        if target_path != '.':
            if path:
                path = target_path + '/' + path
            else:
                path = target_path
        path = os.path.normpath(path)
        return path, name

    def load_targets(self):
        """Load the targets. """
        console.info('loading BUILDs...')
        if self.__command == 'query' and getattr(self.__options,
            'depended', False):
            # For query depended command, always start from root with target ...
            # that is scanning the whole tree
            working_dir = self.__root_dir
        else:
            working_dir = self.__working_dir
        (self.__direct_targets,
         self.__all_command_targets,
         self.__build_targets) = load_targets(self.__command_targets,
                                                  working_dir,
                                                  self.__root_dir,
                                                  self)
        console.info('loading done.')
        return self.__direct_targets, self.__all_command_targets  # For test

    def analyze_targets(self):
        """Expand the targets. """
        console.info('analyzing dependency graph...')
        (self.__sorted_targets_keys,
         self.__depended_targets) = analyze_deps(self.__build_targets)
        self.__targets_expanded = True

        console.info('analyzing done.')
        return self.__build_targets  # For test

    def generate_build_rules(self):
        """Generate the constructing rules. """
        console.info('generating build rules...')
        build_rules_generator = SconsRulesGenerator('SConstruct',
                                                    self.__blade_path, self)
        rules_buf = build_rules_generator.generate_scons_script()
        console.info('generating done.')
        return rules_buf

    def generate(self):
        """Generate the build script. """
        self.load_targets()
        self.analyze_targets()
        if self.__command != 'query':
            self.generate_build_rules()

    def run(self, target):
        """Run the target. """
        key = self._get_normpath_target(target)
        runner = BinaryRunner(self.__build_targets,
                              self.__options,
                              self.__target_database)
        return runner.run_target(key)

    def test(self):
        """Run tests. """
        test_runner = TestRunner(self.__build_targets,
                                 self.__options,
                                 self.__target_database,
                                 self.__direct_targets)
        return test_runner.run()

    def query(self, targets):
        """Query the targets. """
        print_deps = getattr(self.__options, 'deps', False)
        print_depended = getattr(self.__options, 'depended', False)
        dot_file = getattr(self.__options, 'output_to_dot', '')
        print_dep_tree = getattr(self.__options, 'output_tree', False)
        result_map = self.query_helper(targets)
        if dot_file:
            print_mode = 0
            if print_deps:
                print_mode = 0
            if print_depended:
                print_mode = 1
            dot_file = os.path.join(self.__working_dir, dot_file)
            self.output_dot(result_map, print_mode, dot_file)
        else:
            if print_deps:
                if print_dep_tree:
                    self.query_dependency_tree(targets)
                else:
                    for key in result_map:
                        print '\n'
                        deps = result_map[key][0]
                        console.info('//%s:%s depends on the following targets:' % (
                                key[0], key[1]))
                        for d in deps:
                            print '%s:%s' % (d[0], d[1])
            if print_depended:
                for key in result_map:
                    print '\n'
                    depended_by = result_map[key][1]
                    console.info('//%s:%s is depended by the following targets:' % (
                            key[0], key[1]))
                    for d in depended_by:
                        print '%s:%s' % (d[0], d[1])
        return 0

    def print_dot_node(self, output_file, node):
        print >>output_file, '"%s:%s" [label = "%s:%s"]' % (node[0],
                                                            node[1],
                                                            node[0],
                                                            node[1])

    def print_dot_deps(self, output_file, node, target_set):
        targets = self.__build_targets
        deps = targets[node].deps
        for i in deps:
            if not i in target_set:
                continue
            print >>output_file, '"%s:%s" -> "%s:%s"' % (node[0],
                                                         node[1],
                                                         i[0],
                                                         i[1])

    def output_dot(self, result_map, print_mode, dot_file):
        f = open(dot_file, 'w')
        targets = result_map.keys()
        nodes = set(targets)
        for key in targets:
            nodes |= set(result_map[key][print_mode])
        print >>f, 'digraph blade {'
        for i in nodes:
            self.print_dot_node(f, i)
        for i in nodes:
            self.print_dot_deps(f, i, nodes)
        print >>f, '}'
        f.close()

    def query_helper(self, targets):
        """Query the targets helper method. """
        all_targets = self.__build_targets
        query_list = []
        target_path = relative_path(self.__working_dir, self.__root_dir)
        t_path = ''
        for t in targets:
            if t.find(':') != -1:
                key = t.split(':')
                if target_path == '.':
                    t_path = key[0]
                else:
                    t_path = target_path + '/' + key[0]
                t_path = os.path.normpath(t_path)
                query_list.append((t_path, key[1]))
            elif t.endswith('...'):
                t_path = os.path.normpath(target_path + '/' + t[:-3])
                for tkey in all_targets:
                    if tkey[0].startswith(t_path):
                        query_list.append((tkey[0], tkey[1]))
            else:
                t_path = os.path.normpath(target_path + '/' + t)
                for tkey in all_targets:
                    if tkey[0] == t_path:
                        query_list.append((t_path, tkey[1]))
        result_map = {}
        for key in query_list:
            deps = all_targets[key].expanded_deps
            # depended_by = [k for k in all_targets if key in all_targets[k].expanded_deps]
            depended_by = self.__depended_targets[key]
            result_map[key] = (sorted(deps), sorted(depended_by))
        return result_map

    def query_dependency_tree(self, targets):
        """Query the dependency tree of the specified targets. """
        query_targets = []
        for target in targets:
            if ':' not in target:
                console.error_exit(
                    'Target %s is not supported by dependency tree query. '
                    'The target should be in the format directory:name.' % target)
            path, name = target.split(':')
            relpath = os.path.relpath(self.__working_dir, self.__root_dir)
            path = os.path.normpath(os.path.join(relpath, path))
            query_targets.append((path, name))

        for key in query_targets:
            console.info('')
            self._query_dependency_tree(key, 0, self.__build_targets)
            console.info('')

    def _query_dependency_tree(self, key, level, build_targets):
        """Query the dependency tree of the specified target recursively. """
        path, name = key
        if level == 0:
            output = '%s:%s' % (path, name)
        elif level == 1:
            output = '%s %s:%s' % ('+-', path, name)
        else:
            output = '%s%s %s:%s' % ('|  ' * (level - 1), '+-', path, name)
        console.info(console.colors('end') + console.colors('gray') + output)
        for dkey in build_targets[key].deps:
            self._query_dependency_tree(dkey, level + 1, build_targets)

    def get_build_path(self):
        """The current building path. """
        return self.__build_path

    def get_root_dir(self):
        """Return the blade root path. """
        return self.__root_dir

    def set_current_source_path(self, current_source_path):
        """Set the current source path. """
        self.__current_source_path = current_source_path

    def get_current_source_path(self):
        """Get the current source path. """
        return self.__current_source_path

    def get_target_database(self):
        """Get the whole target database that haven't been expanded. """
        return self.__target_database

    def get_direct_targets(self):
        """Return the direct targets. """
        return self.__direct_targets

    def get_build_targets(self):
        """Get all the targets to be build. """
        return self.__build_targets

    def get_options(self):
        """Get the global command options. """
        return self.__options

    def is_expanded(self):
        """Whether the targets are expanded. """
        return self.__targets_expanded

    def register_target(self, target):
        """Register scons targets into the scons targets map.

        It is used to do quick looking.

        """
        key = target.key
        # Check whether there is already a key in database
        if key in self.__target_database:
            console.error_exit('Target %s is duplicate in //%s/BUILD' % (
                               target.name, target.path))
        self.__target_database[key] = target

    def _is_scons_object_type(self, target_type):
        """The types that shouldn't be registered into blade manager.

        Sholdn't invoke scons_rule method when it is not a scons target which
        could not be registered into blade manager, like system library.

        1. system_library

        """
        return target_type != 'system_library'

    def gen_targets_rules(self):
        """Get the build rules and return to the object who queries this. """
        rules_buf = []
        skip_test = getattr(self.__options, 'no_test', False)
        skip_package = not getattr(self.__options, 'generate_package', False)
        for k in self.__sorted_targets_keys:
            target = self.__build_targets[k]
            if not self._is_scons_object_type(target.type):
                continue
            scons_object = self.__target_database.get(k, None)
            if not scons_object:
                console.warning('not registered scons object, key %s' % str(k))
                continue
            if (skip_test and target.type.endswith('_test')
                and k not in self.__direct_targets):
                continue
            if (skip_package and target.type == 'package'
                and k not in self.__direct_targets):
                continue
            scons_object.scons_rules()
            rules = scons_object.get_rules()
            if rules:
                rules_buf.append('\n')
                rules_buf += rules
        return rules_buf

    def get_scons_platform(self):
        """Return handle of the platform class. """
        return self.__scons_platform

    def get_sources_keyword_list(self):
        """This keywords list is used to check the source files path.

        Ex, when users specifies warning=no, it could be used to check that
        the source files is under thirdparty or not. If not, it will warn
        users that this flag is used incorrectly.

        """
        keywords = ['thirdparty']
        return keywords

    def parallel_jobs_num(self):
        """Tune the jobs num. """
        # User has the highest priority
        user_jobs_num = self.__options.jobs
        if user_jobs_num > 0:
            return user_jobs_num

        # Calculate job numbers smartly
        jobs_num = 0
        distcc_enabled = configparse.blade_config.get_config('distcc_config')['enabled']

        if distcc_enabled and self.build_environment.distcc_env_prepared:
            # Distcc cost doesn;t much local cpu, jobs can be quite large.
            distcc_num = len(self.build_environment.get_distcc_hosts_list())
            jobs_num = min(max(int(1.5 * distcc_num), 1), 20)
        else:
            cpu_core_num = cpu_count()
            # machines with cpu_core_num > 4 is usually shared by multiple users,
            # set an upper bound to avoid interfering other users
            jobs_num = min(2 * cpu_core_num, 8)

        if jobs_num != user_jobs_num:
            console.info('tunes the parallel jobs number(-j N) to be %d' % (
                jobs_num))
        return jobs_num
