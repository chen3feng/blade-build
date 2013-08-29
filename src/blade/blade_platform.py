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
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True)
        (stdout, stderr) = p.communicate()
        if p.returncode == 0:
            version_line = stderr.splitlines(True)[0]
            version = version_line.split()[2]
            version = version.replace('"', '')
            include_list.append('/usr/java/jdk%s/include' % version)
            include_list.append('/usr/java/jdk%s/include/linux' % version)
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


class CcFlagsManager(object):
    """The CcFlagsManager class.

    This class manages the compile warning flags.

    """
    def __init__(self, options):
        self.options = options
        self.cpp_str = ''

    def _filter_out_invalid_flags(self, flag_list, flag_type='cpp'):
        """filter the unsupported compliation flags. """
        flag_type_list = ['cpp', 'c', 'cxx']
        flag_list_var = var_to_list(flag_list)
        if not flag_type in flag_type_list:
            return flag_list

        option = ''
        if flag_type == 'c':
            option = '-xc'
        elif flag_type == 'cxx':
            option = '-xc++'

        ret_flag_list = []
        for flag in flag_list_var:
            cmd_str = 'echo "" | %s %s %s >/dev/null 2>&1' % (
                      self.cpp_str, option, flag)
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
        if self.options.profile == 'debug':
            flags_except_warning += ['-ggdb3', '-fstack-protector']
        elif self.options.profile == 'release':
            flags_except_warning += ['-g', '-DNDEBUG']
        flags_except_warning += [
                '-D_FILE_OFFSET_BITS=64',
                '_D__STDC_CONSTANT_MACROS',
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
                flags_except_warning, 'cpp')

        return (flags_except_warning, linkflags)

    def get_warning_flags(self):
        """Get the warning flags. """
        cc_config = configparse.blade_config.get_config('cc_config')
        cppflags = cc_config['warnings']
        cxxflags = cc_config['cxx_warnings']
        cflags = cc_config['c_warnings']

        filtered_cppflags = self._filter_out_invalid_flags(cppflags, 'cpp')
        filtered_cxxflags = self._filter_out_invalid_flags(cxxflags, 'cxx')
        filtered_cflags = self._filter_out_invalid_flags(cflags, 'c')

        return (filtered_cppflags, filtered_cxxflags, filtered_cflags)
