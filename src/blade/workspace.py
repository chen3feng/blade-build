# Copyright (c) 2021 Tencent Inc.
# All rights reserved.
#
# Author: chen3feng <chen3feng@gmail.com>
# Date:   Feb 12, 2013

"""The workspace module represent current workspace."""

import errno
import json
import os
import re
import subprocess
from string import Template

from blade import config
from blade import console

from blade.blade_util import find_blade_root_dir
from blade.blade_util import get_cwd, to_string
from blade.blade_util import lock_file, unlock_file


def _generate_scm_svn():
    url = revision = 'unknown'
    p = subprocess.Popen('svn info', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    stdout = to_string(stdout)
    stderr = to_string(stderr)
    if p.returncode != 0:
        console.debug('Failed to generate svn scm: %s' % stderr)
    else:
        for line in stdout.splitlines():
            if line.startswith('URL: '):
                url = line.strip().split()[-1]
            if line.startswith('Revision: '):
                revision = line.strip().split()[-1]
                break

    return url, revision


def _generate_scm_git():
    url = revision = 'unknown'

    def git(cmd):
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        stdout = to_string(stdout)
        stderr = to_string(stderr)
        if p.returncode != 0:
            console.debug('Failed to generate git scm: %s' % stderr)
            return ''
        return stdout

    out = git('git rev-parse HEAD')
    if out:
        revision = out.strip()
    out = git('git remote -v')
    # $ git remote -v
    # origin  https://github.com/chen3feng/blade-build.git (fetch)
    # origin  https://github.com/chen3feng/blade-build.git (push)
    if out:
        url = out.splitlines()[0].split()[1]
        # Remove userinfo (such as username and password) from url, if any.
        url = re.sub(r'(?<=://).*:.*@', '', url)
    return url, revision


def _generate_scm(build_dir):
    if os.path.isdir('.git'):
        url, revision = _generate_scm_git()
    elif os.path.isdir('.svn'):
        url, revision = _generate_scm_svn()
    else:
        console.debug('Unknown scm.')
        return
    path = os.path.join(build_dir, 'scm.json')
    with open(path, 'w') as f:
        json.dump({
            'revision': revision,
            'url': url,
        }, f)


class Workspace(object):
    """Workspace represent a dir tree rooted from the dir where the BLADE_ROOT residents."""
    def __init__(self, options):
        self.__options = options
        working_dir = get_cwd()
        self.__root_dir = find_blade_root_dir(working_dir)
        self.__working_dir = os.path.relpath(working_dir, self.__root_dir)
        self.__build_dir = ''

    def root_dir(self):
        return self.__root_dir

    def build_dir(self):
        return self.__build_dir

    def working_dir(self):
        return self.__working_dir

    def switch_to_root_dir(self):
        """Switch current dir to root dir of workspace."""
        if self.__root_dir != self.__working_dir:
            # This message is required by vim quickfix mode if pwd is changed during
            # the building, DO NOT change the pattern of this message.
            if self.__options.verbosity != 'quiet':
                print("Blade: Entering directory `%s'" % self.__root_dir)
            os.chdir(self.__root_dir)

    def setup_build_dir(self):
        """Setup build dir."""
        build_path_format = config.get_item('global_config', 'build_path_template')
        s = Template(build_path_format)
        build_dir = s.substitute(bits=self.__options.bits, profile=self.__options.profile)

        if not os.path.exists(build_dir):
            os.mkdir(build_dir)
        try:
            os.remove('blade-bin')
        except os.error:
            pass
        os.symlink(os.path.abspath(build_dir), 'blade-bin')

        log_file = os.path.join(build_dir, 'blade.log')
        console.set_log_file(log_file)
        _generate_scm(build_dir)

        self.__build_dir = build_dir
        return build_dir

    def lock(self):
        """Lock current workspace."""
        _BUILDING_LOCK_FILE = '.blade.building.lock'
        lock_file_fd, ret_code = lock_file(os.path.join(self.__build_dir, _BUILDING_LOCK_FILE))
        if lock_file_fd == -1:
            if ret_code == errno.EAGAIN:
                console.fatal('There is already an active building in current workspace.')
            else:
                console.fatal('Lock exception, please try it later.')
        return lock_file_fd

    def unlock(self, lock_id):
        """Unlock current workspace."""
        unlock_file(lock_id)


__instance = None


def initialize(options):
    global __instance
    assert __instance is None
    __instance = Workspace(options)
    return __instance
