# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Huan Yu <huanyu@tencent.com>
#         Feng Chen <phongchen@tencent.com>
#         Yi Wang <yiwang@tencent.com>
#         Chong Peng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the scons rules genearator module which invokes all
 the builder objects or scons objects to generate scons rules.

"""


import os
import time

import configparse
import console

from blade_platform import CcFlagsManager


def _incs_list_to_string(incs):
    """ Convert incs list to string
    ['thirdparty', 'include'] -> -I thirdparty -I include
    """
    return ' '.join(['-I ' + path for path in incs])


def escape_c_string(s):
    all_chars = (chr(x) for x in range(256))
    trans_table = dict((c, c) for c in all_chars)
    trans_table.update({'"': r'\"'})
    return "".join(trans_table[c] for c in s)


class SconsFileHeaderGenerator(object):
    """SconsFileHeaderGenerator class"""
    def __init__(self, options, build_dir, gcc_version,
                 python_inc, cuda_inc, build_environment, svn_roots):
        """Init method. """
        self.rules_buf = []
        self.options = options
        self.build_dir = build_dir
        self.gcc_version = gcc_version
        self.python_inc = python_inc
        self.cuda_inc = cuda_inc
        self.build_environment = build_environment
        self.ccflags_manager = CcFlagsManager(options, build_dir, gcc_version)
        self.svn_roots = svn_roots

        self.blade_config = configparse.blade_config
        self.distcc_enabled = self.blade_config.get_config(
                              'distcc_config').get('enabled', False)
        self.dccc_enabled = self.blade_config.get_config(
                              'link_config').get('enable_dccc', False)

    def _add_rule(self, rule):
        """Append one rule to buffer. """
        self.rules_buf.append('%s\n' % rule)

    def _append_prefix_to_building_var(
                self,
                prefix='',
                building_var='',
                condition=False):
        """A helper method: append prefix to building var if condition is True."""
        if condition:
            return '%s %s' % (prefix, building_var)
        else:
            return building_var

    def generate_version_file(self):
        """Generate version information files. """
        blade_root_dir = self.build_environment.blade_root_dir
        self._add_rule(
                'version_obj = scons_helper.generate_version_file(top_env, '
                'blade_root_dir="%s", build_dir="%s", profile="%s", '
                'gcc_version="%s", svn_roots=%s)' % (
                    blade_root_dir, self.build_dir, self.options.profile,
                    self.gcc_version, sorted(self.svn_roots)))

    def generate_imports_functions(self, blade_path):
        """Generates imports and functions. """
        self._add_rule(
            r"""
import sys
sys.path.insert(0, '%s')
""" % blade_path)
        self._add_rule(
            r"""
import os
import subprocess
import glob

import blade_util
import build_environment
import console
import scons_helper

