"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Chong peng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the CmdOptions module which parses the users'
 input and provides hint for users.

"""


import os
import platform
import sys
import blade_util
from argparse import ArgumentParser
from blade_util import error_exit
from blade_util import warning


class CmdArguments(object):
    """CmdArguments

    Parses user's input and provides hint.
    blade {command} [options] targets

    """
    def __init__(self):
        """Init the class. """
        (self.options, self.targets) = self._cmd_parse()
        for t in self.targets:
            if t.startswith('-'):
                error_exit("unregconized option %s, use blade [action] "
                           "--help to get all the options" % t)

        command = self.options.command

        # Check the options with different sub command
        actions = {
                  'build' : self._build_action,
                  'run'   : self._run_action,
                  'test'  : self._test_action,
                  'clean' : self._clean_action,
                  'query' : self._query_action
                  }[command]()

    def _check_run_targets(self):
        """check that run command should have only one target. """
        err = False
        targets = []
        if len(self.targets) == 0:
            err = True
        elif self.targets[0].find(':') == -1:
            err = True
        if err:
            error_exit("Please specify a single target to run: "
                       "blade run //target_path:target_name (or a_path:target_name)")
        if self.options.command == 'run' and len(self.targets) > 1:
            warning("run command will only take one target to build and run")
        if self.targets[0].startswith("//"):
            targets.append(self.targets[0][2:])
        else:
            targets.append(self.targets[0])
        self.targets = targets

    def _check_query_targets(self):
        """check query targets, should have a leaset one target. """
        err = False
        targets = []
        if len(self.targets) == 0:
            err = True
        for target in self.targets:
            if target.find(':') == -1:
                err = True
                break
            if target.startswith("//"):
                targets.append(target[2:])
            else:
                targets.append(target)
        if err:
            error_exit("Please specify targets in this way: "
                       "blade query //target_path:target_name (or a_path:target_name)")
        self.targets = targets

    def _check_plat_and_profile_options(self):
        """check platform and profile options. """
        if (self.options.profile != 'debug' and
            self.options.profile != 'release'):
            error_exit("--profile must be 'debug' or 'release'.")

        if self.options.m is None:
            self.options.m = self._arch_bits()
        else:
            if not (self.options.m == "32" or self.options.m == "64"):
                error_exit("--m must be '32' or '64'")

            # TODO(phongchen): cross compile checking
            if self.options.m == "64" and platform.machine() != "x86_64":
                error_exit("Sorry, 64-bit environment is required for "
                            "building 64-bit targets.")

    def _check_color_options(self):
        """check color options. """
        if self.options.color == "yes":
            self.options.color = True;
        elif self.options.color == "no":
            self.options.color = False;
        elif self.options.color == "auto" or  self.options.color is None:
            self.options.color = (sys.stdout.isatty() and
                                  os.environ['TERM'] not in ('emacs', 'dumb'))
        else:
            error_exit("--color can only be yes, no or auto.")
        blade_util.color_enabled = self.options.color

    def _check_clean_options(self):
        """check the clean options. """
        self._check_plat_and_profile_options()
        self._check_color_options()

    def _check_query_options(self):
        """check query action options. """
        if not self.options.deps and not self.options.depended:
            error_exit("please specify --deps, --depended or both to query target")

    def _check_build_options(self):
        """check the building options. """
        self._check_plat_and_profile_options()
        self._check_color_options()

        if self.options.cache_dir is None:
            self.options.cache_dir = os.environ.get('BLADE_CACHE_DIR')
        if self.options.cache_dir:
            self.options.cache_dir = os.path.expanduser(self.options.cache_dir)

        if self.options.cache_size is None:
            self.options.cache_size = os.environ.get('BLADE_CACHE_SIZE')
        if self.options.cache_size == "unlimited":
            self.options.cache_size = -1
        if self.options.cache_size is None:
            self.options.cache_size = 2 * 1024 * 1024 * 1024
        else:
            self.options.cache_size = int(self.options.cache_size) * 1024 * 1024 * 1024

    def _build_action(self):
        """check build options. """
        self._check_build_options()
        return 0

    def _run_action(self):
        """check run options and the run targets. """
        self._check_build_options()
        self._check_run_targets()
        return 0

    def _test_action(self):
        """check test optios. """
        self._check_build_options()
        return 0

    def _clean_action(self):
        """check clean options. """
        self._check_clean_options()
        return 0

    def _query_action(self):
        """check query options. """
        self._check_plat_and_profile_options()
        self._check_color_options()
        self._check_query_options()
        self._check_query_targets()
        return 0

    def __add_plat_profile_arguments(self, parser):
        """Add plat and profile arguments. """
        parser.add_argument("-m",
                            dest = "m",
                            help = ("Generate code for a 32-bit(-m32) or "
                                    "64-bit(-m64) environment, "
                                    "default is autodetect."))

        parser.add_argument("-p",
                            "--profile",
                            dest = "profile",
                            default = "release",
                            help = ("Build profile: debug or release, "
                                    "default is release."))

    def __add_generate_arguments(self, parser):
        """Add generate related arguments. """
        parser.add_argument(
            "--generate-dynamic", dest = "generate_dynamic",
            action = "store_true", default = False,
            help = "Generate dynamic libraries.")

        parser.add_argument(
            "--generate-java", dest = "generate_java",
            action = "store_true", default = False,
            help = "Generate java files for proto_library and swig_library.")

        parser.add_argument(
            "--generate-php", dest = "generate_php",
            action = "store_true", default = False,
            help = "Generate php files for proto_library and swig_library.")

    def __add_build_actions_arguments(self, parser):
        """Add build related action arguments. """
        parser.add_argument(
            "--generate-scons-only", dest = "scons_only",
            action = "store_true", default = False,
            help = "Generate scons script for debug purpose.")

        parser.add_argument(
            "-j", "--jobs", dest = "jobs", type = int, default = 0,
            help = ("Specifies the number of jobs (commands) to "
                    "run simultaneously."))

        parser.add_argument(
            "-k", "--keep-going", dest = "keep_going",
            action = "store_true", default = False,
            help = "Continue as much as possible after an error.")

        parser.add_argument(
            "--verbose", dest = "verbose", action = "store_true",
            default = False, help = "Show all details.")

        parser.add_argument(
            "--no-test", dest = "no_test", action = "store_true",
            default = False, help = "Do not build the test targets.")

    def __add_color_arguments(self, parser):
        """Add color argument. """
        parser.add_argument(
            "--color", dest = "color",
            default = "auto",
            help = "Enable color: yes, no or auto, default is auto.")

    def __add_cache_arguments(self, parser):
        """Add cache related arguments. """
        parser.add_argument(
            "--cache-dir", dest = "cache_dir", type = str,
            help = "Specifies location of shared cache directory.")

        parser.add_argument(
            "--cache-size", dest = "cache_size", type = str,
            help = "Specifies cache size of shared cache directory in Gigabytes."
                   "'unlimited' for unlimited. ")

    def __add_coverage_arguments(self, parser):
        """Add coverage arguments. """
        parser.add_argument(
            "--gprof", dest = "gprof",
            action = "store_true", default = False,
            help = "Add build options to support GNU gprof.")

        parser.add_argument(
            "--gcov", dest = "gcov",
            action = "store_true", default = False,
            help = "Add build options to support GNU gcov to do coverage test.")

    def _add_query_arguments(self, parser):
        """Add query arguments for parser. """
        self.__add_plat_profile_arguments(parser)
        self.__add_color_arguments(parser)
        parser.add_argument(
            "--deps", dest = "deps",
            action = "store_true", default = False,
            help = "Show all targets that depended by the target being queried.")
        parser.add_argument(
            "--depended", dest = "depended",
            action = "store_true", default = False,
            help = "Show all targets that depened on the target being queried.")

    def _add_clean_arguments(self, parser):
        """Add clean arguments for parser. """
        self.__add_plat_profile_arguments(parser)
        self.__add_generate_arguments(parser)
        self.__add_color_arguments(parser)

    def _add_test_arguments(self, parser):
        """Add test command arguments. """
        parser.add_argument(
            "--testargs", dest = "testargs", type = str,
            help = "Command line arguments to be passed to tests.")

        parser.add_argument(
            "--full-test", action = 'store_true',
            dest = "fulltest", default = False,
            help = "Enable full test, default is incremental test.")

        parser.add_argument(
            "-t", "--test-jobs", dest = "test_jobs", type = int, default = 1,
            help = ("Specifies the number of tests to "
                    "run simultaneously."))

        parser.add_argument(
            "--show-details", action = 'store_true',
            dest = "show_details", default = False,
            help = "Shows the test result in detail and provides a file.")

    def _add_run_arguments(self, parser):
        """Add run command arguments. """
        parser.add_argument(
            "--runargs", dest = "runargs", type = str,
            help = "Command line arguments to be passed to the single run target.")

    def _add_build_arguments(self, parser):
        """Add building arguments for parser. """
        self.__add_plat_profile_arguments(parser)
        self.__add_build_actions_arguments(parser)
        self.__add_color_arguments(parser)
        self.__add_cache_arguments(parser)
        self.__add_generate_arguments(parser)
        self.__add_coverage_arguments(parser)

    def _cmd_parse(self):
        """Add command options, add options whthin this method."""
        blade_cmd_help = 'blade {command} [options] target1 [target2] ...'
        arg_parser = ArgumentParser(prog='blade', description=blade_cmd_help)

        sub_parser = arg_parser.add_subparsers(dest="command",
                        help="Available commands")

        build_parser = sub_parser.add_parser("build",
                        help="Builds specified targets")

        run_parser = sub_parser.add_parser("run",
                        help="Builds and runs a single target")

        test_parser = sub_parser.add_parser("test",
                        help="Builds the specified targets and runs tests")

        clean_parser = sub_parser.add_parser("clean",
                        help="Removs all Blade-created output")

        query_parser = sub_parser.add_parser("query",
                        help="Executes a dependency graph query")

        self._add_build_arguments(build_parser)
        self._add_build_arguments(run_parser)
        self._add_build_arguments(test_parser)

        self._add_run_arguments(run_parser)
        self._add_test_arguments(test_parser)
        self._add_clean_arguments(clean_parser)
        self._add_query_arguments(query_parser)

        return arg_parser.parse_known_args()

    def _arch_bits(self):
        """Platform arch."""
        if 'x86_64' == platform.machine():
            return '64'
        else:
            return '32'

    def get_command(self):
        """Return blade command. """
        return self.options.command

    def get_options(self):
        """Returns the command options, which should be used by blade manager."""
        return self.options

    def get_targets(self):
        """Returns the targets from command line."""
        return self.targets
