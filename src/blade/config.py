# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   January 09, 2012


"""
 This is the configuration parse module which parses
 the BLADE_ROOT as a configuration file.

"""
import os
import sys

import console
import build_attributes
from blade_util import var_to_list
from cc_targets import HEAP_CHECK_VALUES
from proto_library_target import ProtocPlugin


_config_globals = {}


def config_rule(func):
    '''Decorator for functions accessible in config files'''
    _config_globals[func.__name__] = func
    return func


class BladeConfig(object):
    """BladeConfig. A configuration parser class. """
    def __init__(self):
        self.current_file_name = ''
        self.configs = {
            'global_config' : {
                'build_path_template': 'build${m}_${profile}',
                'duplicated_source_action': 'warning', # Can be 'warning', 'error', 'none'
                'test_timeout': None,
                'native_builder': 'scons',
                'debug_info_level': 'mid',
            },

            'cc_test_config': {
                'dynamic_link': False,
                'heap_check': '',
                'gperftools_libs': [],
                'gperftools_debug_libs': [],
                'gtest_libs': [],
                'gtest_main_libs': [],
                'pprof_path': '',
            },

            'cc_binary_config': {
                'extra_libs': [],
                'run_lib_paths' : [],
            },

            'distcc_config': {
                'enabled': False
            },

            'link_config': {
                'link_on_tmp': False,
                'enable_dccc': False
            },

            'java_config': {
                'version': '1.6',
                'source_version': '',
                'target_version': '',
                'maven': 'mvn',
                'maven_central': '',
                'warnings':['-Werror', '-Xlint:all'],
                'source_encoding': None,
                'java_home':'',
                'debug_info_levels': {
                    'no': ['-g:none'],
                    'low': ['-g:source'],
                    'mid': ['-g:source,lines'],
                    'high': ['-g'],
                },
            },

            'java_binary_config': {
                'one_jar_boot_jar' : '',
            },
            'java_test_config': {
                'junit_libs' : [],
                'jacoco_home' : '',
                'coverage_reporter' : '',
            },
            'scala_config': {
                'scala_home' : '',
                'target_platform' : '',
                'warnings' : '',
                'source_encoding' : None,
            },
            'scala_test_config': {
                'scalatest_libs' : '',
            },
            'go_config' : {
                'go' : '',
                'go_home' : '',  # GOPATH
            },
            'thrift_config': {
                'thrift': 'thrift',
                'thrift_libs': [],
                'thrift_incs': [],
            },

            'fbthrift_config': {
                'fbthrift1': 'thrift1',
                'fbthrift2': 'thrift2',
                'fbthrift_libs': [],
                'fbthrift_incs': [],
            },

            'proto_library_config': {
                'protoc': 'thirdparty/protobuf/bin/protoc',
                'protoc_java': '',
                'protobuf_libs': [],
                'protobuf_path': '',
                'protobuf_incs': [],
                'protobuf_java_incs': [],
                'protobuf_php_path': '',
                'protoc_php_plugin': '',
                'protobuf_java_libs' : [],
                'protoc_go_plugin': '',
                # All the generated go source files will be placed
                # into $GOPATH/src/protobuf_go_path
                'protobuf_go_path': '',
                'protoc_direct_dependencies': False,
                'protobuf_python_libs' : [],
            },

            'protoc_plugin_config' : {
            },

            'cc_config': {
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
                'securecc' : None,
                'debug_info_levels': {
                    'no': ['-g0'],
                    'low': ['-g1'],
                    'mid': ['-g'],
                    'high': ['-g3'],
                },
            },
            'cc_library_config': {
                'prebuilt_libpath_pattern' : 'lib${bits}_${profile}',
                'generate_dynamic' : None,
                # Options passed to ar/ranlib to control how
                # the archive is created, such as, let ar operate
                # in deterministic mode discarding timestamps
                'arflags': ['rcs'],
                'ranlibflags': [],
            }
        }

    _globals = None

    def try_parse_file(self, filename):
        """load the configuration file and parse. """
        if BladeConfig._globals is None:
            BladeConfig._globals = globals()
            BladeConfig._globals['build_target'] = build_attributes.attributes
        try:
            self.current_file_name = filename
            if os.path.exists(filename):
                execfile(filename, _config_globals, None)
        except SystemExit:
            console.error_exit('Parse error in config file %s, exit...' % filename)
        finally:
            self.current_file_name = ''

    def update_config(self, section_name, append, user_config):
        """update config section by name. """
        section = self.configs.get(section_name)
        if section:
            if append:
                self._append_config(section_name, section, append)
            self._replace_config(section_name, section, user_config)
        else:
            console.error('%s: %s: unknown config section name' % (
                          self.current_file_name, section_name))

    def _append_config(self, section_name, section, append):
        """Append config section items"""
        if not isinstance(append, dict):
            console.error('%s: %s: append must be a dict' %
                    (self.current_file_name, section_name))
        else:
            for k in append:
                if k in section:
                    if isinstance(section[k], list):
                        section[k] += var_to_list(append[k])
                    else:
                        console.warning('%s: %s: config item %s is not a list' %
                                (self.current_file_name, section_name, k))

                else:
                    console.warning('%s: %s: unknown config item name: %s' %
                            (self.current_file_name, section_name, k))

    def _replace_config(self, section_name, section, user_config):
        """Replace config section items"""
        unknown_keys = []
        for k in user_config:
            if k in section:
                if isinstance(section[k], list):
                    user_config[k] = var_to_list(user_config[k])
            else:
                console.warning('%s: %s: unknown config item name: %s' %
                        (self.current_file_name, section_name, k))
                unknown_keys.append(k)
        for k in unknown_keys:
            del user_config[k]
        section.update(user_config)

    def get_section(self, section_name):
        """get config section, returns default values if not set """
        return self.configs[section_name]


