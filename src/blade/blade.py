"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the blade module which mainly holds the global database and
 do the coordination work between classes.

"""


import multiprocessing
import os
import configparse
from blade_util import error_exit
from blade_util import info
from blade_util import relative_path
from blade_util import warning
from dependency_analyzer import DependenciesAnalyzer
from load_build_files import load_targets
from blade_platform import CcFlagsManager
from blade_platform import SconsPlatform
from build_environment import BuildEnvironment
from rules_generator import SconsRulesGenerator
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
                 current_source_path,
                 blade_options,
                 **kwargs):
        """init method.

        Mainly to hold the global data.
        The directory which changes during the runtime of blade, and
        contains BUILD file under current focus.
        current_source_dir = "."

        Given some targets specified in the command line, Blade will load
        BUILD files containing these command line targets; global target
        functions, i.e., cc_libarary, cc_binary and etc, in these BUILD
        files will register targets into target_database, which then becomes
        the input to dependency analyzer and SCons rules generator.  It is
        notable that not all targets in target_database are dependencies of
        command line targets.
        target_database = {}

        related targets after loading the build files and exec BUILD files
        as python script
        related_targets = {}

        The map used by build rules to ensure that a source file occurres in
        exactly one rule/target(only library target).
        target_srcs_map = {}

        The scons cache manager class string, which should be output to
        scons script if ccache is not installed
        scache_manager_class_str = ''

        The targets keys list after sorting by topological sorting method.
        sorted_targets_keys = []

        Inidcating that whether the deps list is expanded by expander or not
        False - not expanded
        True - expanded
        target_deps_expanded

        All targets after expanding their dependency
        all_targets = {}

        The scons target objects registered into blade manager
        scons_targets_map = {}

        The vars which are depended by python binary
        {key : 'python_files'}
        self.python_binary_dep_source_cmd = {}

        The files which are depended by python binary
        {key : 'python_files'}
        python_binary_dep_source_map = {}

        The files which are depended by java jar file
        {key : 'java_files'}
        java_jar_dep_source_map = {}

        The files which should be packed into java jar
        {key : 'packing_files'}
        java_jar_files_packing_map = {}

        The jar files map
        {key : 'jar_files_generated'}
        java_jars_map = {}

        The java compiling classpath parameter map
        java_classpath_map = {}
        {key : 'target_path'}

        The java_jar dep var map, which should be added to dependency chain
        java_jar_dep_vars = {}

        The cc objects pool, a map to hold all the objects name.
        cc_objects_pool = {}

        The gen rule files map, which is used to generate the explict dependency
        relationtion ship between gen_rule target and other targets
        gen_rule_files_map = {}

        The direct targets that are used for analyzing
        direct_targets = []

        All command targets, make sure that all targets specified with ...
        are all in the list now
        all_command_targets = []

        The class to get platform info
        SconsPlatform

        The class to manage the cc flags
        CcFlagsManager

        The sources files that are needed to perform explict dependency
        sources_explict_dependency_map = {}

        The prebuilt cc_library file map which is needed to establish
        symbolic links while testing
        prebuilt_cc_library_file_map = {}

        """
        self.command_targets = command_targets
        self.direct_targets = []
        self.all_command_targets = []
        self.blade_path = blade_path
        self.working_dir = working_dir
        self.build_path = build_path
        self.current_source_path = current_source_path
        self.target_database = {}
        self.related_targets = {}
        self.target_srcs_map = {}
        self.scache_manager_class_str = ''
        self.options = blade_options
        self.sorted_targets_keys = []
        self.target_deps_expanded = False
        self.all_targets_expanded = {}
        self.scons_targets_map = {}
        self.java_jar_dep_source_map = {}
        self.java_jar_files_packing_map = {}
        self.java_jars_map = {}
        self.java_classpath_map = {}
        self.java_jar_dep_vars = {}
        self.python_binary_dep_source_cmd = {}
        self.python_binary_dep_source_map = {}
        self.cc_objects_pool = {}

        self.deps_expander = None
        self.build_rules_generator = None

        self.gen_rule_files_map = {}

        self.scons_platform = SconsPlatform()
        self.ccflags_manager = CcFlagsManager(self.options)
        self.sources_explict_dependency_map = {}
        self.prebuilt_cc_library_file_map = {}

        self.distcc_enabled = configparse.blade_config.get_config(
                'distcc_config')['enabled']

        self.build_environment = BuildEnvironment(self.current_source_path)

        self.svn_root_dirs = []

        self.kwargs = kwargs

    def _get_normpath_target(self, command_target):
        """returns a tuple (path, name).

        path is a full path from BLADE_ROOT

        """
        target_path = relative_path(self.working_dir, self.current_source_path)
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
        info("loading BUILDs...")
        if self.kwargs.get('blade_command', '') == 'query':
            working_dir = self.current_source_path

            if '...' not in self.command_targets:
                new_target_list = []
                for target in self.command_targets:
                    new_target_list.append("%s:%s" %
                            self._get_normpath_target(target))
                self.command_targets = new_target_list
        else:
            working_dir = self.working_dir
        (self.direct_targets,
         self.all_command_targets) = load_targets(self.command_targets,
                                                  working_dir,
                                                  self.current_source_path,
                                                  self)
        info("loading done.")
        return self.direct_targets, self.all_command_targets

    def analyze_targets(self):
        """Expand the targets. """
        info("analyzing dependency graph...")
        self.deps_analyzer = DependenciesAnalyzer(self)
        self.deps_analyzer.analyze_deps()
        info("analyzing done.")
        return self.all_targets_expanded

    def generate_build_rules(self):
        """Generate the constructing rules. """
        info("generating build rules...")
        self.build_rules_generator = SconsRulesGenerator('SConstruct',
                                                         self.blade_path, self)
        rules_buf = self.build_rules_generator.generate_scons_script()
        info("generating done.")
        return rules_buf

    def generate(self):
        """Build the targets. """
        self.load_targets()
        self.analyze_targets()
        self.generate_build_rules()

    def run(self, target):
        """Run the target. """
        key = self._get_normpath_target(target)
        runner = TestRunner(self.all_targets_expanded, self.options)
        return runner.run_target(key)

    def test(self):
        """Run tests. """
        test_runner = TestRunner(self.all_targets_expanded,
                                 self.options,
                                 self.prebuilt_cc_library_file_map,
                                 self.target_database)
        return test_runner.run()

    def query(self, targets):
        """Query the targets. """
        print_deps = hasattr(self.options, 'deps') and (
                        self.options.deps)
        print_depended = hasattr(self.options, 'depended') and (
                        self.options.depended)
        result_map = self.query_helper(targets)
        for key in result_map.keys():
            if print_deps:
                print "\n"
                deps = result_map[key][0]
                info("//%s:%s depends on the following targets:" % (
                        key[0], key[1]))
                for d in deps:
                    print "%s:%s" % (d[0], d[1])
            if print_depended:
                print "\n"
                depended_by = result_map[key][1]
                info("//%s:%s is depeneded by the following targets:" % (
                        key[0], key[1]))
                depended_by.sort(key=lambda x:x, reverse=False)
                for d in depended_by:
                    print "%s:%s" % (d[0], d[1])
        return 0

    def query_helper(self, targets):
        """Query the targets helper method. """
        all_targets = self.all_targets_expanded
        query_list = []
        target_path = relative_path(self.working_dir, self.current_source_path)
        t_path = ''
        for t in targets:
            key = t.split(':')
            if target_path == '.':
                t_path = key[0]
            else:
                t_path = target_path + '/' + key[0]
            t_path = os.path.normpath(t_path)
            query_list.append((t_path, key[1]))
        result_map = {}
        for key in query_list:
            result_map[key] = ([], [])
            deps = all_targets.get(key, {}).get('deps', [])
            deps.sort(key=lambda x:x, reverse=False)
            depended_by = []
            for tkey in all_targets.keys():
                if key in all_targets[tkey]['deps']:
                    depended_by.append(tkey)
            depended_by.sort(key=lambda x:x, reverse=False)
            result_map[key] = (list(deps), list(depended_by))
        return result_map

    def get_blade_path(self):
        """Return the blade archive path. """
        return self.blade_path

    def get_build_path(self):
        """The current building path. """
        return self.build_path

    def set_current_source_path(self, current_source_path):
        """Set the current source path. """
        self.current_source_path = current_source_path

    def get_current_source_path(self):
        """Get the current source path. """
        return self.current_source_path

    def get_target_database(self):
        """Get the whole target database that haven't been expanded. """
        return self.target_database

    def set_related_targets(self, related_targets):
        """Set the related targets. """
        self.related_targets = dict(related_targets)

    def get_related_targets(self):
        """Get the related targets. """
        return self.related_targets

    def get_direct_targets(self):
        """Return the direct targets. """
        return self.direct_targets

    def get_all_command_targets(self):
        """Return all command targets. """
        return self.all_command_targets

    def set_sorted_targets_keys(self, sorted_keys_list):
        """Set the keys list from expaned targets. """
        self.sorted_targets_keys = list(sorted_keys_list)

    def get_sorted_targets_keys(self):
        """Get the keys list from expaned targets. """
        return self.sorted_targets_keys

    def set_all_targets_expanded(self, all_targets):
        """Set the targets that have been expanded by expander. """
        self.all_targets_expanded = dict(all_targets)
        self.target_deps_expanded = True

    def get_all_targets_expanded(self):
        """Get all the targets that expaned. """
        return self.all_targets_expanded

    def get_target_srcs_map(self):
        """Get the targets source files map.

        It is used in generating cc object rules.

        """
        return self.target_srcs_map

    def get_options(self):
        """Get the global command options. """
        return self.options

    def get_expanded(self):
        """Whether the targets are expanded. """
        return self.target_deps_expanded

    def register_scons_target(self, target_key, scons_target):
        """Register scons targets into the scons targets map.

        It is used to do quick looking.

        """
        # check that whether there is already a key in database
        if target_key in self.scons_targets_map.keys():
            error_exit("target name %s is duplicate in //%s/BUILD" % (
                       target_key[1], target_key[0]))
        self.scons_targets_map[target_key] = scons_target

    def get_scons_target(self, target_key):
        """Get scons target according to the key. """
        return self.scons_targets_map.get(target_key, None)

    def get_java_jar_dep_source_map(self):
        """The map mainly to hold the java files from swig or proto rules.

        These files maybe depended by java_jar target.

        """
        return self.java_jar_dep_source_map

    def get_java_jar_files_packing_map(self):
        """The map to hold the files that should be packed into java jar. """
        return  self.java_jar_files_packing_map

    def get_java_jars_map(self):
        """The map to hold the java jar files generated by blade. """
        return self.java_jars_map

    def get_java_classpath_map(self):
        """The classpath list which is needed by java compling. """
        return self.java_classpath_map

    def get_java_jar_dep_vars(self):
        """The vars map which is prerequiste of the java jar target. """
        return self.java_jar_dep_vars

    def get_cc_objects_pool(self):
        """The cc objects pool which is used when generating the cc object rules. """
        return self.cc_objects_pool

    def _is_scons_object_type(self, target_type):
        """The types that shouldn't be registered into blade manager.

        Sholdn't invoke scons_rule method when it is not a scons target which
        could not be registered into blade manager, like system library.

        1. system_library

        """
        if target_type == 'system_library':
            return False
        else:
            return True

    def get_targets_rules(self):
        """Get the build rules and return to the object who queries this. """
        rules_buf = []
        skip_test_targets = False
        if hasattr(self.options, 'no_test') and self.options.no_test:
            skip_test_targets = True
        for k in self.sorted_targets_keys:
            target = self.all_targets_expanded[k]
            if not self._is_scons_object_type(target['type']):
               continue
            scons_object = self.scons_targets_map.get(k, None)
            if not scons_object:
                warning('not registered scons object, key %s' % str(k))
                continue
            if skip_test_targets and (target['type'] == 'cc_test' or
                                      target['type'] == 'dynamic_cc_test'):
                continue
            scons_object.scons_rules()
            rules_buf += scons_object.get_rules()
        return rules_buf

    def set_gen_rule_files_map(self, files_map):
        """Set the gen_rule files map. """
        self.gen_rule_files_map = dict(files_map)

    def get_gen_rule_files_map(self):
        """Get the gen_rule files map. """
        return self.gen_rule_files_map

    def get_scons_platform(self):
        """Return handle of the platform class. """
        return self.scons_platform

    def get_ccflags_manager(self):
        """Return handle of the ccflags manager class. """
        return self.ccflags_manager

    def get_sources_keyword_list(self):
        """This keywords list is used to check the source files path.

        Ex, when users specifies warning=no, it could be used to check that
        the source files is under thirdparty or not. If not, it will warn
        users that this flag is used incorrectly.

        """
        keywords = ['thirdparty']
        return keywords

    def get_sources_explict_dependency_map(self):
        """Returns the handle of sources_explict_dependency_map. """
        return self.sources_explict_dependency_map

    def get_prebuilt_cc_library_file_map(self):
        """Returns the prebuilt_cc_library_file_map. """
        return self.prebuilt_cc_library_file_map

    def tune_parallel_jobs_num(self):
        """Tune the jobs num. """
        user_jobs_num = self.options.jobs
        jobs_num = 0
        cpu_core_num = multiprocessing.cpu_count()
        if self.distcc_enabled and self.build_environment.distcc_env_prepared:
            jobs_num = int(1.5*len(self.build_environment.get_distcc_hosts_list())) + 1
            if jobs_num > 20:
                jobs_num = 20
            if jobs_num and self.options.jobs != jobs_num:
                self.options.jobs = jobs_num
        elif self.options.jobs < 1:
            if cpu_core_num <= 4:
                self.options.jobs = 2*cpu_core_num
            else:
                self.options.jobs = cpu_core_num
                if self.options.jobs > 8:
                    self.options.jobs = 8
        if self.options.jobs != user_jobs_num:
            info("tunes the parallel jobs number(-j N) to be %d" % (
                         self.options.jobs))
        return self.options.jobs
