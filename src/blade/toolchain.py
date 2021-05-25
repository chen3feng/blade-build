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
import re
import subprocess
import tempfile

from blade import console
from blade.util import var_to_list, iteritems, to_string

# example: Cuda compilation tools, release 11.0, V11.0.194
_nvcc_version_re = re.compile(r'V(\d+\.\d+\.\d+)')

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
        """Get the canonical architecture from the specified arch."""
        canonical_arch = None
        for k, v in iteritems(BuildArchitecture._build_architecture):
            if arch == k or arch in v['alias']:
                canonical_arch = k
                break
        return canonical_arch

    @staticmethod
    def get_architecture_bits(arch):
        """Get the architecture bits."""
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
    """The build platform handles and gets the platform information."""

    def __init__(self):
        self.cc = self._get_cc_command('CC', 'gcc')
        self.cxx = self._get_cc_command('CXX', 'g++')
        self.ld = self._get_cc_command('LD', 'g++')
        self.cc_version = self._get_cc_version()
        self.nvcc_version = self._get_nvcc_version()
        self.cuda_inc_list = self._get_cuda_include()

    @staticmethod
    def _get_cc_command(env, default):
        """Get a cc command.
        """
        return os.path.join(os.environ.get('TOOLCHAIN_DIR', ''), os.environ.get(env, default))

    def _get_cc_version(self):
        version = ''
        if 'gcc' in self.cc:
            returncode, stdout, stderr = ToolChain._execute(self.cc + ' -dumpversion')
            if returncode == 0:
                version = stdout.strip()
        elif 'clang' in self.cc:
            returncode, stdout, stderr = ToolChain._execute(self.cc + ' --version')
            if returncode == 0:
                line = stdout.splitlines()[0]
                pos = line.find('version')
                if pos == -1:
                    version = line
                else:
                    version = line[pos + len('version') + 1:]
        if not version:
            console.fatal('Failed to obtain cc toolchain.')
        return version

    @staticmethod
    def get_cc_target_arch():
        """Get the cc target architecture."""
        cc = ToolChain._get_cc_command('CC', 'gcc')
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
        """Get the nvcc version."""
        nvcc = os.environ.get('NVCC', 'nvcc')
        returncode, stdout, _ = ToolChain._execute(nvcc + ' --version')
        if returncode == 0:
            res = re.search(_nvcc_version_re, stdout)
            if res:
                return res.group(1)
        return ''

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

    def get_cc_commands(self):
        return self.cc, self.cxx, self.ld

    def get_cc(self):
        return self.cc

    def get_cc_version(self):
        return self.cc_version

    def cc_is(self, vendor):
        """Is cc is used for C/C++ compilation match vendor."""
        return vendor in self.cc

    def get_nvcc_version(self):
        """Returns nvcc version."""
        return self.nvcc_version

    def get_cuda_include(self):
        """Returns a list of cuda include."""
        return self.cuda_inc_list

    def filter_cc_flags(self, flag_list, language='c'):
        """Filter out the unrecognized compilation flags."""
        flag_list = var_to_list(flag_list)
        valid_flags, unrecognized_flags = [], []

        # Put compilation output into test.o instead of /dev/null
        # because the command line with '--coverage' below exit
        # with status 1 which makes '--coverage' unsupported
        # echo "int main() { return 0; }" | gcc -o /dev/null -c -x c --coverage - > /dev/null 2>&1
        fd, obj = tempfile.mkstemp('.o', 'filter_cc_flags_test')
        cmd = ('export LC_ALL=C; echo "int main() { return 0; }" | '
               '%s -o %s -c -x %s -Werror %s -' % (
                   self.cc, obj, language, ' '.join(flag_list)))
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        unused_out, err = p.communicate()

        try:
            # In case of error, the `.o` file will be deleted by the compiler
            os.remove(obj)
        except OSError:
            pass
        os.close(fd)

        if p.returncode == 0:
            return flag_list
        for flag in flag_list:
            # Example error messages:
            #   clang: warning: unknown warning option '-Wzzz' [-Wunknown-warning-option]
            #   gcc:   gcc: error: unrecognized command line option '-Wxxx'
            if " option '%s'" % flag in err:
                unrecognized_flags.append(flag)
            else:
                valid_flags.append(flag)

        if unrecognized_flags:
            console.warning('config: Unrecognized %s flags: %s' % (
                    language, ', '.join(unrecognized_flags)))

        return valid_flags
