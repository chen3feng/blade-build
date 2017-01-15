# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   August 02, 2012


"""
 building environment checking and managing module.

"""


import glob
import math
import os
import subprocess
import time

import console


class BuildEnvironment(object):
    """Managers ccache, distcc, dccc. """
    def __init__(self, blade_root_dir, distcc_hosts_list=None):
        # ccache
        self.blade_root_dir = blade_root_dir
        self.ccache_installed = self._check_ccache_install()

        # distcc
        self.distcc_env_prepared = False
        self.distcc_installed = self._check_distcc_install()
        if distcc_hosts_list:
            self.distcc_host_list = distcc_hosts_list
        else:
            self.distcc_host_list = os.environ.get('DISTCC_HOSTS', '')
        if self.distcc_installed and self.distcc_host_list:
            self.distcc_env_prepared = True
        if self.distcc_installed and not self.distcc_host_list:
            console.warning('DISTCC_HOSTS not set but you have '
                            'distcc installed, will just build locally')
        self.distcc_log_file = os.environ.get('DISTCC_LOG', '')
        if self.distcc_log_file:
            console.info('distcc log: %s' % self.distcc_log_file)

        # dccc
        self.dccc_env_prepared = True
        self.dccc_master = os.environ.get('MASTER_HOSTS', '')
        self.dccc_hosts_list = os.environ.get('DISTLD_HOSTS', '')
        self.dccc_installed = self._check_dccc_install()
        if self.dccc_installed:
            if not self.dccc_master and not self.dccc_hosts_list:
                self.dccc_env_prepared = False
                console.warning('MASTER_HOSTS and DISTLD_HOSTS not set but '
                                'you have dccc installed, will just build '
                                'locally')
        else:
            self.dccc_env_prepared = False

        self.rules_buf = []

    @staticmethod
    def _check_ccache_install():
        """Check ccache is installed or not. """
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
                    console.info('ccache found')
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
                console.info('distcc found')
                return True

    @staticmethod
    def _check_dccc_install():
        """Check dccc is installed or not. """
        home_dir = os.environ.get('HOME', '')
        if home_dir and os.path.exists(os.path.join(home_dir, 'bin', 'dccc')):
            console.info('dccc found')
            return True
        return False

    def setup_ccache(self):
        """Generates ccache rules. """
        if self.ccache_installed:
            self._add_rule('top_env.Append(CCACHE_BASEDIR="%s")' % self.blade_root_dir)

    def setup_scons_cache(self, options):
        """Setup scons cache"""

        cache_dir = getattr(options, 'cache_dir', os.environ.get('BLADE_CACHE_DIR', '~/.bladescache'))
        if not cache_dir:
            # '' to disable cache
            return

        cache_size = getattr(options, 'cache_size', os.environ.get('BLADE_CACHE_SIZE', '2'))
        if cache_size == 'unlimited':
            cache_size = -1
        else:
            cache_size = int(cache_size) * 1024 * 1024 * 1024

        cache_dir = os.path.expanduser(cache_dir)

        self._add_rule('CacheDir("%s")' % cache_dir)
        self._add_rule('scache_manager = build_environment.ScacheManager("%s", cache_limit=%d)' % (
                    cache_dir, cache_size))
        self._add_rule('Progress(scache_manager, interval=100)')

        console.info('using cache directory %s' % cache_dir)
        console.info('scache size %d' % cache_size)

    def setup_build_cache(self, options):
        if self.ccache_installed:  # Perfer ccache because it also cache warning
            self.setup_ccache()
        else:
            self.setup_scons_cache(options)

    def setup_distcc_env(self):
        """Generates distcc rules. """
        if self.distcc_installed:
            self._add_rule('top_env.Append(DISTCC_HOSTS="%s")' % self.distcc_host_list)

    def get_distcc_hosts_list(self):
        """Returns the hosts list. """
        return filter(lambda x: x, self.distcc_host_list.split(' '))

    def _add_rule(self, rule):
        """Append to buffer. """
        self.rules_buf.append(rule)

    def get_rules(self):
        """Return the scons rules. """
        return self.rules_buf


class ScacheManager(object):
    """Scons cache manager.

    Scons cache manager, which should be output to scons script.
    It will periodically check the cache folder and purge the files
    with smallest weight. The weight for each file is caculated as
    file_size * exp(-age * log(2) / half_time).

    We should pay attention that this progress will impact large builds
    and we should not reduce the progress interval(the evaluating nodes).

    """
    def __init__(self, cache_path=None, cache_limit=0,
                 cache_life=6 * 60 * 60):
        self.cache_path = cache_path
        self.cache_limit = cache_limit
        self.cache_life = cache_life
        self.exponent_scale = math.log(2) / cache_life
        self.purge_cnt = 0

    def __call__(self, node, *args, **kwargs):
        self.purge(self.get_file_list())

    def cache_remove(self, file_item):
        if not file_item:
            return
        if not os.path.exists(file_item):
            return
        os.remove(file_item)

    def purge(self, file_list):
        self.purge_cnt += 1
        if not file_list:
            return
        map(self.cache_remove, file_list)
        console.info('scons cache purged')

    def get_file_list(self):
        if not self.cache_path:
            return []

        file_stat_list = [(x, os.stat(x)[6:8])
                for x in glob.glob(os.path.join(self.cache_path, '*', '*'))]
        if not file_stat_list:
            return []

        current_time = time.time()
        file_stat_list = [(x[0], x[1][0],
            x[1][0] * math.exp(self.exponent_scale * (x[1][1] - current_time)))
            for x in file_stat_list]

        file_stat_list.sort(key=lambda x: x[2], reverse=True)

        total_sz, start_index = 0, None
        for i, x in enumerate(file_stat_list):
            total_sz += x[1]
            if total_sz >= self.cache_limit:
                start_index = i
                break

        if not start_index:
            return []
        else:
            return [x[0] for x in file_stat_list[start_index:]]
