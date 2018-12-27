# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Chong peng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the CmdOptions module which parses the users'
 input and provides hint for users.

"""


import os
import platform
import shlex
from argparse import ArgumentParser

import console
from blade_platform import BuildArchitecture
from blade_platform import BuildPlatform


class CmdArguments(object):
    """CmdArguments

    Parses user's input and provides hint.
    blade {command} [options] targets

    """
    def __init__(self):
        """Init the class. """
        self.options, others = self._cmd_parse()

        # If '--' in arguments, use all other arguments after it as run
        # arguments
        if '--' in others:
            pos = others.index('--')
            self.targets = others[:pos]
            self.options.args = others[pos + 1:]
        else:
            self.targets = others
            self.options.args = []

        for t in self.targets:
            if t.startswith('-'):
                console.error_exit('Unrecognized option %s, use blade [action] '
                                   '--help to get all the options' % t)

        command = self.options.command

        # Check the options with different sub command
        actions = {
                  'build': self._check_build_command,
                  'run':   self._check_run_command,
                  'test':  self._check_test_command,
                  'clean': self._check_clean_command,
                  'query': self._check_query_command
                  }
        actions[command]()

    def _check_run_targets(self):
        """check that run command should have only one target. """
        if not self.targets or ':' not in self.targets[0]:
            console.error_exit('Please specify a single target to run: '
                               'blade run //target_path:target_name (or '
                               'a_path:target_name)')
        if len(self.targets) > 1:
            console.warning('run command will only take one target to build and run')
        if self.options.runargs:
            console.warning('--runargs has been deprecated, please put all run'
                            ' arguments after a "--"')
            self.options.args = shlex.split(self.options.runargs) + self.options.args

    def _check_test_options(self):
        """check that test command options. """
        if self.options.testargs:
            console.warning('--testargs has been deprecated, please put all test'
                            ' arguments after a "--" ')
            self.options.args = shlex.split(self.options.testargs) + self.options.args

    def _check_plat_and_profile_options(self):
        """check platform and profile options. """
        compiler_arch = self._compiler_target_arch()
        arch = BuildArchitecture.get_canonical_architecture(compiler_arch)
        if arch is None:
            console.error_exit('Unknown architecture: %s' % compiler_arch)

        m = self.options.m
        if not m:
            self.options.arch = arch
            self.options.bits = BuildArchitecture.get_architecture_bits(arch)
            assert self.options.bits
        else:
            self.options.bits = m
            self.options.arch = BuildArchitecture.get_model_architecture(arch, m)
            if self.options.arch is None:
                console.error_exit('-m %s is not supported by the architecture %s'
                                   % (m, compiler_arch))

    def _check_clean_options(self):
        """check the clean options. """
        self._check_plat_and_profile_options()

    def _check_query_options(self):
        """check query action options. """
        if not self.options.deps and not self.options.depended:
            console.error_exit('please specify --deps, --depended or both to '
                               'query target')

    def _check_build_options(self):
        """check the building options. """
        self._check_plat_and_profile_options()

    def _check_build_command(self):
        """check build options. """
        self._check_build_options()

    def _check_run_command(self):
        """check run options and the run targets. """
        self._check_build_options()
        self._check_run_targets()

    def _check_test_command(self):
        """check test optios. """
        self._check_build_options()
        self._check_test_options()

    def _check_clean_command(self):
        """check clean options. """
        self._check_clean_options()

    def _check_query_command(self):
        """check query options. """
        self._check_plat_and_profile_options()
        self._check_query_options()

    def __add_plat_profile_arguments(self, parser):
        """Add plat and profile arguments. """
        parser.add_argument('-m',
                            dest='m',
                            choices=['32', '64'],
                            default='',
                            help=('Generate code for a 32-bit(-m32) or '
                                  '64-bit(-m64) environment, '
                                  'default is autodetect'))

        parser.add_argument('-p',
                            '--profile',
                            dest='profile',
                            choices=['debug', 'release'],
                            default='release',
                            help=('Build profile, default is release'))

        parser.add_argument('--no-debug-info',
                            dest='debug_info_level',
                            action='store_const',
                            const='no',
                            help=('Do not produce debugging information, this '
                                  'make less disk space cost but hard to debug, '
                                  'default is false'))

    def __add_generate_arguments(self, parser):
        """Add generate related arguments. """
        parser.add_argument(
            '--generate-dynamic', dest='generate_dynamic',
            action='store_true', default=False,
            help='Generate dynamic libraries')

        parser.add_argument(
            '--generate-package', dest='generate_package',
            action='store_true', default=False,
            help='Generate packages for package target')

        parser.add_argument(
            '--generate-java', dest='generate_java',
            action='store_true', default=False,
            help='Generate java files for proto_library, thrift_library and '
                 'swig_library')

        parser.add_argument(
            '--generate-php', dest='generate_php',
            action='store_true', default=False,
            help='Generate php files for proto_library and swig_library')

        parser.add_argument(
            '--generate-python', dest='generate_python',
            action='store_true', default=False,
            help='Generate python files for proto_library and thrift_library')

        parser.add_argument(
            '--generate-go', dest='generate_go',
            action='store_true', default=False,
            help='Generate go files for proto_library')

    def __add_build_actions_arguments(self, parser):
        """Add build related action arguments. """
        parser.add_argument(
            '--native-builder', dest='native_builder',
            type=str, choices = ['scons', 'ninja'], default='',
            help='Specify the underly native builder')
        parser.add_argument(
            '--generate-scons-only', dest='stop_after',
            action='store_const', const='generate',
            help='Generate scons script for debug purpose. '
                 'DEPRECATED, use --stop_after=generate instead')

        """Add extra native builder options arguments. """
        parser.add_argument(
            '--native-builder-options', dest='native_builder_options', type=str,
            help='Specifies extra native builder options, for debug purpose')

        parser.add_argument(
            '-j', '--jobs', dest='jobs', type=int, default=0,
            help=('Specifies the number of jobs (commands) to run simultaneously'))

        parser.add_argument(
            '-k', '--keep-going', dest='keep_going',
            action='store_true', default=False,
            help='Continue as much as possible after an error')

        parser.add_argument(
            '--verbose', dest='verbose', action='store_true',
            default=False, help='Show all details')

        parser.add_argument(
            '--no-test', dest='no_test', action='store_true',
            default=False, help='Do not build the test targets')

        parser.add_argument(
            '-n', '--dry-run', dest='dry_run', action='store_true', default=False,
            help='Dry run (don\'t run commands but act like they succeeded)')

    def __add_cache_arguments(self, parser):
        """Add cache related arguments. """
        parser.add_argument(
            '--cache-dir', dest='cache_dir', type=str,
            help='Specifies location of shared cache directory')

        parser.add_argument(
            '--cache-size', dest='cache_size', type=str,
            help='Specifies cache size of shared cache directory in Gigabytes'
                 '"unlimited" for unlimited. ')

    def __add_coverage_arguments(self, parser):
        """Add coverage arguments. """
        parser.add_argument(
            '--gprof', dest='gprof',
            action='store_true', default=False,
            help='Add build options to support GNU gprof')

        parser.add_argument(
            '--gcov', dest='coverage',
            action='store_true', default=False,
            help='Add build options to support GNU gcov to do coverage test. '
                 'DEPRECATED, please use --coverage')

        parser.add_argument(
            '--coverage', dest='coverage',
            action='store_true', default=False,
            help='Add build options to support coverage test')

    def _add_query_arguments(self, parser):
        """Add query arguments for parser. """
        self.__add_plat_profile_arguments(parser)
        parser.add_argument(
            '--deps', dest='deps',
            action='store_true', default=False,
            help='Show all targets that depended by the target being queried')
        parser.add_argument(
            '--depended', dest='depended',
            action='store_true', default=False,
            help='Show all targets that depend on the target being queried')
        parser.add_argument(
            '--output-to-dot', dest='output_to_dot', type=str,
            help='The name of file to output query results as dot(graphviz) format')
        parser.add_argument(
            '--output-tree', dest='output_tree',
            action='store_true', default=False,
            help='Show the dependency tree of the specified target')

    def _add_clean_arguments(self, parser):
        """Add clean arguments for parser. """
        self.__add_plat_profile_arguments(parser)
        self.__add_build_actions_arguments(parser)
        self.__add_generate_arguments(parser)

    def _add_test_arguments(self, parser):
        """Add test command arguments. """
        parser.add_argument(
            '--testargs', dest='testargs', type=str,
            help='Command line arguments to be passed to tests')

        parser.add_argument(
            '--full-test', action='store_true',
            dest='fulltest', default=False,
            help='Enable full test, default is incremental test')

        parser.add_argument(
            '-t', '--test-jobs', dest='test_jobs', type=int, default=1,
            help=('Specifies the number of tests to run simultaneously'))

        parser.add_argument(
            '--show-details', action='store_true',
            dest='show_details', default=False,
            help='Shows the test result in detail and provides a file')

        parser.add_argument(
            '--no-build', action='store_true',
            dest='no_build', default=False,
            help='Run tests directly without build')

    def _add_run_arguments(self, parser):
        """Add run command arguments. """
        parser.add_argument(
            '--runargs', dest='runargs', type=str,
            help='Command line arguments to be passed to the single run target')

    def _add_build_arguments(self, *parsers):
        """Add building arguments for parsers. """
        for parser in parsers:
            self.__add_plat_profile_arguments(parser)
            self.__add_build_actions_arguments(parser)
            self.__add_cache_arguments(parser)
            self.__add_generate_arguments(parser)
            self.__add_coverage_arguments(parser)

    def _add_common_arguments(self, *parsers):
        for parser in parsers:
            parser.add_argument(
                '--profiling', dest='profiling', action='store_true',
                help='Blade performance profiling, for blade developing')
            parser.add_argument(
                '--stop-after', dest='stop_after', type=str,
                choices=['load', 'analyze', 'generate', 'build', 'all'], default='all',
                help='Stop after specified phase')
            parser.add_argument(
                '--color', dest='color', choices=['yes', 'no', 'auto'], default='auto',
                help='Output color mode selection')
            parser.add_argument(
                '--load-local-config', dest='load_local_config',
                default=True, action='store_true',
                help='Load BLADE_ROOT.local')
            parser.add_argument(
                '--no-load-local-config', dest='load_local_config',
                action='store_false',
                help='Do not load BLADE_ROOT.local')


    def _cmd_parse(self):
        """Add command options, add options whthin this method."""
        blade_cmd_help = 'blade <subcommand> [options...] [targets...]'
        arg_parser = ArgumentParser(prog='blade', description=blade_cmd_help)

        sub_parser = arg_parser.add_subparsers(
            dest='command',
            help='Available subcommands')

        build_parser = sub_parser.add_parser(
            'build',
            help='Build specified targets')

        run_parser = sub_parser.add_parser(
            'run',
            help='Build and runs a single target')

        test_parser = sub_parser.add_parser(
            'test',
            help='Build the specified targets and runs tests')

        clean_parser = sub_parser.add_parser(
            'clean',
            help='Remove all Blade-created output')

        query_parser = sub_parser.add_parser(
            'query',
            help='Execute a dependency graph query')

        self._add_common_arguments(build_parser, run_parser, test_parser, clean_parser, query_parser)
        self._add_build_arguments(build_parser, run_parser, test_parser)
        self._add_run_arguments(run_parser)
        self._add_test_arguments(test_parser)
        self._add_clean_arguments(clean_parser)
        self._add_query_arguments(query_parser)

        return arg_parser.parse_known_args()

    def _compiler_target_arch(self):
        """Compiler(gcc) target architecture. """
        arch = BuildPlatform._get_cc_target_arch()
        pos = arch.find('-')
        if pos == -1:
            console.error_exit('Unknown target architecture %s from gcc.'
                               % arch)
        return arch[:pos]

    def get_command(self):
        """Return blade command. """
        return self.options.command

    def get_options(self):
        """Returns the command options, which should be used by blade manager."""
        return self.options

    def get_targets(self):
        """Returns the targets from command line."""
        return self.targets
