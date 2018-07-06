# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Chong Peng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the blade_platform module which deals with the environment
 variable.

"""


import os
import subprocess

import configparse
import console
from blade_util import var_to_list


class BuildArchitecture(object):
    """
    The BuildArchitecture class manages architecture/bits configuration
    across various platforms/compilers combined with the input from
    command line.
    """
    _build_architecture = {
        'i386' : {
            'alias' : ['x86'],
            'bits' : '32',
        },
        'x86_64' : {
            'alias' : ['amd64'],
            'bits' : '64',
            'models' : {
                '32' : 'i386',
            }
        },
        'ppc' : {
            'alias' : ['powerpc'],
            'bits' : '32',
        },
        'ppc64' : {
            'alias' : ['powerpc64'],
            'bits' : '64',
            'models' : {
                '32' : 'ppc',
            }
        },
        'ppc64le' : {
            'alias' : ['powerpc64le'],
            'bits' : '64',
            'models' : {
                '32' : 'ppcle',
            }
        },
    }

    @staticmethod
    def get_canonical_architecture(arch):
        """Get the canonical architecture from the specified arch. """
        canonical_arch = None
        for k, v in BuildArchitecture._build_architecture.iteritems():
            if arch == k or arch in v['alias']:
                canonical_arch = k
                break
        return canonical_arch

    @staticmethod
    def get_architecture_bits(arch):
        """Get the architecture bits. """
        arch = BuildArchitecture.get_canonical_architecture(arch)
        if arch:
            return BuildArchitecture._build_architecture[arch]['bits']
        return None

    @staticmethod
    def get_model_architecture(arch, bits):
        """
        Get the model architecture from the specified arch and bits,
        such as, if arch is x86_64 and bits is '32', then the resulting
        model architecture is i386 which effectively means building
        32 bit target in a 64 bit environment.
        """
        arch = BuildArchitecture.get_canonical_architecture(arch)
        if arch:
            if bits == BuildArchitecture._build_architecture[arch]['bits']:
                return arch
            models = BuildArchitecture._build_architecture[arch].get('models')
            if models and bits in models:
                return models[bits]
        return None


class BuildPlatform(object):
    """The build platform class which handles and gets the platform info. """
    def __init__(self):
        """Init. """
        self.gcc_version = self._get_gcc_version()
        self.python_inc = self._get_python_include()
        self.php_inc_list = self._get_php_include()
        self.java_inc_list = self._get_java_include()
        self.nvcc_version = self._get_nvcc_version()
        self.cuda_inc_list = self._get_cuda_include()

    @staticmethod
    def _get_gcc_version():
        """Get the gcc version. """
        gcc = os.path.join(os.environ.get('TOOLCHAIN_DIR', ''),
                           os.environ.get('CC', 'gcc'))
        returncode, stdout, stderr = BuildPlatform._execute(gcc + ' -dumpversion')
        if returncode == 0:
            return stdout.strip()
        return ''

    @staticmethod
    def _get_cc_target_arch():
        """Get the cc target architecture. """
        gcc = os.path.join(os.environ.get('TOOLCHAIN_DIR', ''),
                           os.environ.get('CC', 'gcc'))
        returncode, stdout, stderr = BuildPlatform._execute(gcc + ' -dumpmachine')
        if returncode == 0:
            return stdout.strip()
        return ''

    @staticmethod
    def _get_nvcc_version():
        """Get the nvcc version. """
        nvcc = os.environ.get('NVCC', 'nvcc')
        returncode, stdout, stderr = BuildPlatform._execute(nvcc + ' --version')
        if returncode == 0:
            version_line = stdout.splitlines(True)[-1]
            version = version_line.split()[5]
            return version
        return ''

    @staticmethod
    def _get_python_include():
        """Get the python include dir. """
        returncode, stdout, stderr = BuildPlatform._execute('python-config --includes')
        if returncode == 0:
            include_line = stdout.splitlines(True)[0]
            header = include_line.split()[0][2:]
            return header
        return ''

    @staticmethod
    def _get_php_include():
        returncode, stdout, stderr = BuildPlatform._execute('php-config --includes')
        if returncode == 0:
            include_line = stdout.splitlines(True)[0]
            headers = include_line.split()
            header_list = ["'%s'" % s[2:] for s in headers]
            return header_list
        return []

    @staticmethod
    def _get_java_include():
        include_list = []
        java_home = os.environ.get('JAVA_HOME', '')
        if java_home:
            include_list.append('%s/include' % java_home)
            include_list.append('%s/include/linux' % java_home)
            return include_list
        returncode, stdout, stderr = BuildPlatform._execute(
                'java -version', redirect_stderr_to_stdout = True)
        if returncode == 0:
            version_line = stdout.splitlines(True)[0]
            version = version_line.split()[2]
            version = version.replace('"', '')
            include_list.append('/usr/java/jdk%s/include' % version)
            include_list.append('/usr/java/jdk%s/include/linux' % version)
            return include_list
        return []

    @staticmethod
    def _get_cuda_include():
        include_list = []
        cuda_path = os.environ.get('CUDA_PATH')
        if cuda_path:
            include_list.append('%s/include' % cuda_path)
            include_list.append('%s/samples/common/inc' % cuda_path)
            return include_list
        returncode, stdout, stderr = BuildPlatform._execute('nvcc --version')
        if returncode == 0:
            version_line = stdout.splitlines(True)[-1]
            version = version_line.split()[4]
            version = version.replace(',', '')
            if os.path.isdir('/usr/local/cuda-%s' % version):
                include_list.append('/usr/local/cuda-%s/include' % version)
                include_list.append('/usr/local/cuda-%s/samples/common/inc' % version)
                return include_list
        return []

    @staticmethod
    def _execute(cmd, redirect_stderr_to_stdout = False):
        redirect_stderr = subprocess.PIPE
        if redirect_stderr_to_stdout:
            redirect_stderr = subprocess.STDOUT
        p = subprocess.Popen(cmd,
                             env=os.environ,
                             stderr=redirect_stderr,
                             stdout=subprocess.PIPE,
                             shell=True,
                             universal_newlines=True)
        stdout, stderr = p.communicate()
        return p.returncode, stdout, stderr

    def get_gcc_version(self):
        """Returns gcc version. """
        return self.gcc_version

    def get_python_include(self):
        """Returns python include. """
        return self.python_inc

    def get_php_include(self):
        """Returns a list of php include. """
        return self.php_inc_list

    def get_java_include(self):
        """Returns a list of java include. """
        return self.java_inc_list

    def get_nvcc_version(self):
        """Returns nvcc version. """
        return self.nvcc_version

    def get_cuda_include(self):
        """Returns a list of cuda include. """
        return self.cuda_inc_list


class CcFlagsManager(object):
    """The CcFlagsManager class.

    This class manages the compile warning flags.

    """
    def __init__(self, options, build_dir, gcc_version):
        self.cc = ''
        self.options = options
        self.build_dir = build_dir
        self.gcc_version = gcc_version

    def _filter_out_invalid_flags(self, flag_list, language='c'):
        """Filter the unsupported compilation flags. """
        supported_flags, unsupported_flags = [], []
        # Put compilation output into test.o instead of /dev/null
        # because the command line with '--coverage' below exit
        # with status 1 which makes '--coverage' unsupported
        # echo "int main() { return 0; }" | gcc -o /dev/null -c -x c --coverage - > /dev/null 2>&1
        obj = os.path.join(self.build_dir, 'test.o')
        for flag in var_to_list(flag_list):
            cmd = ('echo "int main() { return 0; }" | '
                   '%s -o %s -c -x %s %s - > /dev/null 2>&1 && rm -f %s' % (
                   self.cc, obj, language, flag, obj))
            if subprocess.call(cmd, shell=True) == 0:
                supported_flags.append(flag)
            else:
                unsupported_flags.append(flag)
        if unsupported_flags:
            console.warning('Unsupported C/C++ flags: %s' %
                            ', '.join(unsupported_flags))
        return supported_flags

    def set_cc(self, cc):
        """set up the compiler. """
        self.cc = cc

    def get_flags_except_warning(self):
        """Get the flags that are not warning flags. """
        global_config = configparse.blade_config.get_config('global_config')
        cc_config = configparse.blade_config.get_config('cc_config')
        flags_except_warning = ['-m%s' % self.options.m, '-mcx16', '-pipe']
        linkflags = ['-m%s' % self.options.m]

        # Debugging information setting
        debug_info_level = global_config['debug_info_level']
        debug_info_options = cc_config['debug_info_levels'][debug_info_level]
        flags_except_warning += debug_info_options

        # Option debugging flags
        if self.options.profile == 'debug':
            flags_except_warning.append('-fstack-protector')
        elif self.options.profile == 'release':
            flags_except_warning.append('-DNDEBUG')

        flags_except_warning += [
                '-D_FILE_OFFSET_BITS=64',
                '-D__STDC_CONSTANT_MACROS',
                '-D__STDC_FORMAT_MACROS',
                '-D__STDC_LIMIT_MACROS',
        ]

        if getattr(self.options, 'gprof', False):
            flags_except_warning.append('-pg')
            linkflags.append('-pg')

        if getattr(self.options, 'coverage', False):
            if self.gcc_version > '4.1':
                flags_except_warning.append('--coverage')
                linkflags.append('--coverage')
            else:
                flags_except_warning.append('-fprofile-arcs')
                flags_except_warning.append('-ftest-coverage')
                linkflags += ['-Wl,--whole-archive', '-lgcov',
                              '-Wl,--no-whole-archive']

        flags_except_warning = self._filter_out_invalid_flags(
                flags_except_warning)

        return (flags_except_warning, linkflags)

    def get_warning_flags(self):
        """Get the warning flags. """
        cc_config = configparse.blade_config.get_config('cc_config')
        cppflags = cc_config['warnings']
        cxxflags = cc_config['cxx_warnings']
        cflags = cc_config['c_warnings']

        filtered_cppflags = self._filter_out_invalid_flags(cppflags)
        filtered_cxxflags = self._filter_out_invalid_flags(cxxflags, 'c++')
        filtered_cflags = self._filter_out_invalid_flags(cflags, 'c')

        return (filtered_cppflags, filtered_cxxflags, filtered_cflags)
