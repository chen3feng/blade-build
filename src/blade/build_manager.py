# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the blade module which mainly holds the global database and
 do the coordination work between classes.

"""

from __future__ import absolute_import
from __future__ import print_function

import json
import os
import sys
import time

from blade import config
from blade import console
from blade import target
from blade.binary_runner import BinaryRunner
from blade.blade_platform import BuildPlatform
from blade.blade_util import cpu_count
from blade.build_environment import BuildEnvironment
from blade.dependency_analyzer import analyze_deps
from blade.load_build_files import load_targets
from blade.rules_generator import NinjaRulesGenerator
from blade.rules_generator import SconsRulesGenerator
from blade.test_runner import TestRunner

# Global build manager instance
instance = None


class Blade(object):
    """Blade. A blade manager class. """

    # pylint: disable=too-many-public-methods
    def __init__(self,
                 command_targets,
                 load_targets,
                 blade_path,
                 working_dir,
                 build_path,
                 blade_root_dir,
                 blade_options,
                 command):
        """init method.

        """
        self.__command_targets = command_targets
        self.__load_targets = load_targets
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
        # functions, i.e., cc_library, cc_binary and etc, in these BUILD
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

        # Indicate whether the deps list is expanded by expander or not
        self.__targets_expanded = False

        self.__build_time = time.time()

        self.__build_platform = BuildPlatform()
        self.build_environment = BuildEnvironment(self.__root_dir)

        self.svn_root_dirs = []

        self._verify_history_path = os.path.join(build_path, '.blade_verify.json')
        self._verify_history = {
            'header_inclusion_dependencies': {},  # path(.H) -> mtime(modification time)
        }

    def load_targets(self):
        """Load the targets. """
        console.info('loading BUILDs...')
        (self.__direct_targets,
         self.__all_command_targets,
         self.__build_targets) = load_targets(self.__load_targets,
                                              self.__root_dir,
                                              self)
        if self.__command_targets != self.__load_targets:
            # In query dependents mode, we must use command targets to execute query
            self.__all_command_targets = self._expand_command_targets()
        console.info('loading done.')
        return self.__direct_targets, self.__all_command_targets  # For test

    def _expand_command_targets(self):
        """Expand command line targets to targets list"""
        all_targets = self.__build_targets
        all_command_targets = []
        for t in self.__command_targets:
            t_path, name = t.split(':')
            if name == '...':
                for tkey in all_targets:
                    if tkey[0].startswith(t_path):
                        all_command_targets.append(tkey)
            elif name == '*':
                for tkey in all_targets:
                    if tkey[0] == t_path:
                        all_command_targets.append(tkey)
            else:
                all_command_targets.append((t_path, name))
        return all_command_targets

    def analyze_targets(self):
        """Expand the targets. """
        console.info('analyzing dependency graph...')
        (self.__sorted_targets_keys,
         self.__depended_targets) = analyze_deps(self.__build_targets)
        self.__targets_expanded = True

        console.info('analyzing done.')
        return self.__build_targets  # For test

    def new_build_rules_generator(self):
        if config.get_item('global_config', 'native_builder') == 'ninja':
            return NinjaRulesGenerator('build.ninja', self.__blade_path, self)
        else:
            return SconsRulesGenerator('SConstruct', self.__blade_path, self)

    def generate_build_rules(self):
        """Generate the constructing rules. """
        console.info('generating build rules...')
        generator = self.new_build_rules_generator()
        rules = generator.generate_build_script()
        self.__all_rule_names = generator.get_all_rule_names()
        console.info('generating done.')
        return rules

    def generate(self):
        """Generate the build script. """
        if self.__command != 'query':
            self.generate_build_rules()

    def verify(self):
        """Verify specific targets after build is complete. """
        verify_history = self._load_verify_history()
        error = 0
        header_inclusion_dependencies = config.get_item('cc_config',
                                                        'header_inclusion_dependencies')
        header_inclusion_history = verify_history['header_inclusion_dependencies']
        for k in self.__sorted_targets_keys:
            target = self.__build_targets[k]
            if (header_inclusion_dependencies and
                    target.type == 'cc_library' and target.srcs):
                if not target.verify_header_inclusion_dependencies(header_inclusion_history):
                    error += 1
        self._dump_verify_history()
        return error == 0

    def run(self, target):
        """Run the target. """
        runner = BinaryRunner(self.__build_targets,
                              self.__options,
                              self.__target_database)
        return runner.run_target(target)

    def test(self):
        """Run tests. """
        skip_tests = []
        if self.__options.skip_tests:
            skip_tests = target.normalize(self.__options.skip_tests.split(','), self.__working_dir)
        test_runner = TestRunner(self.__build_targets,
                                 self.__options,
                                 self.__target_database,
                                 self.__direct_targets,
                                 skip_tests)
        return test_runner.run()

    def query(self):
        """Query the targets. """
        output_file_name = self.__options.output_file
        if output_file_name:
            output_file_name = os.path.join(self.__working_dir, output_file_name)
            output_file = open(output_file_name, 'w')
            console.info('query result will be written to file "%s"' % self.__options.output_file)
        else:
            output_file = sys.stdout
            console.info('query result:')

        output_format = self.__options.output_format
        if output_format == 'dot':
            self.query_dependency_dot(output_file)
        elif output_format == 'tree':
            self.query_dependency_tree(output_file)
        else:
            self.query_dependency_plain(output_file)
        if output_file_name:
            output_file.close()
        return 0

    def query_dependency_plain(self, output_file):
        result_map = self.query_helper()
        if self.__options.deps:
            for key in result_map:
                print(file=output_file)
                deps = result_map[key][0]
                print('//%s:%s depends on the following targets:' % (key[0], key[1]),
                      file=output_file)
                for d in deps:
                    print('%s:%s' % (d[0], d[1]), file=output_file)
        if self.__options.dependents:
            for key in result_map:
                print(file=output_file)
                depended_by = result_map[key][1]
                print('//%s:%s is depended by the following targets:' % (key[0], key[1]),
                      file=output_file)
                for d in depended_by:
                    print('%s:%s' % (d[0], d[1]), file=output_file)

    def print_dot_node(self, output_file, node):
        print('"%s:%s" [label = "%s:%s"]' % (node[0], node[1], node[0], node[1]), file=output_file)

    def print_dot_deps(self, output_file, node, target_set):
        targets = self.__build_targets
        deps = targets[node].deps
        for i in deps:
            if not i in target_set:
                continue
            print('"%s:%s" -> "%s:%s"' % (node[0], node[1], i[0], i[1]), file=output_file)

    def __print_dot_graph(self, result_map, name, print_mode, output_file):
        # print_mode = 0: deps, 1: dependents
        targets = result_map.keys()
        nodes = set(targets)
        for key in targets:
            nodes |= set(result_map[key][print_mode])
        print('digraph %s {' % name, file=output_file)
        for i in nodes:
            self.print_dot_node(output_file, i)
        for i in nodes:
            self.print_dot_deps(output_file, i, nodes)
        print('}', file=output_file)
        pass

    def query_dependency_dot(self, output_file):
        result_map = self.query_helper()
        if self.__options.deps:
            self.__print_dot_graph(result_map, 'deps', 0, output_file)
        if self.__options.dependents:
            self.__print_dot_graph(result_map, 'dependents', 1, output_file)

    def query_helper(self):
        """Query the targets helper method. """
        all_targets = self.__build_targets
        query_list = self.__all_command_targets

        result_map = {}
        for key in query_list:
            deps = all_targets[key].expanded_deps
            # depended_by = [k for k in all_targets if key in all_targets[k].expanded_deps]
            depended_by = self.__depended_targets[key]
            result_map[key] = (sorted(deps), sorted(depended_by))
        return result_map

    def query_dependency_tree(self, output_file):
        """Query the dependency tree of the specified targets. """
        if self.__options.dependents:
            console.error_exit('only query --deps can be output as tree format')
        print(file=output_file)
        for key in self.__all_command_targets:
            self._query_dependency_tree(key, 0, self.__build_targets, output_file)
            print(file=output_file)

    def _query_dependency_tree(self, key, level, build_targets, output_file):
        """Query the dependency tree of the specified target recursively. """
        path, name = key
        if level == 0:
            output = '%s:%s' % (path, name)
        elif level == 1:
            output = '%s %s:%s' % ('+-', path, name)
        else:
            output = '%s%s %s:%s' % ('|  ' * (level - 1), '+-', path, name)
        print(output, file=output_file)
        for dkey in build_targets[key].deps:
            self._query_dependency_tree(dkey, level + 1, build_targets, output_file)

    def dump_targets(self, output_file_name):
        result = []
        with open(output_file_name, 'w') as f:
            for target_key in self.__all_command_targets:
                target = self.__target_database[target_key]
                result.append(target.dump())
            json.dump(result, fp=f, indent=2)
            print(file=f)

    def get_build_time(self):
        return self.__build_time

    def get_build_path(self):
        """The current building path. """
        return self.__build_path

    def get_root_dir(self):
        """Return the blade root path. """
        return self.__root_dir

    def get_command(self):
        """Get the blade command. """
        return self.__command

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

    def get_depended_target_database(self):
        """Get depended target database that query dependent targets directly. """
        return self.__depended_targets

    def get_options(self):
        """Get the global command options. """
        return self.__options

    def is_expanded(self):
        """Whether the targets are expanded. """
        return self.__targets_expanded

    def register_target(self, target):
        """Register a target into blade target database.
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
        native_builder = config.get_item('global_config', 'native_builder')
        for k in self.__sorted_targets_keys:
            target = self.__build_targets[k]
            if not self._is_scons_object_type(target.type):
                continue
            blade_object = self.__target_database.get(k, None)
            if not blade_object:
                console.warning('not registered blade object, key %s' % str(k))
                continue
            if (skip_test and target.type.endswith('_test')
                    and k not in self.__direct_targets):
                continue
            if (skip_package and target.type == 'package'
                    and k not in self.__direct_targets):
                continue

            if native_builder == 'ninja':
                blade_object.ninja_rules()
            else:
                blade_object.scons_rules()
            rules = blade_object.get_rules()
            if rules:
                rules_buf.append('\n')
                rules_buf += rules
        return rules_buf

    def get_build_platform(self):
        """Return build platform instance. """
        return self.__build_platform

    def get_sources_keyword_list(self):
        """This keywords list is used to check the source files path.

        Ex, when users specifies warning=no, it could be used to check that
        the source files is under thirdparty or not. If not, it will warn
        users that this flag is used incorrectly.

        """
        keywords = ['thirdparty']
        return keywords

    def _load_verify_history(self):
        if os.path.exists(self._verify_history_path):
            with open(self._verify_history_path) as f:
                self._verify_history = json.load(f)
        return self._verify_history

    def _dump_verify_history(self):
        with open(self._verify_history_path, 'w') as f:
            json.dump(self._verify_history, f)

    def parallel_jobs_num(self):
        """Tune the jobs num. """
        # User has the highest priority
        user_jobs_num = self.__options.jobs
        if user_jobs_num > 0:
            return user_jobs_num

        # Calculate job numbers smartly
        distcc_enabled = config.get_item('distcc_config', 'enabled')
        if distcc_enabled and self.build_environment.distcc_env_prepared:
            # Distcc doesn't cost much local cpu, jobs can be quite large.
            distcc_num = len(self.build_environment.get_distcc_hosts_list())
            jobs_num = min(max(int(1.5 * distcc_num), 1), 20)
        else:
            cpu_core_num = cpu_count()
            # machines with cpu_core_num > 4 is usually shared by multiple users,
            # set an upper bound to avoid interfering other users
            jobs_num = min(2 * cpu_core_num, 8)
        console.info('tunes the parallel jobs number(-j N) to be %d' % jobs_num)
        return jobs_num

    def get_all_rule_names(self):
        return self.__all_rule_names


def initialize(
        command_targets,
        load_targets,
        blade_path,
        working_dir,
        build_path,
        blade_root_dir,
        blade_options,
        command):
    global instance
    instance = Blade(command_targets, load_targets,
                     blade_path, working_dir, build_path, blade_root_dir,
                     blade_options, command)
