# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   January 09, 2012


"""
 This is the configuration parse module which parses
 the BLADE_ROOT as a configuration file.

"""

from __future__ import absolute_import
from __future__ import print_function

import os
import pprint
import re
import sys

from blade import blade_util
from blade import build_attributes
from blade import console
from blade.blade_util import var_to_list, iteritems, exec_file_content, source_location
from blade.constants import HEAP_CHECK_VALUES


_MAVEN_SNAPSHOT_UPDATE_POLICY_VALUES = ['always', 'daily', 'interval', 'never']

_config_globals = {}


def config_rule(func):
    """Decorator used to register functions accessible in the configuration file"""
    _config_globals[func.__name__] = func
    return func


class BladeConfig(object):
    """BladeConfig. A configuration parser class. """

    def __init__(self):
        self.current_file_name = ''  # For error reporting
        self.__md5 = blade_util.md5.md5()

        # Support generate comments when dump the config by the special '__doc__' convention.
        # __doc__ field is for section
        # __doc__ suffix of items are for items.
        self.configs = {
            'global_config': {
                '__doc__': 'Global Configuration',
                'build_path_template': 'build${bits}_${profile}',
                'duplicated_source_action': 'warning',
                'duplicated_source_action__doc__': "Can be 'warning', 'error', 'none'",
                'test_timeout': None,
                'test_timeout__doc__': 'In seconds',
                'test_related_envs__doc__':
                    'Environment variables which need to see whether changed before incremental '
                    'testing. regex is allowed',
                'test_related_envs': [],
                'backend_builder': 'ninja',
                'debug_info_level': 'mid',
                'build_jobs': 0,
                'build_jobs__doc__': 'The number of build jobs (commands) to run simultaneously',
                'test_jobs': 0,
                'test_jobs__doc__': 'The number of test jobs to run simultaneously',
                'run_unrepaired_tests': False,
                'run_unrepaired_tests__doc__':
                    'Whether run unrepaired(no changw after previous failure) tests during incremental test',
                'glob_error_severity': 'warning',
                'glob_error_severity__doc__': 'The severity of glob error, can be debug, info, warning, error',
            },

            'cc_config': {
                '__doc__': 'C/C++ Configuration',
                'extra_incs': [],
                'cppflags': [],
                'cflags': [],
                'cxxflags': [],
                'linkflags': [],
                'c_warnings': [],
                'cxx_warnings': [],
                'warnings': [],
                'cpplint': 'cpplint.py',
                'optimize': [],
                'benchmark_libs': [],
                'benchmark_main_libs': [],
                'securecc': None,
                'debug_info_levels': {
                    'no': ['-g0'],
                    'low': ['-g1'],
                    'mid': ['-g'],
                    'high': ['-g3'],
                },
                'hdr_dep_missing_severity': 'warning',
                'hdr_dep_missing_severity__doc__': 'The severity of the missing dependency on the '
                    'library to which the header file belongs, can be "info", "warning", "error"',
                'hdr_dep_missing_suppress': {},
                'hdr_dep_missing_suppress__doc__': 'header deps missing suppress control, see docs for details',
            },

            'cc_library_config': {
                '__doc__': 'C/C++ Library Configuration',
                'prebuilt_libpath_pattern': 'lib${bits}',
                'generate_dynamic': None,
                # Options passed to ar/ranlib to control how
                # the archive is created, such as, let ar operate
                # in deterministic mode discarding timestamps
                'arflags': ['rcs'],
                'ranlibflags': [],
                'hdrs_missing_severity': 'error',
                'hdrs_missing_suppress': set(),
            },

            'cc_binary_config': {
                '__doc__': 'C/C++ Executable Configuration',
                'extra_libs': [],
                'run_lib_paths': [],
            },

            'cc_test_config': {
                '__doc__': 'C/C++ Test Configuration',
                'dynamic_link': False,
                'heap_check': '',
                'gperftools_libs': [],
                'gperftools_debug_libs': [],
                'gtest_libs': [],
                'gtest_main_libs': [],
                'pprof_path': '',
            },

            'distcc_config': {
                'enabled': False
            },

            'link_config': {
                '__doc__': 'Linking Configuration',
                'link_on_tmp': False,
                'link_jobs': None,
            },

            'java_config': {
                '__doc__': 'Java Configuration',
                'version': '1.8',
                'source_version': '',
                'target_version': '',
                'maven': 'mvn',
                'maven_central': '',
                'maven_snapshot_update_policy': 'daily',
                'maven_snapshot_update_policy__doc__':
                    'Can be %s' % _MAVEN_SNAPSHOT_UPDATE_POLICY_VALUES,
                'maven_snapshot_update_interval': 0,
                'maven_snapshot_update_interval__doc__': 'When policy is interval, in minutes',
                'maven_download_concurrency': 0,
                'maven_download_concurrency__doc__':
                    'Number of processes to pre-download maven_jar, 0 to disable pre-downloading',
                'warnings': ['-Werror', '-Xlint:all'],
                'source_encoding': None,
                'java_home': '',
                'debug_info_levels': {
                    'no': ['-g:none'],
                    'low': ['-g:source'],
                    'mid': ['-g:source,lines'],
                    'high': ['-g'],
                },
            },

            'java_binary_config': {
                '__doc__': 'Java Executable Configuration',
                'one_jar_boot_jar': '',
            },

            'java_test_config': {
                '__doc__': 'Java Test Configuration',
                'junit_libs': [],
                'jacoco_home': '',
            },

            'scala_config': {
                '__doc__': 'Scala Configuration',
                'scala_home': '',
                'target_platform': '',
                'warnings': '',
                'source_encoding': None,
            },

            'scala_test_config': {
                '__doc__': 'Scala Test Configuration',
                'scalatest_libs': '',
            },

            'go_config': {
                '__doc__': 'Golang Configuration',
                'go': '',
                'go_home': os.path.expandvars('$HOME/go'),  # GOPATH
                # enable go module for explicit use
                'go_module_enabled': os.environ.get("GO111MODULE") == "on",
                # onetree repository go module doesn't work in repository root
                'go_module_relpath': os.environ.get("go_module_relpath"),
            },

            'proto_library_config': {
                '__doc__': 'Protobuf Configuration',
                'protoc': 'thirdparty/protobuf/bin/protoc',
                'protoc_java': '',
                'protobuf_libs': [],
                'protobuf_path': '',
                'protobuf_incs': [],
                'protobuf_java_incs': [],
                'protobuf_php_path': '',
                'protoc_php_plugin': '',
                'protobuf_java_libs': [],
                'protoc_go_plugin': '',
                'protoc_go_subplugins': [],
                # All the generated go source files will be placed
                # into $GOPATH/src/protobuf_go_path
                'protobuf_go_path': '',
                'protobuf_python_libs': [],
                'protoc_direct_dependencies': False,
                'well_known_protos': [],
            },

            'protoc_plugin_config': {
                '__doc__': 'Protobuf Plugin Configuration',
            },

            'thrift_config': {
                '__doc__': 'Thrift Configuration',
                'thrift': 'thrift',
                'thrift_libs': [],
                'thrift_incs': [],
                'thrift_gen_params': 'cpp:include_prefix,pure_enums'
            },

            'fbthrift_config': {
                '__doc__': 'Facebook Thrift Configuration',
                'fbthrift1': 'thrift1',
                'fbthrift2': 'thrift2',
                'fbthrift_libs': [],
                'fbthrift_incs': [],
            },
        }

    def info(self, msg):
        console.info('%s info: %s' % (source_location(self.current_file_name), msg), prefix=False)

    def warning(self, msg):
        console.warning('%s warning: %s' % (source_location(self.current_file_name), msg), prefix=False)

    def error(self, msg):
        console.error('%s error: %s' % (source_location(self.current_file_name), msg), prefix=False)

    def fatal(self, msg):
        # NOTE: VSCode's problem matcher doesn't recognize 'fatal', use 'error' instead
        console.fatal('%s error: %s' % (source_location(self.current_file_name), msg), prefix=False)

    def try_parse_file(self, filename):
        """load the configuration file and parse. """
        try:
            self.current_file_name = filename
            if os.path.exists(filename):
                console.info('Loading config file "%s"' % filename)
                with open(filename, 'rb') as f:
                    content = f.read()
                    self.__md5.update(content)
                    exec_file_content(filename, content, _config_globals, None)
        except SystemExit:
            console.error('Parse error in config file %s' % filename)
        finally:
            self.current_file_name = ''

    def digest(self):
        """Hex md5 degest of all loaded config files"""
        return self.__md5.hexdigest()

    def update_config(self, section_name, append, user_config):
        """update config section by name. """
        section = self.configs.get(section_name)
        if section:
            if append:
                self._append_config(section_name, section, append)
            self._replace_config(section_name, section, user_config)
        else:
            self.error('%s: Unknown config section name' % section_name)

    def _append_config(self, section_name, section, append):
        """Append config section items"""
        if not isinstance(append, dict):
            self.error('%s: Append must be a dict' % section_name)
        for k in append:
            if k in section:
                if isinstance(section[k], list):
                    section[k] += var_to_list(append[k])
                else:
                    self.warning('%s: Config item %s is not a list' %
                                    (section_name, k))

            else:
                self.warning('%s: Unknown config item name: %s' % (section_name, k))

    def _replace_config(self, section_name, section, user_config):
        """Replace config section items"""
        unknown_keys = []
        for k in user_config:
            if k in section:
                if isinstance(section[k], list):
                    user_config[k] = var_to_list(user_config[k])
                elif isinstance(section[k], set):  # Allow using `list` to config `set`
                    user_config[k] = set(user_config[k])
            else:
                self.warning('%s: Unknown config item name: %s' % (section_name, k))
                unknown_keys.append(k)
        for k in unknown_keys:
            del user_config[k]
        section.update(user_config)

    def get_section(self, section_name):
        """get config section, returns default values if not set """
        return self.configs[section_name]

    def dump(self, output_file_name):
        with open(output_file_name, 'w') as f:
            print('# This config file was generated by `blade dump --config --to-file=<FILENAME>`\n', file=f)
            for name, value in sorted(iteritems(self.configs)):
                self._dump_section(name, value, f)

    def _dump_section(self, name, values, f):
        doc = '__doc__'
        if doc in values:
            print('# %s' % values[doc], file=f)
        print('%s(' % name, file=f)
        for k, v in values.items():
            if k.endswith('__doc__'):
                continue
            doc = k + '__doc__'
            if doc in values:
                print('    # %s' % values[doc], file=f)
            print('    %s = %s,' % (k, pprint.pformat(v, indent=8)), file=f)
        print(')\n', file=f)


