# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Chong Peng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This module deals with the build toolchains.
"""

from __future__ import absolute_import
from __future__ import print_function

import os
import subprocess
import tempfile

from blade import config
from blade import console
from blade.blade_util import var_to_list, iteritems, to_string


class BuildArchitecture(object):
    """
    The BuildArchitecture class manages architecture/bits configuration
    across various platforms/compilers combined with the input from
    command line.
    """
    _build_architecture = {
        'i386': {
            'alias': ['x86'],
            'bits': '32',
        },
        'x86_64': {
            'alias': ['amd64'],
            'bits': '64',
            'models': {
                '32': 'i386',
            }
        },
        'arm': {
            'alias': [],
            'bits': '32'
        },
        'aarch64': {
            'alias': ['arm64'],
            'bits': '64',
        },
        'ppc': {
            'alias': ['powerpc'],
            'bits': '32',
        },
        'ppc64': {
            'alias': ['powerpc64'],
            'bits': '64',
            'models': {
                '32': 'ppc',
            }
        },
        'ppc64le': {
            'alias': ['powerpc64le'],
            'bits': '64',
            'models': {
                '32': 'ppcle',
            }
        },
    }

    @staticmethod
    def get_canonical_architecture(arch):
        """Get the canonical architecture from the specified arch. """
        canonical_arch = None
        for k, v in iteritems(BuildArchitecture._build_architecture):
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


class ToolChain(object):
    """The build platform handles and gets the platform information. """

    def __init__(self):
        self.cc, self.cc_version = self._get_cc_toolchain()
        self.php_inc_list = self._get_php_include()
        self.java_inc_list = self._get_java_include()
        self.nvcc_version = self._get_nvcc_version()
        self.cuda_inc_list = self._get_cuda_include()

    @staticmethod
    def _get_cc_toolchain():
        """Get the cc toolchain. """
        cc = os.path.join(os.environ.get('TOOLCHAIN_DIR', ''),
                          os.environ.get('CC', 'gcc'))
        version = ''
        if 'gcc' in cc:
            returncode, stdout, stderr = ToolChain._execute(cc + ' -dumpversion')
            if returncode == 0:
                version = stdout.strip()
        elif 'clang' in cc:
            returncode, stdout, stderr = ToolChain._execute(cc + ' --version')
            if returncode == 0:
                line = stdout.splitlines()[0]
                pos = line.find('version')
                if pos == -1:
                    version = line
                else:
                    version = line[pos + len('version') + 1:]
        if not version:
            console.fatal('Failed to obtain cc toolchain.')
        return cc, version

    @staticmethod
    def _get_cc_target_arch():
        """Get the cc target architecture. """
        cc = os.path.join(os.environ.get('TOOLCHAIN_DIR', ''),
                          os.environ.get('CC', 'gcc'))
        if 'gcc' in cc:
            returncode, stdout, stderr = ToolChain._execute(cc + ' -dumpmachine')
            if returncode == 0:
                return stdout.strip()
        elif 'clang' in cc:
            llc = cc[:-len('clang')] + 'llc'
            returncode, stdout, stderr = ToolChain._execute('%s --version' % llc)
            if returncode == 0:
                for line in stdout.splitlines():
                    if 'Default target' in line:
                        return line.split()[-1]
        return ''

    @staticmethod
    def _get_nvcc_version():
        """Get the nvcc version. """
        nvcc = os.environ.get('NVCC', 'nvcc')
        returncode, stdout, stderr = ToolChain._execute(nvcc + ' --version')
        if returncode == 0:
            version_line = stdout.splitlines(True)[-1]
            version = version_line.split()[5]
            return version
        return ''

    @staticmethod
    def _get_php_include():
        returncode, stdout, stderr = ToolChain._execute('php-config --includes')
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
        returncode, stdout, stderr = ToolChain._execute(
            'java -version', redirect_stderr_to_stdout=True)
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
        returncode, stdout, stderr = ToolChain._execute('nvcc --version')
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
    def _execute(cmd, redirect_stderr_to_stdout=False):
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
        stdout = to_string(stdout)
        stderr = to_string(stderr)
        return p.returncode, stdout, stderr

    def get_cc(self):
        return self.cc

    def get_cc_version(self):
        return self.cc_version

    def cc_is(self, vendor):
        """Is cc is used for C/C++ compilation match vendor. """
        return vendor in self.cc

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

    def filter_cc_flags(self, flag_list, language='c'):
        """Filter out the unrecognized compilation flags. """
        valid_flags, unrecognized_flags = [], []
        # Put compilation output into test.o instead of /dev/null
        # because the command line with '--coverage' below exit
        # with status 1 which makes '--coverage' unsupported
        # echo "int main() { return 0; }" | gcc -o /dev/null -c -x c --coverage - > /dev/null 2>&1
        fd, obj = tempfile.mkstemp('.o', 'filter_cc_flags_test')
        for flag in var_to_list(flag_list):
            cmd = ('echo "int main() { return 0; }" | '
                   '%s -o %s -c -x %s -Werror %s - > /dev/null 2>&1' % (
                       self.cc, obj, language, flag))
            if subprocess.call(cmd, shell=True) == 0:
                valid_flags.append(flag)
            else:
                unrecognized_flags.append(flag)
        os.remove(obj)
        os.close(fd)
        if unrecognized_flags:
            console.warning('config: Unrecognized %s flags: %s' % (
                    language, ', '.join(unrecognized_flags)))
        return valid_flags
