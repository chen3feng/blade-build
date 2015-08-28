# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Chong Peng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the blade_platform module which dues with the environment
 variable.

"""


import os
import subprocess

import configparse
from blade_util import var_to_list


class SconsPlatform(object):
    """The scons platform class that it handles and gets the platform info. """
    def __init__(self):
        """Init. """
        self.gcc_version = self._get_gcc_version('gcc')
        self.python_inc = self._get_python_include()
        self.php_inc_list = self._get_php_include()
        self.java_inc_list = self._get_java_include()
        self.nvcc_version = self._get_nvcc_version('nvcc')
        self.cuda_inc_list = self._get_cuda_include()

    @staticmethod
    def _get_gcc_version(compiler):
        """Get the gcc version. """
        p = subprocess.Popen(
            compiler + ' --version',
            env=os.environ,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True)
        (stdout, stderr) = p.communicate()
        if p.returncode == 0:
            version_line = stdout.splitlines(True)[0]
            version = version_line.split()[2]
            return version
        return ''

    @staticmethod
    def _get_nvcc_version(compiler):
        """Get the nvcc version. """
        p = subprocess.Popen(
            compiler + ' --version',
            env=os.environ,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True)
        (stdout, stderr) = p.communicate()
        if p.returncode == 0:
            version_line = stdout.splitlines(True)[-1]
            version = version_line.split()[5]
            return version
        return ''

    @staticmethod
    def _get_python_include():
        """Get the python include dir. """
        p = subprocess.Popen(
            'python-config --includes',
            env=os.environ,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True)
        (stdout, stderr) = p.communicate()
        if p.returncode == 0:
            include_line = stdout.splitlines(True)[0]
            header = include_line.split()[0][2:]
            return header
        return ''

    @staticmethod
    def _get_php_include():
        p = subprocess.Popen(
            'php-config --includes',
            env=os.environ,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True)
        (stdout, stderr) = p.communicate()
        if p.returncode == 0:
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
        p = subprocess.Popen(
            'java -version',
            env=os.environ,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            universal_newlines=True)
        (stdout, stderr) = p.communicate()
        if p.returncode == 0:
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
        p = subprocess.Popen(
            'nvcc --version',
            env=os.environ,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True)
        (stdout, stderr) = p.communicate()
        if p.returncode == 0:
            version_line = stdout.splitlines(True)[-1]
            version = version_line.split()[4]
            version = version.replace(',', '')
            if os.path.isdir('/usr/local/cuda-%s' % version):
                include_list.append('/usr/local/cuda-%s/include' % version)
                include_list.append('/usr/local/cuda-%s/samples/common/inc' % version)
                return include_list
        return []

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
    def __init__(self, options):
        self.options = options
        self.cpp_str = ''

    def _filter_out_invalid_flags(self, flag_list, language=''):
        """filter the unsupported compliation flags. """
        flag_list_var = var_to_list(flag_list)
        xlanguage = ''
        if language:
            xlanguage = '-x' + language

        ret_flag_list = []
        for flag in flag_list_var:
            cmd_str = 'echo "" | %s %s %s >/dev/null 2>&1' % (
                      self.cpp_str, xlanguage, flag)
            if subprocess.call(cmd_str, shell=True) == 0:
                ret_flag_list.append(flag)
        return ret_flag_list

    def set_cpp_str(self, cpp_str):
        """set up the cpp_str. """
        self.cpp_str = cpp_str

    def get_flags_except_warning(self):
        """Get the flags that are not warning flags. """
        flags_except_warning = ['-m%s' % self.options.m, '-mcx16', '-pipe']
        linkflags = ['-m%s' % self.options.m]

        # Debigging information setting
        if self.options.no_debug_info:
            flags_except_warning += ['-g0']
        else:
            if self.options.profile == 'debug':
                flags_except_warning += ['-ggdb3']
            elif self.options.profile == 'release':
                flags_except_warning += ['-g']

        # Option debugging flags
        if self.options.profile == 'debug':
            flags_except_warning += ['-fstack-protector']
        elif self.options.profile == 'release':
            flags_except_warning += ['-DNDEBUG']

        flags_except_warning += [
                '-D_FILE_OFFSET_BITS=64',
                '-D__STDC_CONSTANT_MACROS',
                '-D__STDC_FORMAT_MACROS',
                '-D__STDC_LIMIT_MACROS',
        ]

        if getattr(self.options, 'gprof', False):
            flags_except_warning.append('-pg')
            linkflags.append('-pg')

        if getattr(self.options, 'gcov', False):
            if SconsPlatform().gcc_version > '4.1':
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