# Global config object
_blade_config = BladeConfig()


def load_files(blade_root_dir, load_local_config):
    _config_globals['build_target'] = build_attributes.attributes
    _blade_config.try_parse_file(os.path.join(os.path.dirname(sys.argv[0]), 'blade.conf'))
    _blade_config.try_parse_file(os.path.expanduser('~/.bladerc'))
    _blade_config.try_parse_file(os.path.join(blade_root_dir, 'BLADE_ROOT'))
    if load_local_config:
        _blade_config.try_parse_file(os.path.join(blade_root_dir, 'BLADE_ROOT.local'))


def digest():
    """Hex md5 digest of all loaded config files"""
    # Used in rule hash entropy
    return _blade_config.digest()


def dump(output_file_name):
    _blade_config.dump(output_file_name)


def get_section(section_name):
    return _blade_config.get_section(section_name)


def get_item(section_name, item_name):
    return _blade_config.get_section(section_name)[item_name]


def _check_kwarg_enum_value(kwargs, name, valid_values):
    value = kwargs.get(name)
    if value is not None and value not in valid_values:
        _blade_config.error('Invalid config item "%s" value "%s", can only be in %s' % (
            name, value, valid_values))


def _check_test_related_envs(kwargs):
    for name in kwargs.get('test_related_envs', []):
        try:
            re.compile(name)
        except re.error as e:
            _blade_config.error(
                '"global_config.test_related_envs": Invalid env name or regex "%s", %s' % (name, e))


