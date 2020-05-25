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

from __future__ import absolute_import
from __future__ import print_function

import fcntl
import os
import json
import sys
import string
import signal
import subprocess

from blade import console

try:
    import hashlib as md5
except ImportError:
    import md5


_IN_PY3 = sys.version_info[0] == 3


def md5sum_bytes(content):
    """Calculate md5sum of a byte string."""
    assert isinstance(content, bytes), 'Invalid type %s' % type(content)
    m = md5.md5()
    m.update(content)
    return m.hexdigest()


def md5sum_str(content):
    """Calculate md5sum of a string."""
    assert isinstance(content, str), 'Invalid type %s' % type(content)
    return md5sum_bytes(content.encode('utf-8'))


def md5sum_file(file_name):
    """Calculate md5sum of a file. """
    with open(file_name, 'rb') as f:
        digest = md5sum_bytes(f.read())
    return digest


def md5sum(obj):
    """Calculate md5sum of a string-like object"""
    if isinstance(obj, bytes):
        return md5sum_bytes(obj)
    elif isinstance(obj, str):
        return md5sum_str(obj)
    assert False, 'Invalid type %s' % type(str)


def lock_file(filename):
    """lock file. """
    try:
        fd = os.open(filename, os.O_CREAT | os.O_RDWR)
        old_fd_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        fcntl.fcntl(fd, fcntl.F_SETFD, old_fd_flags | fcntl.FD_CLOEXEC)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd, 0
    except IOError as ex_value:
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


def to_string(text):
    if text is None:
        return text
    if isinstance(text, str):
        return text
    if isinstance(text, bytes):
        return text.decode('utf-8')
    assert False, 'Unknown type %s' % type(text)


def get_cwd():
    """get_cwd

    os.getcwd() doesn't work because it will follow symbol link.
    os.environ.get('PWD') doesn't work because it won't reflect os.chdir().
    So in practice we simply use system('pwd') to get current working directory.

    """
    p = subprocess.Popen(['pwd'], stdout=subprocess.PIPE, shell=True)
    return to_string(p.communicate()[0].strip())


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


_TRANS_TABLE = (str if _IN_PY3 else string).maketrans(',-/.+*', '______')


def regular_variable_name(name):
    """convert some name to a valid identifier name"""
    return name.translate(_TRANS_TABLE)

if _IN_PY3:
    def iteritems(d, **kw):
        return iter(d.items(**kw))
else:
    def iteritems(d, **kw):
        return d.iteritems(**kw)


def exec_(filename, globals, locals):
    exec(compile(open(filename, "rb").read(), filename, 'exec'), globals, locals)
