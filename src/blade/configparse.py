"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   January 09, 2012

 This is the configuration parse module which parses
 the BLADE_ROOT as a configuration file.

"""
import os
import sys
import traceback
from blade_util import error_exit
from cc_targets import HEAP_CHECK_VALUES


# Global config object
blade_config = None


class BladeConfig(object):
    """BladeConfig. A configuration parser class. """
    def __init__(self, current_source_dir):
        self.current_source_dir = current_source_dir
        self.configs = {
            'cc_test_config' : {
                'dynamic_link' : False,
                'heap_check' : '',
                'gperftools_libs' : ['thirdparty/perftools:tcmalloc'],
                'gperftools_debug_libs' :
                ['thirdparty/perftools:tcmalloc_debug'],
                'gtest_libs' : ['thirdparty/gtest:gtest'],
                'gtest_main_libs' : ['thirdparty/gtest:gtest_main']
            },

            'distcc_config' : {
                'enabled' : False
            },

            'link_config' : {
                'link_on_tmp' : False,
                'enable_dccc' : False
            },

            'java_config' : {
                'source_version' : '',
                'target_version' : ''
            },

            'protoc_config' : {
                'protoc' : 'thirdparty/protobuf/bin/protoc',
                'protobuf_libs':
                ['thirdparty/protobuf:protobuf'],
                'protobuf_path' : 'thirdparty',
                'protobuf_include_path' :
                'thirdparty', # splitted by space,
                'protobuf_php_path' :
                'thirdparty/Protobuf-PHP/library',
                'protoc_php_plugin' :
                'thirdparty/Protobuf-PHP/protoc-gen-php.php',
            },

            'cc_config' : {
                'extra_incs' : 'thirdparty' # splitted by space
            }
        }

    def parse(self):
        """load the configuration file and parse. """
        try:
            blade_conf = os.path.join(os.path.dirname(sys.argv[0]), "blade.conf")
            if os.path.exists(blade_conf):
                execfile(blade_conf)
        except:
            error_exit("Parse error in config file blade.conf, exit...\n%s" %
                       traceback.format_exc())

        try:
            bladerc_file = os.path.expanduser("~/.bladerc")
            if os.path.exists(bladerc_file):
                execfile(bladerc_file)
        except:
            error_exit("Parse error in config file bladerc, exit...\n%s" %
                       traceback.format_exc())

        try:
            execfile(os.path.join(self.current_source_dir, 'BLADE_ROOT'))
        except:
            error_exit("Parse error in config file BLADE_ROOT, exit...\n%s" %
                       traceback.format_exc())

    def update_config(self, section_name, user_configs):
        """update helper. """
        configs = self.configs.get(section_name, {})
        if configs:
            configs.update(user_configs)

    def get_config(self, section_name):
        """get config section, returns default values if not set """
        return self.configs.get(section_name, {})

def cc_test_config(**kwargs):
    """cc_test_config section. """
    heap_check = kwargs.get('heap_check', '')
    if heap_check and heap_check not in HEAP_CHECK_VALUES:
        error_exit('cc_test_config: heap_check can only be in %s' %
                   HEAP_CHECK_VALUES)
    global blade_config
    blade_config.update_config('cc_test_config', kwargs)

def distcc_config(**kwargs):
    """distcc_config. """
    global blade_config
    blade_config.update_config('distcc_config', kwargs)

def link_config(**kwargs):
    """link_config. """
    global blade_config
    blade_config.update_config('link_config', kwargs)

def java_config(**kwargs):
    """java_config. """
    global blade_config
    blade_config.update_config('java_config', kwargs)

def proto_library_config(**kwargs):
    """protoc config. """
    global blade_config
    blade_config.update_config('protoc_config', kwargs)

def cc_config(**kwargs):
    """extra cc config, like extra cpp include path splited by space. """
    global blade_config
    blade_config.update_config('cc_config', kwargs)