_DUPLICATED_SOURCE_ACTION_VALUES = set(['warning', 'error', 'none', None])


@config_rule
def config_items(**kwargs):
    """Used in config functions for config file, to construct a appended
    items dict, and then make syntax more pretty
    """
    return kwargs


@config_rule
def global_config(append=None, **kwargs):
    """global_config section. """
    _check_kwarg_enum_value(kwargs, 'duplicated_source_action', _DUPLICATED_SOURCE_ACTION_VALUES)
    debug_info_levels = _blade_config.get_section('cc_config')['debug_info_levels'].keys()
    _check_kwarg_enum_value(kwargs, 'debug_info_level', debug_info_levels)
    _check_test_related_envs(kwargs)
    _blade_config.update_config('global_config', append, kwargs)


@config_rule
def cc_test_config(append=None, **kwargs):
    """cc_test_config section. """
    _check_kwarg_enum_value(kwargs, 'heap_check', HEAP_CHECK_VALUES)
    _blade_config.update_config('cc_test_config', append, kwargs)


@config_rule
def cc_binary_config(append=None, **kwargs):
    """cc_binary_config section. """
    _blade_config.update_config('cc_binary_config', append, kwargs)


@config_rule
def cc_library_config(append=None, **kwargs):
    """cc_library_config section. """
    _blade_config.update_config('cc_library_config', append, kwargs)


