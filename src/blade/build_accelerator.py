# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   August 02, 2012

"""
 build accelerator (ccache, distcc, etc.) checking and managing module.
"""

from __future__ import absolute_import
from __future__ import print_function

import os
import subprocess

from blade import config
from blade import console


class BuildAccelerator(object):
    """Managers ccache, distcc."""

    def __init__(self, blade_root_dir, toolchain, distcc_host_list=None):
        # ccache
        self.blade_root_dir = blade_root_dir
        self.__toolchain = toolchain
        self.ccache_installed = self._check_ccache_install()

        # distcc
        self.distcc_env_prepared = False
        self.distcc_installed = self._check_distcc_install()
        self.distcc_host_list = distcc_host_list or os.environ.get('DISTCC_HOSTS', '')
        if self.distcc_installed and self.distcc_host_list:
            self.distcc_env_prepared = True
            console.info('Distcc is enabled automatically due DISTCC_HOSTS set')
            distcc_log_file = os.environ.get('DISTCC_LOG', '')
            if distcc_log_file:
                console.debug('Distcc log: %s' % distcc_log_file)

    @staticmethod
    def _check_ccache_install():
        """Check ccache is installed or not."""
        CC = os.getenv('CC')
        CXX = os.getenv('CXX')
        # clang scan-build always fail with ccache.
        if CC and os.path.basename(CC) == 'ccc-analyzer' and CXX and os.path.basename(CXX) == 'c++-analyzer':
            console.debug('Ccache is disabled for scan-build')
            return False

        try:
            p = subprocess.Popen(
                ['ccache', '-V'],
                env=os.environ,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                universal_newlines=True)
            (stdout, stderr) = p.communicate()
            if p.returncode == 0:
                version_line = stdout.splitlines(True)[0]
                if version_line and version_line.find('ccache version') != -1:
                    console.debug('Ccache found')
                    return True
        except OSError:
            pass
        return False

    @staticmethod
    def _check_distcc_install():
        """Check distcc is installed or not."""
        p = subprocess.Popen(
            'distcc --version',
            env={},
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True)
        (stdout, stderr) = p.communicate()
        if p.returncode == 0:
            version_line = stdout.splitlines(True)[0]
            if version_line and version_line.find('distcc') != -1:
                console.debug('Distcc found')
                return True
        return False

    def get_distcc_hosts_list(self):
        """Returns the hosts list."""
        return [x for x in self.distcc_host_list.split(' ') if x]

    def get_cc_commands(self):
        """Get correct c/c++ commands with proper build accelerator prefix
        Returns:
            cc, cxx, linker
        """
        cc, cxx, ld = self.__toolchain.get_cc_commands()
        if self.ccache_installed:
            os.environ['CCACHE_BASEDIR'] = self.blade_root_dir
            os.environ['CCACHE_NOHASHDIR'] = 'true'
            cc = 'ccache ' + cc
            cxx = 'ccache ' + cxx
        return cc, cxx, ld

    def adjust_jobs_num(self, cpu_core_num):
        # Calculate job numbers smartly
        distcc_enabled = config.get_item('distcc_config', 'enabled')
        if distcc_enabled and self.distcc_env_prepared:
            # Distcc doesn't cost much local cpu, jobs can be quite large.
            distcc_num = len(self.get_distcc_hosts_list())
            jobs_num = min(max(int(1.5 * distcc_num), 1), 20)
        else:
            # machines with cpu_core_num > 8 is usually shared by multiple users,
            # set an upper bound to avoid interfering other users
            jobs_num = min(cpu_core_num, 8)
        return jobs_num