""")

        if getattr(self.options, 'verbose', False):
            self._add_rule('scons_helper.option_verbose = True')
            self._add_rule('console.set_verbose(True)')

        self._add_rule((
                """if not os.path.exists('%s'):
    os.mkdir('%s')""") % (self.build_dir, self.build_dir))
        self._add_rule('console.set_log_file("%s")' % os.path.join(
                self.build_dir, 'blade_scons.log'))

        # Add java_home/bin into PATH to make scons
        # construction variables of java work as expected
        # See http://scons.org/faq.html#SCons_Questions
        java_config = self.blade_config.get_config('java_config')
        java_home = java_config['java_home']
        if java_home:
            self._add_rule('blade_util.environ_add_path(os.environ, "PATH", '
                           'os.path.join("%s", "bin"))' % java_home)

    def generate_top_level_env(self):
        """generates top level environment. """
        self._add_rule('top_env = scons_helper.make_top_env("%s")' % self.build_dir)

    def generate_compliation_verbose(self):
        """Generates color and verbose message. """
        self._add_rule('scons_helper.setup_compliation_verbose(top_env, color_enabled=%s, verbose=%s)' %
                (console.color_enabled, getattr(self.options, 'verbose', False)))

    def _generate_fast_link_builders(self):
        """Generates fast link builders if it is specified in blade bash. """
        link_config = self.blade_config.get_config('link_config')
        enable_dccc = link_config['enable_dccc']
        if link_config['link_on_tmp']:
            if (not enable_dccc) or (
                    enable_dccc and not self.build_environment.dccc_env_prepared):
                self._add_rule('scons_helper.setup_fast_link_builders(top_env)')

    def _generate_proto_builders(self):
        self._add_rule('time_value = Value("%s")' % time.asctime())
        proto_config = self.blade_config.get_config('proto_library_config')
        protoc_bin = proto_config['protoc']
        protoc_java_bin = protoc_bin
        if proto_config['protoc_java']:
            protoc_java_bin = proto_config['protoc_java']
        protobuf_path = proto_config['protobuf_path']

        protobuf_incs_str = _incs_list_to_string(proto_config['protobuf_incs'])
        protobuf_php_path = proto_config['protobuf_php_path']
        protoc_php_plugin = proto_config['protoc_php_plugin']
        protoc_go_plugin = proto_config['protoc_go_plugin']
        self._add_rule('scons_helper.setup_proto_builders(top_env, "%s", protoc_bin="%s", '
                       'protoc_java_bin="%s", protobuf_path="%s", protobuf_incs_str="%s", '
                       'protobuf_php_path="%s", protoc_php_plugin="%s", '
                       'protoc_go_plugin="%s")' % (
            self.build_dir, protoc_bin, protoc_java_bin, protobuf_path, protobuf_incs_str,
            protobuf_php_path, protoc_php_plugin, protoc_go_plugin))

    def _generate_thrift_builders(self):
        # Generate thrift library builders.
        thrift_config = self.blade_config.get_config('thrift_config')
        thrift_incs_str = _incs_list_to_string(thrift_config['thrift_incs'])
        thrift_bin = thrift_config['thrift']
        if thrift_bin.startswith('//'):
            thrift_bin = thrift_bin.replace('//', self.build_dir + '/')
            thrift_bin = thrift_bin.replace(':', '/')
        self._add_rule(
            'scons_helper.setup_thrift_builders(top_env, build_dir="%s", thrift_bin="%s", thrift_incs_str="%s")' % (
                    self.build_dir, thrift_bin, thrift_incs_str))

    def _generate_fbthrift_builders(self):
        fbthrift_config = self.blade_config.get_config('fbthrift_config')
        fbthrift1_bin = fbthrift_config['fbthrift1']
        fbthrift2_bin = fbthrift_config['fbthrift2']
        fbthrift_incs_str = _incs_list_to_string(fbthrift_config['fbthrift_incs'])
        self._add_rule('scons_helper.setup_fbthrift_builders(top_env, "%s", '
                'fbthrift1_bin="%s", fbthrift2_bin="%s", fbthrift_incs_str="%s")' % (
                    self.build_dir, fbthrift1_bin, fbthrift2_bin, fbthrift_incs_str))

    def _generate_cuda_builders(self):
        nvcc_str = os.environ.get('NVCC', 'nvcc')
        cuda_incs_str = ' '.join(['-I%s' % inc for inc in self.cuda_inc])
        self._add_rule('scons_helper.setup_cuda_builders(top_env, "%s", "%s")' % (
            nvcc_str, cuda_incs_str))

    def _generate_swig_builders(self):
        self._add_rule('scons_helper.setup_swig_builders(top_env, "%s")' % self.build_dir)

    def _generate_java_builders(self):
        config = self.blade_config.get_config('java_config')
        bin_config = self.blade_config.get_config('java_binary_config')
        self._add_rule('scons_helper.setup_java_builders(top_env, "%s", "%s")' % (
            config['java_home'], bin_config['one_jar_boot_jar']))

    def _generate_scala_builders(self):
        config = self.blade_config.get_config('scala_config')
        self._add_rule('scons_helper.setup_scala_builders(top_env, "%s")' % config['scala_home'])

    def _generate_go_builders(self):
        config = self.blade_config.get_config('go_config')
        self._add_rule('scons_helper.setup_go_builders(top_env, "%s", "%s")' %
                       (config['go'], config['go_home']))

    def _generate_other_builders(self):
        self._add_rule('scons_helper.setup_other_builders(top_env)')

    def generate_builders(self):
        """Generates common builders. """
        # Generates builders specified in blade bash at first
        self._generate_fast_link_builders()
        self._generate_proto_builders()
        self._generate_thrift_builders()
        self._generate_fbthrift_builders()
        self._generate_cuda_builders()
        self._generate_swig_builders()
        self._generate_java_builders()
        self._generate_scala_builders()
        self._generate_go_builders()
        self._generate_other_builders()

    def generate_compliation_flags(self):
        """Generates compliation flags. """
        toolchain_dir = os.environ.get('TOOLCHAIN_DIR', '')
        if toolchain_dir and not toolchain_dir.endswith('/'):
            toolchain_dir += '/'
        cpp = toolchain_dir + os.environ.get('CPP', 'cpp')
        cc = toolchain_dir + os.environ.get('CC', 'gcc')
        cxx = toolchain_dir + os.environ.get('CXX', 'g++')
        ld = toolchain_dir + os.environ.get('LD', 'g++')
        console.info('CPP=%s' % cpp)
        console.info('CC=%s' % cc)
        console.info('CXX=%s' % cxx)
        console.info('LD=%s' % ld)

        self.ccflags_manager.set_cc(cc)

        # To modify CC, CXX, LD according to the building environment and
        # project configuration
        build_with_distcc = (self.distcc_enabled and
                             self.build_environment.distcc_env_prepared)
        cc_str = self._append_prefix_to_building_var(
                         prefix='distcc',
                         building_var=cc,
                         condition=build_with_distcc)

        cxx_str = self._append_prefix_to_building_var(
                         prefix='distcc',
                         building_var=cxx,
                         condition=build_with_distcc)

        build_with_ccache = self.build_environment.ccache_installed
        cc_str = self._append_prefix_to_building_var(
                         prefix='ccache',
                         building_var=cc_str,
                         condition=build_with_ccache)

        cxx_str = self._append_prefix_to_building_var(
                         prefix='ccache',
                         building_var=cxx_str,
                         condition=build_with_ccache)

        build_with_dccc = (self.dccc_enabled and
                           self.build_environment.dccc_env_prepared)
        ld_str = self._append_prefix_to_building_var(
                        prefix='dccc',
                        building_var=ld,
                        condition=build_with_dccc)

        cc_config = self.blade_config.get_config('cc_config')
        cc_env_str = ('CC="%s", CXX="%s", SECURECXX="%s %s"' % (
                      cc_str, cxx_str, cc_config['securecc'], cxx))
        ld_env_str = 'LINK="%s"' % ld_str

        extra_incs = cc_config['extra_incs']
        extra_incs_str = ', '.join(['"%s"' % inc for inc in extra_incs])
        if not extra_incs_str:
            extra_incs_str = '""'

        (cppflags_except_warning, linkflags) = self.ccflags_manager.get_flags_except_warning()
        linkflags += cc_config['linkflags']

        self._add_rule('top_env.Replace(%s, '
                       'CPPPATH=[%s, "%s", "%s"], '
                       'CPPFLAGS=%s, CFLAGS=%s, CXXFLAGS=%s, '
                       '%s, LINKFLAGS=%s)' %
                       (cc_env_str,
                        extra_incs_str, self.build_dir, self.python_inc,
                        cc_config['cppflags'] + cppflags_except_warning,
                        cc_config['cflags'],
                        cc_config['cxxflags'],
                        ld_env_str, linkflags))

        cc_library_config = self.blade_config.get_config('cc_library_config')
        # By default blade use 'ar rcs' and skip ranlib
        # to generate index for static library
        arflags = cc_library_config['arflags']
        if arflags:
            self._add_rule('top_env.Replace(ARFLAGS="%s")' % ''.join(arflags))
        else:
            self._add_rule('top_env.Replace(ARFLAGS="rcs")')
        ranlibflags = cc_library_config['ranlibflags']
        if ranlibflags:
            self._add_rule('top_env.Replace(RANLIBFLAGS="%s")' % ''.join(ranlibflags))
        else:
            self._add_rule('top_env.Replace(RANLIBCOM="", RANLIBCOMSTR="")')

        # The default ASPPFLAGS of scons is same as ASFLAGS,
        # this is incorrect for gcc/gas
        options = self.options
        self._add_rule('top_env.Replace(ASFLAGS=["-g", "--%s"])' % options.m)
        self._add_rule('top_env.Replace(ASPPFLAGS="-Wa,--%s")' % options.m)

        self._setup_cache()

        if build_with_distcc:
            self.build_environment.setup_distcc_env()

        for rule in self.build_environment.get_rules():
            self._add_rule(rule)

        self._setup_envs()

    def _setup_envs(self):
        env_with_error, env_no_warning = 'env_with_error', 'env_no_warning'
        for env in [env_with_error, env_no_warning]:
            self._add_rule('%s = top_env.Clone()' % env)

        warnings, cxx_warnings, c_warnings = self.ccflags_manager.get_warning_flags()
        self._add_rule('%s.Append(CPPFLAGS=%s, CFLAGS=%s, CXXFLAGS=%s)' % (
                       env_with_error, warnings, c_warnings, cxx_warnings))
        self._setup_env_java()

    def _setup_env_java(self):
        env_java = 'env_java'
        self._add_rule('%s = top_env.Clone()' % env_java)
        java_config = self.blade_config.get_config('java_config')
        version = java_config['version']
        source_version = java_config.get('source_version', version)
        target_version = java_config.get('target_version', version)
        # JAVAVERSION must be set because scons need it to deduce class names
        # from java source, and the default value '1.5' is too low.
        java_version = version or '1.6'
        self._add_rule('%s.Replace(JAVAVERSION="%s")' % (env_java, java_version))
        if source_version:
            self._add_rule('%s.Append(JAVACFLAGS="-source %s")' % (
                           env_java, source_version))
        if target_version:
            self._add_rule('%s.Append(JAVACFLAGS="-target %s")' % (
                           env_java, target_version))
        java_test_config = self.blade_config.get_config('java_test_config')
        jacoco_home = java_test_config['jacoco_home']
        if jacoco_home:
            jacoco_agent = os.path.join(jacoco_home, 'lib', 'jacocoagent.jar')
            self._add_rule('%s.Replace(JACOCOAGENT="%s")' % (env_java, jacoco_agent))

    def _setup_cache(self):
        self.build_environment.setup_build_cache(self.options)

    def generate(self, blade_path):
        """Generates all rules. """
        self.generate_imports_functions(blade_path)
        self.generate_top_level_env()
        self.generate_compliation_verbose()
        self.generate_builders()
        self.generate_compliation_flags()
        self.generate_version_file()
        return self.rules_buf


class SconsRulesGenerator(object):
    """The main class to generate scons rules and outputs rules to SConstruct. """
    def __init__(self, scons_path, blade_path, blade):
        """Init method. """
        self.scons_path = scons_path
        self.blade_path = blade_path
        self.blade = blade
        self.scons_platform = self.blade.get_scons_platform()

        build_dir = self.blade.get_build_path()
        options = self.blade.get_options()
        gcc_version = self.scons_platform.get_gcc_version()
        python_inc = self.scons_platform.get_python_include()
        cuda_inc = self.scons_platform.get_cuda_include()

        self.scons_file_header_generator = SconsFileHeaderGenerator(
                options,
                build_dir,
                gcc_version,
                python_inc,
                cuda_inc,
                self.blade.build_environment,
                self.blade.svn_root_dirs)
        try:
            os.remove('blade-bin')
        except os.error:
            pass
        os.symlink(os.path.abspath(build_dir), 'blade-bin')

    def generate_scons_script(self):
        """Generates SConstruct script. """
        rules_buf = self.scons_file_header_generator.generate(self.blade_path)
        rules_buf += self.blade.gen_targets_rules()

        # Write to SConstruct
        self.scons_file_fd = open(self.scons_path, 'w')
        self.scons_file_fd.writelines(rules_buf)
        self.scons_file_fd.close()
        return rules_buf