@config_rule
def cc_config(append=None, **kwargs):
    """extra cc config, like extra cpp include path splited by space. """
    _check_kwarg_enum_value(kwargs, 'hdr_dep_missing_severity', ['debug', 'info', 'warning', 'error'])
    if 'extra_incs' in kwargs:
        extra_incs = kwargs['extra_incs']
        if isinstance(extra_incs, str) and ' ' in extra_incs:
            _blade_config.warning('"cc_config.extra_incs" has been changed to list')
            kwargs['extra_incs'] = extra_incs.split()
    _blade_config.update_config('cc_config', append, kwargs)


@config_rule
def distcc_config(append=None, **kwargs):
    """distcc_config. """
    _blade_config.update_config('distcc_config', append, kwargs)


@config_rule
def link_config(append=None, **kwargs):
    """link_config. """
    _blade_config.update_config('link_config', append, kwargs)


@config_rule
def java_config(append=None, **kwargs):
    """java_config. """
    _check_kwarg_enum_value(kwargs, 'maven_snapshot_update_policy',
            _MAVEN_SNAPSHOT_UPDATE_POLICY_VALUES)
    _blade_config.update_config('java_config', append, kwargs)


@config_rule
def java_binary_config(append=None, **kwargs):
    """java_test_config. """
    _blade_config.update_config('java_binary_config', append, kwargs)


@config_rule
def java_test_config(append=None, **kwargs):
    """java_test_config. """
    _blade_config.update_config('java_test_config', append, kwargs)


@config_rule
def scala_config(append=None, **kwargs):
    """scala_config. """
    _blade_config.update_config('scala_config', append, kwargs)


@config_rule
def scala_test_config(append=None, **kwargs):
    """scala_test_config. """
    _blade_config.update_config('scala_test_config', append, kwargs)


@config_rule
def go_config(append=None, **kwargs):
    """go_config. """
    _blade_config.update_config('go_config', append, kwargs)


@config_rule
def proto_library_config(append=None, **kwargs):
    """protoc config. """
    path = kwargs.get('protobuf_include_path')
    if path:
        _blade_config.warning('proto_library_config: protobuf_include_path has '
                              'been renamed to protobuf_incs, and become a list')
        del kwargs['protobuf_include_path']
        if isinstance(path, str) and ' ' in path:
            kwargs['protobuf_incs'] = path.split()
        else:
            kwargs['protobuf_incs'] = [path]

    _blade_config.update_config('proto_library_config', append, kwargs)


@config_rule
def protoc_plugin(**kwargs):
    """protoc_plugin. """
    from blade.proto_library_target import ProtocPlugin  # pylint: disable=import-outside-toplevel
    if 'name' not in kwargs:
        _blade_config.error('Missing "name" in protoc_plugin parameters: %s' % kwargs)
        return
    section = _blade_config.get_section('protoc_plugin_config')
    section[kwargs['name']] = ProtocPlugin(**kwargs)


@config_rule
def thrift_library_config(append=None, **kwargs):
    """thrift config. """
    _blade_config.update_config('thrift_config', append, kwargs)


@config_rule
def fbthrift_library_config(append=None, **kwargs):
    """fbthrift config. """
    _blade_config.update_config('fbthrift_config', append, kwargs)
