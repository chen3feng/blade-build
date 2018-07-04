# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Huan Yu <huanyu@tencent.com>
#         Feng chen <phongchen@tencent.com>
#         Yi Wang <yiwang@tencent.com>
#         Chong peng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the util module which provides command functions.

"""

import fcntl
import os
import json
import sys
import re
import string
import signal
import subprocess

import console


try:
    import hashlib as md5
except ImportError:
    import md5


location_re = re.compile(r'\$\(location\s+(\S*:\S+)(\s+\w*)?\)')


def md5sum_str(user_str):
    """md5sum of basestring. """
    if not isinstance(user_str, basestring):
        console.error_exit('Not a valid basestring type to calculate md5.')
    m = md5.md5()
    m.update(user_str)
    return m.hexdigest()


def md5sum_file(file_name):
    """Calculate md5sum of the file. """
    f = open(file_name)
    digest = md5sum_str(f.read())
    f.close()
    return digest


def md5sum(obj):
    """Calculate md5sum and returns it. """
    return md5sum_str(obj)


def lock_file(filename):
    """lock file. """
    try:
        fd = os.open(filename, os.O_CREAT|os.O_RDWR)
        old_fd_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        fcntl.fcntl(fd, fcntl.F_SETFD, old_fd_flags | fcntl.FD_CLOEXEC)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd, 0
    except IOError, ex_value:
        return -1, ex_value[0]


def unlock_file(fd):
    """unlock file. """
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except IOError:
        pass


def var_to_list(var):
    """change the var to be a list. """
    if isinstance(var, list):
        return var
    if not var:
        return []
    return [var]


def stable_unique(seq):
    """unique a seq and keep its original order"""
    # See http://stackoverflow.com/questions/480214/how-do-you-remove-duplicates-from-a-list-in-python-whilst-preserving-order
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


def get_cwd():
    """get_cwd

    os.getcwd() doesn't work because it will follow symbol link.
    os.environ.get('PWD') doesn't work because it won't reflect os.chdir().
    So in practice we simply use system('pwd') to get current working directory.

    """
    p = subprocess.Popen(['pwd'], stdout=subprocess.PIPE, shell=True)
    return p.communicate()[0].strip()


def find_file_bottom_up(name, from_dir=None):
    """Find the specified file/dir from from_dir bottom up until found or failed.
       Returns abspath if found, or empty if failed.
    """
    if from_dir is None:
        from_dir = get_cwd()
    finding_dir = os.path.abspath(from_dir)
    while True:
        path = os.path.join(finding_dir, name)
        if os.path.exists(path):
            return path
        if finding_dir == '/':
            break
        finding_dir = os.path.dirname(finding_dir)
    return ''


def find_blade_root_dir(working_dir=None):
    """find_blade_root_dir to find the dir holds the BLADE_ROOT file.

    The blade_root_dir is the directory which is the closest upper level
    directory of the current working directory, and containing a file
    named BLADE_ROOT.

    """
    blade_root = find_file_bottom_up('BLADE_ROOT', from_dir=working_dir)
    if not blade_root:
        console.error_exit(
                "Can't find the file 'BLADE_ROOT' in this or any upper directory.\n"
                "Blade need this file as a placeholder to locate the root source directory "
                "(aka the directory where you #include start from).\n"
                "You should create it manually at the first time.")
    return os.path.dirname(blade_root)


if "check_output" not in dir( subprocess ):
    def check_output(*popenargs, **kwargs):
        r"""Run command with arguments and return its output as a byte string.

        Backported from Python 2.7 as it's implemented as pure python on stdlib.

        >>> check_output(["ls", "-l", "/dev/null"])
        'crw-rw-rw- 1 root root 1, 3 Oct 18  2007 /dev/null\n'

        """
        process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            error = subprocess.CalledProcessError(retcode, cmd)
            error.output = output
            raise error
        return output


def _echo(stdout, stderr):
    """Echo messages to stdout and stderr. """
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)


def shell(cmd, env=None):
    if isinstance(cmd, list):
        cmdline = ' '.join(cmd)
    else:
        cmdline = cmd
    p = subprocess.Popen(cmdline,
                         env=env,
                         stderr=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         shell=True)
    stdout, stderr = p.communicate()
    if p.returncode:
        if p.returncode != -signal.SIGINT:
            # Error
            _echo(stdout, stderr)
    else:
        # Warnings
        _echo(stdout, stderr)

    return p.returncode


def load_scm(build_dir):
    revision = url = 'unknown'
    path = os.path.join(build_dir, 'scm.json')
    if os.path.exists(path):
        with open(path) as f:
            scm = json.load(f)
            revision, url = scm['revision'], scm['url']
    return revision, url


def environ_add_path(env, key, path):
    """Add path to PATH link environments, such as PATH, LD_LIBRARY_PATH, etc"""
    old = env.get(key)
    if old:
        env[key] = path + ':' + old
    else:
        env[key] = path


def cpu_count():
    try:
        import multiprocessing
        return multiprocessing.cpu_count()
    except ImportError:
        return int(os.sysconf('SC_NPROCESSORS_ONLN'))


def regular_variable_name(var):
    """regular_variable_name.

    Parameters
    -----------
    var: the variable to be modified

    Returns
    -----------
    s: the variable modified

    Description
    -----------
    Replace the chars that scons doesn't regconize.

    """
    return var.translate(string.maketrans(',-/.+*', '______'))
