# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   August 02, 2012


"""
 building environment checking and managing module.

"""

from __future__ import absolute_import
from __future__ import print_function

import os
import subprocess

from blade import console


class BuildEnvironment(object):
    """Managers ccache, distcc. """

    def __init__(self, blade_root_dir, distcc_host_list=None):
        # ccache
        self.blade_root_dir = blade_root_dir
        self.ccache_installed = self._check_ccache_install()

        # distcc
        self.distcc_env_prepared = False
        self.distcc_installed = self._check_distcc_install()
        self.distcc_host_list = distcc_host_list or os.environ.get('DISTCC_HOSTS', '')
        if self.distcc_installed and self.distcc_host_list:
            self.distcc_env_prepared = True
            console.info('distcc is enabled automatically due DISTCC_HOSTS set')
            distcc_log_file = os.environ.get('DISTCC_LOG', '')
            if distcc_log_file:
                console.debug('distcc log: %s' % distcc_log_file)

        self.rules_buf = []

    @staticmethod
    def _check_ccache_install():
        """Check ccache is installed or not. """
        CC = os.getenv('CC')
        CXX = os.getenv('CXX')
        # clang scan-build always fail with ccache.
        if CC and os.path.basename(CC) == 'ccc-analyzer' and CXX and os.path.basename(CXX) == 'c++-analyzer':
            console.debug('ccache is disabled for scan-build')
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
                    console.debug('ccache found')
                    return True
        except OSError:
            pass
        return False

    @staticmethod
    def _check_distcc_install():
        """Check distcc is installed or not. """
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
                console.debug('distcc found')
                return True

    def setup_build_cache(self, options):
        if self.ccache_installed:
            self._add_rule('top_env.Append(CCACHE_BASEDIR="%s")' % self.blade_root_dir)
            self._add_rule('top_env.Append(CCACHE_NOHASHDIR="true")')

    def setup_distcc_env(self):
        """Generates distcc rules. """
        if self.distcc_installed:
            self._add_rule('top_env.Append(DISTCC_HOSTS="%s")' % self.distcc_host_list)

    def get_distcc_hosts_list(self):
        """Returns the hosts list. """
        return [x for x in self.distcc_host_list.split(' ') if x]

    def _add_rule(self, rule):
        """Append to buffer. """
        self.rules_buf.append(rule)

    def get_rules(self):
        """Return the scons rules. """
        return self.rules_buf
