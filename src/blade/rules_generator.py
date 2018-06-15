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
import subprocess

import configparse
import console

from blade_platform import CcFlagsManager


def _incs_list_to_string(incs):
    """ Convert incs list to string
    ['thirdparty', 'include'] -> -I thirdparty -I include
    """
    return ' '.join(['-I ' + path for path in incs])


def protoc_import_path_option(incs):
    return ' '.join(['-I=%s' % inc for inc in incs])


class ScriptHeaderGenerator(object):
    """Generate global declarations and definitions for build script.

    Specifically it may consist of global functions and variables,
    environment setup, predefined rules and builders, utilities
    for the underlying build system.
    """
    def __init__(self, options, build_dir, gcc_version,
                 python_inc, cuda_inc, build_environment, svn_roots):
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


class SconsScriptHeaderGenerator(ScriptHeaderGenerator):
    def __init__(self, options, build_dir, gcc_version,
                 python_inc, cuda_inc, build_environment, svn_roots):
        ScriptHeaderGenerator.__init__(
                self, options, build_dir, gcc_version,
                python_inc, cuda_inc, build_environment, svn_roots)

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
        self._add_rule('scons_helper.set_blade_error_log("%s")' %
                       os.path.join(self.build_dir, 'blade_scons.log.error'))

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
        protobuf_incs_str = protoc_import_path_option(proto_config['protobuf_incs'])
        protobuf_java_incs = protobuf_incs_str
        if proto_config['protobuf_java_incs']:
            protobuf_java_incs = protoc_import_path_option(proto_config['protobuf_java_incs'])
        protobuf_php_path = proto_config['protobuf_php_path']
        protoc_php_plugin = proto_config['protoc_php_plugin']
        protoc_go_plugin = proto_config['protoc_go_plugin']
        self._add_rule('scons_helper.setup_proto_builders(top_env, "%s", protoc_bin="%s", '
                       'protoc_java_bin="%s", protobuf_path="%s", '
                       'protobuf_incs_str="%s", protobuf_java_incs="%s", '
                       'protobuf_php_path="%s", protoc_php_plugin="%s", '
                       'protoc_go_plugin="%s")' % (
            self.build_dir, protoc_bin,
            protoc_java_bin, protobuf_path,
            protobuf_incs_str, protobuf_java_incs,
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
        arflags = ''.join(cc_library_config['arflags'])
        self._add_rule('top_env.Replace(ARFLAGS="%s")' % arflags)
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
        self._setup_env_cc()
        self._setup_env_java()

    def _setup_env_cc(self):
        env_cc_warning, env_cc = 'env_cc_warning', 'env_cc'
        for env in [env_cc_warning, env_cc]:
            self._add_rule('%s = top_env.Clone()' % env)

        warnings, cxx_warnings, c_warnings = self.ccflags_manager.get_warning_flags()
        self._add_rule('%s.Append(CPPFLAGS=%s, CFLAGS=%s, CXXFLAGS=%s)' % (
                       env_cc_warning, warnings, c_warnings, cxx_warnings))

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


class NinjaScriptHeaderGenerator(ScriptHeaderGenerator):
    def __init__(self, options, build_dir, blade_path, gcc_version,
                 python_inc, cuda_inc, build_environment, svn_roots):
        ScriptHeaderGenerator.__init__(
                self, options, build_dir, gcc_version,
                python_inc, cuda_inc, build_environment, svn_roots)
        self.blade_path = blade_path

    def generate_rule(self, name, command, description=None,
                      depfile=None, generator=False, pool=None,
                      restat=False, rspfile=None,
                      rspfile_content=None, deps=None):
        self._add_rule('rule %s' % name)
        self._add_rule('  command = %s' % command)
        if description:
            self._add_rule('  description = %s%s%s' % (
                           console.colors('dimpurple'), description, console.colors('end')))
        if depfile:
            self._add_rule('  depfile = %s' % depfile)
        if generator:
            self._add_rule('  generator = 1')
        if pool:
            self._add_rule('  pool = %s' % pool)
        if restat:
            self._add_rule('  restat = 1')
        if rspfile:
            self._add_rule('  rspfile = %s' % rspfile)
        if rspfile_content:
            self._add_rule('  rspfile_content = %s' % rspfile_content)
        if deps:
            self._add_rule('  deps = %s' % deps)

    def generate_top_level_vars(self):
        self._add_rule('''# build.ninja generated by blade
ninja_required_version = 1.7
builddir = %s
''' % self.build_dir)

    def generate_common_rules(self):
        self.generate_rule(name='stamp',
                           command='touch ${out}',
                           description='STAMP ${out}')
        self.generate_rule(name='copy',
                           command='cp -f ${in} ${out}',
                           description='COPY ${in} ${out}')

    def generate_cc_warning_vars(self):
        warnings, cxx_warnings, cc_warnings = self.ccflags_manager.get_warning_flags()
        cc_warnings += warnings
        cxx_warnings += warnings
        self._add_rule('''
cc_warnings = %s
cxx_warnings = %s
''' % (' '.join(cc_warnings), ' '.join(cxx_warnings)))

    def generate_cc_rules(self):
        cc = os.environ.get('CC', 'gcc')
        cxx = os.environ.get('CXX', 'g++')
        ld = os.environ.get('LD', 'g++')
        self.ccflags_manager.set_cc(cc)
        cc_config = self.blade_config.get_config('cc_config')
        cc_library_config = self.blade_config.get_config('cc_library_config')
        cflags, cxxflags = cc_config['cflags'], cc_config['cxxflags']
        cppflags, ldflags = self.ccflags_manager.get_flags_except_warning()
        cppflags = cc_config['cppflags'] + cppflags
        arflags = ''.join(cc_library_config['arflags'])
        ldflags = cc_config['linkflags'] + ldflags
        includes = cc_config['extra_incs']
        includes = includes + ['.', self.build_dir]
        includes = ' '.join(['-I%s' % inc for inc in includes])

        self.generate_cc_warning_vars()
        self.generate_rule(name='cc',
                command='%s -o ${out} -MMD -MF ${out}.d '
                        '-c -fPIC %s %s ${cc_warnings} ${cppflags} '
                        '%s ${includes} ${in}' % (
                        cc, ' '.join(cflags), ' '.join(cppflags), includes),
                description='CC ${in}',
                depfile='${out}.d',
                deps='gcc')
        self.generate_rule(name='cxx',
                command='%s -o ${out} -MMD -MF ${out}.d '
                        '-c -fPIC %s %s ${cxx_warnings} ${cppflags} '
                        '%s ${includes} ${in}' % (
                        cxx, ' '.join(cxxflags), ' '.join(cppflags), includes),
                description='CXX ${in}',
                depfile='${out}.d',
                deps='gcc')
        securecc = '%s %s' % (cc_config['securecc'], cxx)
        self._add_rule('''
build __securecc_phony__ : phony
''')
        self.generate_rule(name='securecccompile',
                command='%s -o ${out} -c -fPIC '
                        '%s %s ${cxx_warnings} ${cppflags} %s ${includes} ${in}' % (
                        securecc, ' '.join(cxxflags), ' '.join(cppflags), includes),
                description='SECURECC ${in}')
        self.generate_rule(name='securecc',
                command=self.generate_toolchain_command('securecc_object'),
                description='SECURECC ${in}',
                restat=True)

        self.generate_rule(name='ar',
                           command='rm -f $out; ar %s $out $in' % arflags,
                           description='AR ${out}')
        self.generate_rule(name='link',
                           command='%s -o ${out} %s ${ldflags} ${in} ${extra_ldflags}' % (
                                   ld, ' '.join(ldflags)),
                           description='LINK ${out}')
        self.generate_rule(name='solink',
                           command='%s -o ${out} -shared %s ${ldflags} ${in} ${extra_ldflags}' % (
                                   ld, ' '.join(ldflags)),
                           description='SHAREDLINK ${out}')

    def generate_proto_rules(self):
        config = self.blade_config.get_config('proto_library_config')
        protoc = config['protoc']
        protoc_java = protoc
        if config['protoc_java']:
            protoc_java = config['protoc_java']
        protobuf_incs = protoc_import_path_option(config['protobuf_incs'])
        protobuf_java_incs = protobuf_incs
        if config['protobuf_java_incs']:
            protobuf_java_incs = protoc_import_path_option(config['protobuf_java_incs'])
        self._add_rule('''
protoccpppluginflags =
protocjavapluginflags =
protocpythonpluginflags =
''')
        self.generate_rule(name='proto',
                           command='%s --proto_path=. %s -I=`dirname ${in}` '
                                   '--cpp_out=%s ${protoccpppluginflags} ${in}' % (
                                   protoc, protobuf_incs, self.build_dir),
                           description='PROTOC ${in}')
        self.generate_rule(name='protojava',
                           command='%s --proto_path=. %s --java_out=%s/`dirname ${in}` '
                                   '${protocjavapluginflags} ${in}' % (
                                   protoc_java, protobuf_java_incs, self.build_dir),
                           description='PROTOCJAVA ${in}')
        self.generate_rule(name='protopython',
                           command='%s --proto_path=. %s -I=`dirname ${in}` '
                                   '--python_out=%s ${protocpythonpluginflags} ${in}' % (
                                   protoc, protobuf_incs, self.build_dir),
                           description='PROTOCPYTHON ${in}')
        self.generate_rule(name='protodescriptors',
                           command='%s --proto_path=. %s -I=`dirname ${first}` '
                                   '--descriptor_set_out=${out} --include_imports '
                                   '--include_source_info ${in}' % (
                                   protoc, protobuf_incs),
                           description='PROTODESCRIPTORS ${in}')

    def generate_resource_rules(self):
        args = '${name} ${path} ${out} ${in}'
        self.generate_rule(name='resource_index',
                           command=self.generate_toolchain_command('resource_index', suffix=args),
                           description='RESOURCE INDEX ${out}')
        self.generate_rule(name='resource',
                           command='xxd -i ${in} | '
                                   'sed -e "s/^unsigned char /const char RESOURCE_/g" '
                                   '-e "s/^unsigned int /const unsigned int RESOURCE_/g" > ${out}',
                           description='RESOURCE ${in}')

    def generate_javac_rules(self, java_config):
        java_home = java_config['java_home']
        javac = os.path.join(java_home, 'bin', 'javac')
        jar = os.path.join(java_home, 'bin', 'jar')
        cmd = [javac]
        version = java_config['version']
        source_version = java_config.get('source_version', version)
        target_version = java_config.get('target_version', version)
        if source_version:
            cmd.append('-source %s' % source_version)
        if target_version:
            cmd.append('-target %s' % target_version)
        cmd += [
            '-encoding ${source_encoding}',
            '-d ${classes_dir}',
            '-classpath ${classpath}',
            '${javacflags}',
            '${in}',
        ]
        self._add_rule('''
source_encoding = UTF-8
classpath = .
javacflags =
''')
        self.generate_rule(name='javac',
                           command='rm -fr ${classes_dir} && mkdir -p ${classes_dir} && '
                                   '%s && sleep 0.5 && '
                                   '%s cf ${out} -C ${classes_dir} .' % (
                                   ' '.join(cmd), jar),
                           description='JAVAC ${in}')

    def generate_java_resource_rules(self):
        self.generate_rule(name='javaresource',
                           command=self.generate_toolchain_command('java_resource'),
                           description='JAVA RESOURCE ${in}')

    def generate_java_test_rules(self):
        java_test_config = self.blade_config.get_config('java_test_config')
        jacoco_home = java_test_config['jacoco_home']
        if jacoco_home:
            jacoco_agent = os.path.join(jacoco_home, 'lib', 'jacocoagent.jar')
            prefix = 'JACOCOAGENT=%s' % jacoco_agent
        else:
            prefix = ''
        self._add_rule('javatargetundertestpkg = __targetundertestpkg__')
        args = '${mainclass} ${javatargetundertestpkg} ${out} ${in}'
        self.generate_rule(name='javatest',
                           command=self.generate_toolchain_command('java_test',
                                                                   prefix=prefix,
                                                                   suffix=args),
                           description='JAVA TEST ${out}')

    def generate_java_binary_rules(self):
        config = self.blade_config.get_config('java_binary_config')
        bootjar = config['one_jar_boot_jar']
        args = '%s ${mainclass} ${out} ${in}' % bootjar
        self.generate_rule(name='onejar',
                           command=self.generate_toolchain_command('java_onejar', suffix=args),
                           description='ONE JAR ${out}')
        self.generate_rule(name='javabinary',
                           command=self.generate_toolchain_command('java_binary'),
                           description='JAVA BIN ${out}')

    def generate_scala_rules(self, java_home):
        scala_config = self.blade_config.get_config('scala_config')
        scala_home = scala_config['scala_home']
        scala = os.path.join(scala_home, 'bin', 'scala')
        scalac = os.path.join(scala_home, 'bin', 'scalac')
        java = os.path.join(java_home, 'bin', 'java')
        self._add_rule('''
scalacflags = -nowarn
''')
        cmd = [
            'JAVACMD=%s' % java,
            scalac,
            '-encoding UTF8',
            '-d ${out}',
            '-classpath ${classpath}',
            '${scalacflags}',
            '${in}'
        ]
        self.generate_rule(name='scalac',
                           command=' '.join(cmd),
                           description='SCALAC ${out}')
        args = '%s %s ${out} ${in}' % (java, scala)
        self.generate_rule(name='scalatest',
                           command=self.generate_toolchain_command('scala_test', suffix=args),
                           description='SCALA TEST ${out}')

    def generate_java_scala_rules(self):
        java_config = self.blade_config.get_config('java_config')
        self.generate_javac_rules(java_config)
        self.generate_java_resource_rules()
        java_home = java_config['java_home']
        jar = os.path.join(java_home, 'bin', 'jar')
        args = '%s ${out} ${in}' % jar
        self.generate_rule(name='javajar',
                           command=self.generate_toolchain_command('java_jar', suffix=args),
                           description='JAVA JAR ${out}')
        self.generate_java_test_rules()
        self.generate_rule(name='fatjar',
                           command=self.generate_toolchain_command('java_fatjar'),
                           description='FAT JAR ${out}')
        self.generate_java_binary_rules()
        self.generate_scala_rules(java_home)

    def generate_thrift_rules(self):
        thrift_config = self.blade_config.get_config('thrift_config')
        incs = _incs_list_to_string(thrift_config['thrift_incs'])
        thrift = thrift_config['thrift']
        if thrift.startswith('//'):
            thrift = thrift.replace('//', self.build_dir + '/')
            thrift = thrift.replace(':', '/')
        self.generate_rule(name='thrift',
                           command='%s --gen cpp:include_prefix,pure_enums '
                                   '-I . %s -I `dirname ${in}` '
                                   '-out %s/`dirname ${in}` ${in}' % (
                                   thrift, incs, self.build_dir),
                           description='THRIFT ${in}')

    def generate_python_rules(self):
        self._add_rule('''
pythonbasedir = __pythonbasedir__
''')
        args = '${pythonbasedir} ${out} ${in}'
        self.generate_rule(name='pythonlibrary',
                           command=self.generate_toolchain_command('python_library', suffix=args),
                           description='PYTHON LIBRARY ${out}')
        args = '${pythonbasedir} ${mainentry} ${out} ${in}'
        self.generate_rule(name='pythonbinary',
                           command=self.generate_toolchain_command('python_binary', suffix=args),
                           description='PYTHON BINARY ${out}')

    def generate_shell_rules(self):
        self.generate_rule(name='shelltest',
                           command=self.generate_toolchain_command('shell_test'),
                           description='SHELL TEST ${out}')
        args = '${out} ${in} ${testdata}'
        self.generate_rule(name='shelltestdata',
                           command=self.generate_toolchain_command('shell_testdata', suffix=args),
                           description='SHELL TEST DATA ${out}')

    def generate_lex_yacc_rules(self):
        self.generate_rule(name='lex',
                           command='flex ${lexflags} -o ${out} ${in}',
                           description='LEX ${in}')
        self.generate_rule(name='yacc',
                           command='bison ${yaccflags} -o ${out} ${in}',
                           description='YACC ${in}')

    def generate_package_rules(self):
        args = '${out} ${in} ${entries}'
        self.generate_rule(name='package',
                           command=self.generate_toolchain_command('package', suffix=args),
                           description='PACKAGE ${out}')

    def generate_version_rules(self):
        p = subprocess.Popen('svn info', shell=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        revision = url = 'unknown'
        if p.returncode == 0:
            for line in stdout.splitlines():
                if line.startswith('URL: '):
                    url = line.strip().split()[-1]
                if line.startswith('Revision: '):
                    revision = line.strip().split()[-1]
                    break
        args = '${out} ${revision} ${url} ${profile} "${compiler}"'
        self.generate_rule(name='scm',
                           command=self.generate_toolchain_command('scm', suffix=args),
                           description='SCM ${out}')
        scm = os.path.join(self.build_dir, 'scm.cc')
        self._add_rule('''
build %s: scm
  revision = %s
  url = %s
  profile = %s
  compiler = %s
''' % (scm, revision, url, self.options.profile, 'GCC ' + self.gcc_version))
        self._add_rule('''
build %s: cxx %s
  cppflags = -w -O2
  cxx_warnings =
''' % (scm + '.o', scm))

    def generate_toolchain_command(self, builder, prefix='', suffix=''):
        cmd = ['PYTHONPATH=%s:$$PYTHONPATH' % self.blade_path]
        if prefix:
            cmd.append(prefix)
        cmd.append('python -m toolchain %s' % builder)
        if suffix:
            cmd.append(suffix)
        else:
            cmd.append('${out} ${in}')
        return ' '.join(cmd)

    def generate(self):
        """Generate ninja rules. """
        self.generate_top_level_vars()
        self.generate_common_rules()
        self.generate_cc_rules()
        self.generate_proto_rules()
        self.generate_resource_rules()
        self.generate_java_scala_rules()
        self.generate_thrift_rules()
        self.generate_python_rules()
        self.generate_shell_rules()
        self.generate_lex_yacc_rules()
        self.generate_package_rules()
        self.generate_version_rules()
        return self.rules_buf


class RulesGenerator(object):
    """
    Generate build rules according to underlying build system and blade options.
    This class should be inherited by particular build system generator.
    """
    def __init__(self, script_path, blade_path, blade):
        self.script_path = script_path
        self.blade_path = blade_path
        self.blade = blade
        self.scons_platform = self.blade.get_scons_platform()
        self.build_dir = self.blade.get_build_path()
        try:
            os.remove('blade-bin')
        except os.error:
            pass
        os.symlink(os.path.abspath(self.build_dir), 'blade-bin')

    def generate_build_rules(self):
        """Generate build rules for underlying build system. """
        raise NotImplementedError

    def generate_build_script(self):
        """Generate build script for underlying build system. """
        rules = self.generate_build_rules()
        script = open(self.script_path, 'w')
        script.writelines(rules)
        script.close()
        return rules


class SconsRulesGenerator(RulesGenerator):
    """The main class to generate scons rules and outputs rules to SConstruct. """
    def __init__(self, scons_path, blade_path, blade):
        RulesGenerator.__init__(self, scons_path, blade_path, blade)
        options = self.blade.get_options()
        gcc_version = self.scons_platform.get_gcc_version()
        python_inc = self.scons_platform.get_python_include()
        cuda_inc = self.scons_platform.get_cuda_include()
        self.scons_script_header_generator = SconsScriptHeaderGenerator(
                options,
                self.build_dir,
                gcc_version,
                python_inc,
                cuda_inc,
                self.blade.build_environment,
                self.blade.svn_root_dirs)

    def generate_build_rules(self):
        """Generates scons rules to SConstruct. """
        rules = self.scons_script_header_generator.generate(self.blade_path)
        rules += self.blade.gen_targets_rules()
        return rules


class NinjaRulesGenerator(RulesGenerator):
    """Generate ninja rules to build.ninja. """
    def __init__(self, ninja_path, blade_path, blade):
        RulesGenerator.__init__(self, ninja_path, blade_path, blade)

    def generate_build_rules(self):
        """Generate ninja rules to build.ninja. """
        options = self.blade.get_options()
        gcc_version = self.scons_platform.get_gcc_version()
        python_inc = self.scons_platform.get_python_include()
        cuda_inc = self.scons_platform.get_cuda_include()
        ninja_script_header_generator = NinjaScriptHeaderGenerator(
                options,
                self.build_dir,
                self.blade_path,
                gcc_version,
                python_inc,
                cuda_inc,
                self.blade.build_environment,
                self.blade.svn_root_dirs)
        rules = ninja_script_header_generator.generate()
        rules += self.blade.gen_targets_rules()
        return rules