# Global config object
_blade_config = BladeConfig()


def load_files(blade_root_dir, load_local_config):
    _config_globals['build_target'] = build_attributes.attributes
    _blade_config.try_parse_file(os.path.join(os.path.dirname(sys.argv[0]), 'blade.conf'))
    _blade_config.try_parse_file(os.path.expanduser('~/.bladerc'))
    _blade_config.try_parse_file(os.path.join(blade_root_dir, 'BLADE_ROOT'))
    if load_local_config:
        _blade_config.try_parse_file(os.path.join(blade_root_dir, 'BLADE_ROOT.local'))


def get_section(section_name):
    return _blade_config.get_section(section_name)


def get_item(section_name, item_name):
    return _blade_config.get_section(section_name)[item_name]


def _check_kwarg_enum_value(kwargs, name, valid_values):
    value = kwargs.get(name)
    if value is not None and value not in valid_values:
        console.error_exit('%s: Invalid %s value %s, can only be in %s' % (
            _blade_config.current_file_name, name, value, valid_values))


@config_rule
def config_items(**kwargs):
    """Used in config functions for config file, to construct a appended
    items dict, and then make syntax more pretty
    """
    return kwargs


@config_rule
def cc_test_config(append=None, **kwargs):
    """cc_test_config section. """
    heap_check = kwargs.get('heap_check')
    if heap_check is not None and heap_check not in HEAP_CHECK_VALUES:
        console.error_exit('cc_test_config: heap_check can only be in %s' %
                HEAP_CHECK_VALUES)
    _blade_config.update_config('cc_test_config', append, kwargs)


@config_rule
def cc_binary_config(append=None, **kwargs):
    """cc_binary_config section. """
    _blade_config.update_config('cc_binary_config', append, kwargs)


@config_rule
def cc_library_config(append=None, **kwargs):
    """cc_library_config section. """
    _blade_config.update_config('cc_library_config', append, kwargs)


__DUPLICATED_SOURCE_ACTION_VALUES = set(['warning', 'error', 'none', None])


@config_rule
def global_config(append=None, **kwargs):
    """global_config section. """
    _check_kwarg_enum_value(kwargs, 'duplicated_source_action', __DUPLICATED_SOURCE_ACTION_VALUES)
    debug_info_levels = _blade_config.get_section('cc_config')['debug_info_levels'].keys()
    _check_kwarg_enum_value(kwargs, 'debug_info_level', debug_info_levels)
    _blade_config.update_config('global_config', append, kwargs)


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
        console.warning(('%s: proto_library_config: protobuf_include_path has '
                         'been renamed to protobuf_incs, and become a list') %
                         _blade_config.current_file_name)
        del kwargs['protobuf_include_path']
        if isinstance(path, basestring) and ' ' in path:
            kwargs['protobuf_incs'] = path.split()
        else:
            kwargs['protobuf_incs'] = [path]

    _blade_config.update_config('proto_library_config', append, kwargs)


@config_rule
def protoc_plugin(**kwargs):
    """protoc_plugin. """
    if 'name' not in kwargs:
        console.error_exit("Missing 'name' in protoc_plugin parameters: %s" % kwargs)
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


@config_rule
def cc_config(append=None, **kwargs):
    """extra cc config, like extra cpp include path splited by space. """
    if 'extra_incs' in kwargs:
        extra_incs = kwargs['extra_incs']
        if isinstance(extra_incs, basestring) and ' ' in extra_incs:
            console.warning('%s: cc_config: extra_incs has been changed to list' %
                    _blade_config.current_file_name)
            kwargs['extra_incs'] = extra_incs.split()
    _blade_config.update_config('cc_config', append, kwargs)
