# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Huan Yu <huanyu@tencent.com>
#         Feng Chen <phongchen@tencent.com>
#         Yi Wang <yiwang@tencent.com>
#         Chong Peng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
This is the build rules genearator module which invokes all the builder
objects to generate build rules.
"""

from __future__ import absolute_import
from __future__ import print_function

import os
import subprocess
import sys
import textwrap

from blade import config
from blade import console
from blade import util


# To verify whether a header file is included without depends on the library it belongs to,
# we use the gcc's `-H` option to generate the inclusion stack information, see
# https://gcc.gnu.org/onlinedocs/gcc/Preprocessor-Options.html for details.
# But this information is output to stderr mixed with diagnostic messages.
# So we use this awk script to split them.
#
# The inclusion information is writes to stdout, other normal diagnostic message is write to stderr.
#
# NOTE the `$$` is required by ninja. and the `Multiple...` is the last and useless part of
# the messages.
_INCLUSION_STACK_SPLITTER = (r"awk '"
     r"""/Multiple include guards may be useful for:/ {stop=1} """  # Can't exit here otherwise SIGPIPE maybe occurs.
     r"""/^\.+ [^\/]/ && !stop { print $$0} """  # Non absolute path
     r"""!/^\./ && !/^\// && !/Multiple include guards may be useful for:/ {print $$0 > "/dev/stderr"}"""  # Maybe error messages
     r"'"
)

def _incs_list_to_string(incs):
    """Convert incs list to string.

    Example:
        ['thirdparty', 'include'] -> "-I thirdparty -I include"
    """
    return ' '.join(['-I ' + path for path in incs])


def protoc_import_path_option(incs):
    return ' '.join(['-I=%s' % inc for inc in incs])


def _shell_support_pipefail():
    """Whether current shell support the `pipefail` option."""
    return subprocess.call('set -o pipefail 2>/dev/null', shell=True) == 0


class _NinjaFileHeaderGenerator(object):
    """Generate global declarations and definitions for build script.

    Specifically it may consist of global functions and variables,
    environment setup, predefined rules and builders, utilities
    for the underlying build system.
    """
    # pylint: disable=too-many-public-methods
    def __init__(self, command, options, build_dir, blade_path, build_toolchain, blade):
        self.command = command
        self.options = options
        self.build_dir = build_dir
        self.blade_path = blade_path
        self.build_toolchain = build_toolchain
        self.build_accelerator = blade.build_accelerator
        self.blade = blade

        self.rules_buf = []
        self.__all_rule_names = set()

    def _add_line(self, rule):
        """Append one rule to buffer."""
        self.rules_buf.append('%s\n' % rule)

    def get_all_rule_names(self):
        return list(self.__all_rule_names)

    def generate_rule(self, name, command, description=None,
                      depfile=None, generator=False, pool=None,
                      restat=False, rspfile=None,
                      rspfile_content=None, deps=None):
        self.__all_rule_names.add(name)
        self._add_line('rule %s' % name)
        self._add_line('  command = %s' % command)
        if description:
            self._add_line('  description = %s' % console.colored(description, 'dimpurple'))
        if depfile:
            self._add_line('  depfile = %s' % depfile)
        if generator:
            self._add_line('  generator = 1')
        if pool:
            self._add_line('  pool = %s' % pool)
        if restat:
            self._add_line('  restat = 1')
        if rspfile:
            self._add_line('  rspfile = %s' % rspfile)
        if rspfile_content:
            self._add_line('  rspfile_content = %s' % rspfile_content)
        if deps:
            self._add_line('  deps = %s' % deps)
        self._add_line('')  # An empty line to improve readability

    def generate_file_header(self):
        self._add_line(textwrap.dedent('''\
                # build.ninja generated by blade
                ninja_required_version = 1.7
                builddir = %s
                ''') % self.build_dir)
        # No more than 1 heavy target at a time
        self._add_line(textwrap.dedent('''\
                pool heavy_pool
                  depth = 1
                '''))

    def generate_common_rules(self):
        self.generate_rule(name='copy',
                           command='cp -f ${in} ${out}',
                           description='COPY ${in} ${out}')

    def _get_intrinsic_cc_flags(self):
        """Get the common c/c++ flags."""
        global_config = config.get_section('global_config')
        cc_config = config.get_section('cc_config')

        cppflags = []
        linkflags = []
        if self.options.m:
            cppflags = ['-m%s' % self.options.m]
            linkflags = ['-m%s' % self.options.m]
        # Add -fno-omit-frame-pointer to optimize mode for easy debugging.
        cppflags += ['-pipe', '-fno-omit-frame-pointer']

        # Debugging information setting
        debug_info_level = global_config['debug_info_level']
        debug_info_options = cc_config['debug_info_levels'][debug_info_level]
        cppflags += debug_info_options

        # Option debugging flags
        if self.options.profile == 'debug':
            cppflags.append('-fstack-protector')
        elif self.options.profile == 'release':
            cppflags.append('-DNDEBUG')

        cppflags += [
            '-D_FILE_OFFSET_BITS=64',
            '-D__STDC_CONSTANT_MACROS',
            '-D__STDC_FORMAT_MACROS',
            '-D__STDC_LIMIT_MACROS',
        ]

        if getattr(self.options, 'gprof', False):
            cppflags.append('-pg')
            linkflags.append('-pg')

        if getattr(self.options, 'coverage', False):
            cppflags.append('--coverage')
            linkflags.append('--coverage')

        cppflags = self.build_toolchain.filter_cc_flags(cppflags)
        return cppflags, linkflags

    def _get_warning_flags(self):
        """Get the warning flags."""
        cc_config = config.get_section('cc_config')
        cuda_config = config.get_section('cuda_config')
        cppflags = cc_config['warnings']
        cxxflags = cc_config['cxx_warnings']
        cflags = cc_config['c_warnings']
        cuflags = cuda_config['cu_warnings']

        filtered_cppflags = self.build_toolchain.filter_cc_flags(cppflags)
        filtered_cxxflags = self.build_toolchain.filter_cc_flags(cxxflags, 'c++')
        filtered_cflags = self.build_toolchain.filter_cc_flags(cflags, 'c')

        return filtered_cppflags, filtered_cxxflags, filtered_cflags, cuflags

    def generate_cc_rules(self):
        cc, cxx, ld = self.build_accelerator.get_cc_commands()
        cppflags, linkflags = self._get_intrinsic_cc_flags()
        self._generate_cc_compile_rules(cc, cxx, cppflags)
        self._generate_cc_inclusion_check_rule()
        self._generate_cc_ar_rules()
        self._generate_cc_link_rules(ld, linkflags)
        self.generate_rule(name='strip',
                           command='strip --strip-unneeded -o ${out} ${in}',
                           description='STRIP ${out}')

    def _generate_cc_vars(self):
        warnings, cxx_warnings, c_warnings, cu_warnings = self._get_warning_flags()
        c_warnings += warnings
        cxx_warnings += warnings
        cu_warnings += ['-Xcompiler %s' % warning for warning in cxx_warnings]
        # optimize_flags is need for `always_optimize`
        optimize_flags = config.get_item('cc_config', 'optimize')
        optimize = '$optimize_flags' if self.options.profile == 'release' else ''
        self._add_line(textwrap.dedent('''\
                c_warnings = %s
                cxx_warnings = %s
                cu_warnings = %s
                optimize_flags = %s
                optimize = %s
                ''') % (' '.join(c_warnings), ' '.join(cxx_warnings),
                        ' '.join(cu_warnings),
                        ' '.join(optimize_flags), optimize))

    def _generate_cc_compile_rules(self, cc, cxx, cppflags):
        self._generate_cc_vars()

        cc_config = config.get_section('cc_config')
        cflags, cxxflags = cc_config['cflags'], cc_config['cxxflags']
        cppflags = cc_config['cppflags'] + cppflags
        includes = cc_config['extra_incs']
        includes = includes + ['.', self.build_dir]
        includes = ' '.join(['-I%s' % inc for inc in includes])

        template = self._cc_compile_command_wrapper_template('${out}.H')

        cc_command = ('%s -o ${out} -MMD -MF ${out}.d -c -fPIC %s %s ${optimize} '
                      '${c_warnings} ${cppflags} %s ${includes} ${in}') % (
                              cc, ' '.join(cflags), ' '.join(cppflags), includes)
        self.generate_rule(name='cc',
                           command=template % cc_command,
                           description='CC ${in}',
                           depfile='${out}.d',
                           deps='gcc')

        cxx_command = ('%s -o ${out} -MMD -MF ${out}.d -c -fPIC %s %s ${optimize} '
                       '${cxx_warnings} ${cppflags} %s ${includes} ${in}') % (
                               cxx, ' '.join(cxxflags), ' '.join(cppflags), includes)
        self.generate_rule(name='cxx',
                           command=template % cxx_command,
                           description='CXX ${in}',
                           depfile='${out}.d',
                           deps='gcc')

        self.generate_rule(name='secretcc',
                           command=template % (cc_config['secretcc'] + ' ' + cxx_command),
                           description='SECRET CC ${in}',
                           depfile='${out}.d')

        self._generate_cc_hdrs_rule(cc, cxx, cppflags, cflags, cxxflags, includes)

    def _generate_cc_hdrs_rule(self, cc, cxx, cppflags, cflags, cxxflags, includes):
        """
        Generate inclusion stack file for header file to check dependency missing.
        See the '-H' in https://gcc.gnu.org/onlinedocs/gcc/Preprocessor-Options.html for details.
        """
        self.generate_rule(name='cxxhdrs',
                           command=self._hdrs_command(cxx, cxxflags, cppflags, includes),
                           depfile='${out}.d', deps='gcc',
                           description='CXX HDRS ${in}')

    def _hdrs_command(self, cc, flags, cppflags, includes):
        """Command to generate cc inclusion information file"""
        args = (' -o /dev/null -E -MMD -MF ${out}.d %s %s -w ${cppflags} %s ${includes} ${in} '
                '2> ${out}.err' % (' '.join(flags), ' '.join(cppflags), includes))

        # The `-fdirectives-only` option can significantly increase the speed of preprocessing,
        # but errors may occur under certain boundary conditions (for example,
        # `#if __COUNTER__ == __COUNTER__ + 1`),
        # try the command again without it on error.
        cmd1 = cc + ' -fdirectives-only' + args
        cmd2 = cc + args

        # If the first cpp command fails, the second cpp command will be executed.
        # The error message of the first command should be completely ignored.
        return ('export LC_ALL=C; %s || %s; ec=$$?; %s ${out}.err > ${out}; '
                'rm -f ${out}.err; exit $$ec') % (cmd1, cmd2, _INCLUSION_STACK_SPLITTER)

    def _generate_cc_inclusion_check_rule(self):
        self.generate_rule(name='ccincchk',
                           command=self._builtin_command('cc_inclusion_check'),
                           description='CC INCLUSION CHECK ${in}')

    def _generate_cc_ar_rules(self):
        arflags = ''.join(config.get_item('cc_library_config', 'arflags'))
        self.generate_rule(name='ar',
                           command='rm -f $out; ar %s $out $in' % arflags,
                           description='AR ${out}')

    def _generate_cc_link_rules(self, ld, linkflags):
        self._add_line('linkflags = %s' % ' '.join(config.get_item('cc_config', 'linkflags')))
        self._add_line('intrinsic_linkflags = %s\n' % ' '.join(linkflags))

        link_jobs = config.get_item('link_config', 'link_jobs')
        if link_jobs:
            link_jobs = min(link_jobs, self.blade.build_jobs_num())
            console.info('Adjust parallel link jobs number to %s' % link_jobs)
            pool = 'link_pool'
            self._add_line(textwrap.dedent('''\
                    pool %s
                      depth = %s''') % (pool, link_jobs))
        else:
            pool = None

        # Linking might have a lot of object files exceeding maximal length of a bash command line.
        # Using response file can resolve this problem.
        # Refer to: https://ninja-build.org/manual.html
        link_args = '-o ${out} ${intrinsic_linkflags} ${linkflags} ${target_linkflags} @${out}.rsp ${extra_linkflags}'
        self.generate_rule(name='link',
                           command=ld + ' ' + link_args,
                           rspfile='${out}.rsp',
                           rspfile_content='${in}',
                           description='LINK BINARY ${out}',
                           pool=pool)
        self.generate_rule(name='solink',
                           command=ld + ' -shared ' + link_args,
                           rspfile='${out}.rsp',
                           rspfile_content='${in}',
                           description='LINK SHARED ${out}',
                           pool=pool)

    def _cc_compile_command_wrapper_template(self, inclusion_stack_file, cuda=False):
        """Calculate the cc compile command wrapper template."""
        # When dumping compdb, a raw compile command without wrapper should be generated,
        # otherwise some tools can't handle it.
        if self.command == 'dump' and self.options.dump_compdb:
            return '%s'

        print_header_option = '-H'
        if cuda:
            print_header_option = '-Xcompiler -H'

        if _shell_support_pipefail():
            # Use `pipefail` to ensure that the exit code is correct.
            template = 'export LC_ALL=C; set -o pipefail; %%s %s 2>&1 | %s > %s' % (
                print_header_option, _INCLUSION_STACK_SPLITTER, inclusion_stack_file)
        else:
            # Some shell such as Ubuntu's `dash` doesn't support pipefail, make a workaround.
            template = ('export LC_ALL=C; %%s %s 2> ${out}.err; ec=$$?; %s < ${out}.err > %s ; '
                        'rm -f ${out}.err; exit $$ec') % (
                            print_header_option, _INCLUSION_STACK_SPLITTER, inclusion_stack_file)

        return template

    def generate_proto_rules(self):
        proto_config = config.get_section('proto_library_config')
        protoc = proto_config['protoc']
        protoc_java = protoc
        if proto_config['protoc_java']:
            protoc_java = proto_config['protoc_java']
        protobuf_incs = protoc_import_path_option(proto_config['protobuf_incs'])
        protobuf_java_incs = protobuf_incs
        if proto_config['protobuf_java_incs']:
            protobuf_java_incs = protoc_import_path_option(proto_config['protobuf_java_incs'])
        self._add_line(textwrap.dedent('''\
                protocflags =
                protoccpppluginflags =
                protocjavapluginflags =
                protocpythonpluginflags =
                '''))
        self.generate_rule(name='proto',
                           command='%s --proto_path=. %s -I=`dirname ${in}` '
                                   '--cpp_out=%s ${protocflags} ${protoccpppluginflags} ${in}' % (
                                       protoc, protobuf_incs, self.build_dir),
                           description='PROTOC CPP ${in}')
        self.generate_rule(name='protojava',
                           command='%s --proto_path=. %s --java_out=%s/`dirname ${in}` '
                                   '${protocjavapluginflags} ${in}' % (
                                       protoc_java, protobuf_java_incs, self.build_dir),
                           description='PROTOC JAVA ${in}')
        self.generate_rule(name='protopython',
                           command='%s --proto_path=. %s -I=`dirname ${in}` '
                                   '--python_out=%s ${protocpythonpluginflags} ${in}' % (
                                       protoc, protobuf_incs, self.build_dir),
                           description='PROTOC PYTHON ${in}')
        self.generate_rule(name='protodescriptors',
                           command='%s --proto_path=. %s -I=`dirname ${first}` '
                                   '--descriptor_set_out=${out} --include_imports '
                                   '--include_source_info ${in}' % (
                                       protoc, protobuf_incs),
                           description='PROTODESCRIPTORS ${in}')
        protoc_go_plugin = proto_config['protoc_go_plugin']
        if protoc_go_plugin:
            go_home = config.get_item('go_config', 'go_home')
            go_module_enabled = config.get_item('go_config', 'go_module_enabled')
            go_module_relpath = config.get_item('go_config', 'go_module_relpath')
            if not go_home:
                console.fatal('"go_config.go_home" is not configured')
            if go_module_enabled and not go_module_relpath:
                outdir = proto_config['protobuf_go_path']
            else:
                outdir = os.path.join(go_home, 'src')
            subplugins = proto_config['protoc_go_subplugins']
            if subplugins:
                go_out = 'plugins=%s:%s' % ('+'.join(subplugins), outdir)
            else:
                go_out = outdir
            self.generate_rule(name='protogo',
                               command='%s --proto_path=. %s -I=`dirname ${in}` '
                                       '--plugin=protoc-gen-go=%s --go_out=%s ${in}' % (
                                           protoc, protobuf_incs, protoc_go_plugin, go_out),
                               description='PROTOCGOLANG ${in}')

    def generate_resource_rules(self):
        args = '${name} ${path} ${out} ${in}'
        self.generate_rule(name='resource_index',
                           command=self._builtin_command('resource_index', args),
                           description='RESOURCE INDEX ${out}')
        self.generate_rule(name='resource',
                           command='xxd -i ${in} | '
                                   'sed -e "s/^unsigned char /const char RESOURCE_/g" '
                                   '-e "s/^unsigned int /const unsigned int RESOURCE_/g" > ${out}',
                           description='RESOURCE ${in}')

    def get_java_command(self, java_config, cmd):
        java_home = java_config['java_home']
        if java_home:
            return os.path.join(java_home, 'bin', cmd)
        return cmd

    def get_jacocoagent(self):
        jacoco_home = config.get_item('java_test_config', 'jacoco_home')
        if jacoco_home:
            return os.path.join(jacoco_home, 'lib', 'jacocoagent.jar')
        return ''

    def generate_javac_rules(self, java_config):
        javac = self.get_java_command(java_config, 'javac')
        jar = self.get_java_command(java_config, 'jar')
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
        self._add_line(textwrap.dedent('''\
                source_encoding = UTF-8
                classpath = .
                javacflags =
                '''))
        jarflags = 'cf' + config.get_item('java_config', 'jar_compression_level')
        self.generate_rule(name='javac',
                           command='rm -fr ${classes_dir} && mkdir -p ${classes_dir} && '
                                   '%s && sleep 0.01 && '
                                   '%s %s ${out} -C ${classes_dir} .' % (
                                       ' '.join(cmd), jar, jarflags),
                           description='JAVAC ${out}')

    def generate_java_resource_rules(self):
        self.generate_rule(name='javaresource',
                           command=self._builtin_command('java_resource'),
                           description='JAVA RESOURCE ${resources_dir}')

    def generate_java_jar_rules(self, java_config):
        jar = self.get_java_command(java_config, 'jar')
        level = config.get_item('java_config', 'jar_compression_level')
        args = '%s --compression_level=%s ${out} ${in}' % (jar, level)
        self.generate_rule(name='javajar',
                           command=self._builtin_command('java_jar', args),
                           description='JAVA JAR ${out}')

    def generate_java_test_rules(self):
        jacocoagent = self.get_jacocoagent()
        args = ('--script=${out} --main_class=${mainclass} --jacocoagent=%s '
                '--packages_under_test=${packages_under_test} ${in}') % jacocoagent
        self.generate_rule(name='javatest',
                           command=self._builtin_command('java_test', args),
                           description='JAVA TEST ${out}')

    def generate_fatjar_rules(self, java_config):
        conflict_severity = java_config.get('fat_jar_conflict_severity', 'warning')
        compression_level = java_config.get('fat_jar_compression_level')
        args = '--output=${out} --compression_level=%s --conflict_severity=%s ${in}' % (
            compression_level, conflict_severity)
        self.generate_rule(name='fatjar',
                           command=self._builtin_command('java_fatjar', args),
                           description='FAT JAR ${out}')

    def generate_java_binary_rules(self):
        bootjar = config.get_item('java_binary_config', 'one_jar_boot_jar')
        args = '--onejar=${out} --bootjar=%s --main_class=${mainclass} ${in}' % bootjar
        self.generate_rule(name='onejar',
                           command=self._builtin_command('java_onejar', args),
                           description='ONE JAR ${out}')
        self.generate_rule(name='javabinary',
                           command=self._builtin_command('java_binary'),
                           description='JAVA BINARY ${out}')

    def generate_scalac_rule(self, java_config):
        scalac = 'scalac'
        scala_home = config.get_item('scala_config', 'scala_home')
        if scala_home:
            scalac = os.path.join(scala_home, 'bin', scalac)
        java = self.get_java_command(java_config, 'java')
        self._add_line(textwrap.dedent('''\
                scalacflags = -nowarn
                '''))
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

    def generate_scalatest_rule(self, java_config):
        java = self.get_java_command(java_config, 'java')
        scala = 'scala'
        scala_home = config.get_item('scala_config', 'scala_home')
        if scala_home:
            scala = os.path.join(scala_home, 'bin', scala)
        jacocoagent = self.get_jacocoagent()
        args = ('--java=%s --scala=%s --jacocoagent=%s --packages_under_test=${packages_under_test} '
                '--script=${out} ${in}') % (java, scala, jacocoagent)
        self.generate_rule(name='scalatest', command=self._builtin_command('scala_test', args),
                           description='SCALA TEST ${out}')

    def generate_java_scala_rules(self):
        java_config = config.get_section('java_config')
        self.generate_javac_rules(java_config)
        self.generate_java_resource_rules()
        jar = self.get_java_command(java_config, 'jar')
        args = '%s ${out} ${in}' % jar
        self.generate_java_jar_rules(java_config)
        self.generate_java_test_rules()
        self.generate_fatjar_rules(java_config)
        self.generate_java_binary_rules()
        self.generate_scalac_rule(java_config)
        self.generate_scalatest_rule(java_config)

    def generate_thrift_rules(self):
        thrift_config = config.get_section('thrift_config')
        incs = _incs_list_to_string(thrift_config['thrift_incs'])
        gen_params = thrift_config['thrift_gen_params']
        thrift = thrift_config['thrift']
        if thrift.startswith('//'):
            thrift = thrift.replace('//', self.build_dir + '/')
            thrift = thrift.replace(':', '/')
        self.generate_rule(name='thrift',
                           command='%s --gen %s '
                                   '-I . %s -I `dirname ${in}` '
                                   '-out %s/`dirname ${in}` ${in}' % (
                                       thrift, gen_params, incs, self.build_dir),
                           description='THRIFT ${in}')

    def generate_python_rules(self):
        args = '--basedir=${basedir} --pylib=${out} ${in}'
        self.generate_rule(name='pythonlibrary',
                           command=self._builtin_command('python_library', args),
                           description='PYTHON LIBRARY ${out}')
        args = ('--basedir=${basedir} --exclusions=${exclusions} --mainentry=${mainentry} '
                '--pybin=${out} ${in}')
        self.generate_rule(name='pythonbinary',
                           command=self._builtin_command('python_binary', args),
                           description='PYTHON BINARY ${out}')

    def generate_go_rules(self):
        go_home = config.get_item('go_config', 'go_home')
        go = config.get_item('go_config', 'go')
        go_module_enabled = config.get_item('go_config', 'go_module_enabled')
        go_module_relpath = config.get_item('go_config', 'go_module_relpath')
        if go_home and go:
            go_pool = 'golang_pool'
            self._add_line(textwrap.dedent('''\
                    pool %s
                      depth = 1
                    ''') % go_pool)
            go_path = os.path.normpath(os.path.abspath(go_home))
            out_relative = ""
            if go_module_enabled:
                prefix = go
                if go_module_relpath:
                    relative_prefix = os.path.relpath(prefix, go_module_relpath)
                    prefix = "cd {go_module_relpath} && {relative_prefix}".format(
                        go_module_relpath=go_module_relpath,
                        relative_prefix=relative_prefix,
                    )
                    # add slash to the end of the relpath
                    out_relative = os.path.join(os.path.relpath("./", go_module_relpath), "")
            else:
                prefix = 'GOPATH=%s %s' % (go_path, go)
            self.generate_rule(name='gopackage',
                               command='%s install ${extra_goflags} ${package}' % prefix,
                               description='GO INSTALL ${package}',
                               pool=go_pool)
            self.generate_rule(name='gocommand',
                               command='%s build -o %s${out} ${extra_goflags} ${package}' % (prefix, out_relative),
                               description='GO BUILD ${package}',
                               pool=go_pool)
            self.generate_rule(name='gotest',
                               command='%s test -c -o %s${out} ${extra_goflags} ${package}' % (prefix, out_relative),
                               description='GO TEST ${package}',
                               pool=go_pool)

    def generate_shell_rules(self):
        self.generate_rule(name='shelltest',
                           command=self._builtin_command('shell_test'),
                           description='SHELL TEST ${out}')
        args = '${out} ${in} ${testdata}'
        self.generate_rule(name='shelltestdata',
                           command=self._builtin_command('shell_testdata', args),
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
                           command=self._builtin_command('package', args),
                           description='PACKAGE ${out}')
        self.generate_rule(name='package_tar',
                           command='tar -c -f ${out} ${tarflags} -C ${packageroot} ${entries}',
                           description='TAR ${out}')
        self.generate_rule(name='package_zip',
                           command='cd ${packageroot} && zip -q temp_archive.zip ${entries} && '
                                   'cd - && mv ${packageroot}/temp_archive.zip ${out}',
                           description='ZIP ${out}')

    def generate_version_rules(self):
        cc = self.build_toolchain.get_cc()
        cc_version = self.build_toolchain.get_cc_version()

        revision, url = util.load_scm(self.build_dir)
        args = '--scm=${out} --revision=${revision} --url=${url} --profile=${profile} --compiler="${compiler}"'
        self.generate_rule(name='scm',
                           command=self._builtin_command('scm', args),
                           description='SCM ${out}')
        scm = os.path.join(self.build_dir, 'scm.cc')
        self._add_line(textwrap.dedent('''\
                build %s: scm
                  revision = %s
                  url = %s
                  profile = %s
                  compiler = %s
                ''') % (scm, revision, url, self.options.profile, '%s %s' % (cc, cc_version)))
        self._add_line(textwrap.dedent('''\
                build %s: cxx %s
                  cppflags = -w -O2
                  cxx_warnings =
                ''') % (scm + '.o', scm))

    def generate_cuda_rules(self):
        nvcc_cmd = '${cmd}'

        cc_config = config.get_section('cc_config')
        cuda_config = config.get_section('cuda_config')
        cxxflags = cc_config['cxxflags']
        cppflags, _ = self._get_intrinsic_cc_flags()
        cppflags = cc_config['cppflags'] + cppflags
        cxxflags = ['-Xcompiler %s' % flag for flag in cxxflags]
        cppflags = ['-Xcompiler %s' % flag for flag in cppflags]
        cuflags = cuda_config['cuflags']
        includes = cc_config['extra_incs']
        includes = includes + ['.', self.build_dir]
        includes = ' '.join(['-I%s' % inc for inc in includes])

        template = self._cc_compile_command_wrapper_template('${out}.H', cuda=True)

        _, cxx, _ = self.build_accelerator.get_cc_commands()
        cu_command = '%s -ccbin %s -o ${out} -MMD -MF ${out}.d ' \
            '-Xcompiler -fPIC %s %s %s ${optimize} ${cu_warnings} ' \
            '%s ${includes} ${cppflags} ${cuflags} -c ${in}' % (
                nvcc_cmd, cxx, ' '.join(cxxflags), ' '.join(cppflags),
                ' '.join(cuflags), includes)
        self.generate_rule(
            name='cudacc',
            command=template % cu_command,
            description='CUDA LIBRARY ${in}',
            depfile='${out}.d',
            deps='gcc',
        )

        link_args = '-o ${out} ${includes} ${cppflags} ${target_linkflags} ${extra_linkflags} ${in}'
        self.generate_rule(
            name='cudalink',
            command=nvcc_cmd + ' ' + link_args,
            description='CUDA LINK BINARY ${out}')

        self.generate_rule(
            name='cudasolink',
            command=nvcc_cmd + ' -shared ' + link_args,
            description='CUDA LINK SHARED ${out}')

    def _builtin_command(self, builder, args=''):
        cmd = ['PYTHONPATH=%s:$$PYTHONPATH' % self.blade_path]
        python = os.environ.get('BLADE_PYTHON_INTERPRETER') or sys.executable
        cmd.append('%s -m blade.builtin_tools %s' % (python, builder))
        if args:
            cmd.append(args)
        else:
            cmd.append('${out} ${in}')
        return ' '.join(cmd)

    def generate(self):
        """Generate ninja rules."""
        self.generate_file_header()
        self.generate_common_rules()
        self.generate_cc_rules()
        self.generate_proto_rules()
        self.generate_resource_rules()
        self.generate_java_scala_rules()
        self.generate_thrift_rules()
        self.generate_python_rules()
        self.generate_go_rules()
        self.generate_shell_rules()
        self.generate_lex_yacc_rules()
        self.generate_package_rules()
        self.generate_version_rules()
        self.generate_cuda_rules()
        return self.rules_buf


class NinjaFileGenerator(object):
    """Generate ninja rules to build.ninja."""

    def __init__(self, ninja_path, blade_path, blade):
        self.script_path = ninja_path
        self.blade_path = blade_path
        self.blade = blade
        self.build_toolchain = blade.get_build_toolchain()
        self.build_dir = blade.get_build_dir()
        self.__all_rule_names = []

    def get_all_rule_names(self):
        return self.__all_rule_names

    def generate_build_code(self):
        """Generate ninja code to build.ninja."""
        ninja_script_header_generator = _NinjaFileHeaderGenerator(
            self.blade.get_command(),
            self.blade.get_options(),
            self.build_dir,
            self.blade_path,
            self.build_toolchain,
            self.blade)
        code = ninja_script_header_generator.generate()
        code += self.blade.generate_targets_build_code()
        self.__all_rule_names = ninja_script_header_generator.get_all_rule_names()
        return code

    def generate_build_script(self):
        """Generate build script for underlying build system."""
        code = self.generate_build_code()
        script = open(self.script_path, 'w')
        script.writelines(code)
        script.close()
