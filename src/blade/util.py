# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Huan Yu <huanyu@tencent.com>
#         Feng chen <phongchen@tencent.com>
#         Yi Wang <yiwang@tencent.com>
#         Chong peng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
This is the util module which provides some helper functions.
"""

from __future__ import absolute_import
from __future__ import print_function

import ast
import errno
import fcntl
import hashlib
import inspect
import json
import os
import signal
import string
import subprocess
import sys


_IN_PY3 = sys.version_info[0] == 3

# In python 2, cPickle is much faster than pickle, but in python 3, pickle is
# reimplemented in C extension and then the standardalone cPickle is removed.
if _IN_PY3:
    import pickle  # pylint: disable=unused-import
else:
    import cPickle as pickle  # pylint: disable=import-error, unused-import


def md5sum_bytes(content):
    """Calculate md5sum of a byte string."""
    assert isinstance(content, bytes), 'Invalid type %s' % type(content)
    m = hashlib.md5()
    m.update(content)
    return m.hexdigest()


def md5sum_str(content):
    """Calculate md5sum of a string."""
    assert isinstance(content, str), 'Invalid type %s' % type(content)
    return md5sum_bytes(content.encode('utf-8'))


def md5sum_file(file_name):
    """Calculate md5sum of a file."""
    with open(file_name, 'rb') as f:
        digest = md5sum_bytes(f.read())
    return digest


def md5sum(obj):
    """Calculate md5sum of a string-like object"""
    if isinstance(obj, bytes):
        return md5sum_bytes(obj)
    if isinstance(obj, str):
        return md5sum_str(obj)
    raise TypeError('Invalid type %s' % type(str))


def lock_file(filename):
    """lock file."""
    try:
        fd = os.open(filename, os.O_CREAT | os.O_RDWR)
        old_fd_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        fcntl.fcntl(fd, fcntl.F_SETFD, old_fd_flags | fcntl.FD_CLOEXEC)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd, 0
    except IOError as ex_value:
        return -1, ex_value.errno


def unlock_file(fd):
    """unlock file."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except IOError:
        pass


def var_to_list(var):
    """Normalize a singlar or list to list."""
    if isinstance(var, list):
        return var[:]
    if var is None:
        return []
    return [var]


def var_to_list_or_none(var):
    """Similar to var_to_list but keeps the None unchanged"""
    if var is None:
        return var
    return var_to_list(var)


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
    raise TypeError('Unknown type %s' % type(text))


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


def path_under_dir(path, dir):
    """Check whether path is under dir."""
    return path == dir or path.startswith(dir) and path[len(dir)] == os.path.sep


def mkdir_p(path):
    """Make directory if it does not exist."""
    try:
        if not os.path.isdir(path):
            os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def _echo(stdout, stderr):
    """Echo messages to stdout and stderr."""
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
        import multiprocessing  # pylint: disable=import-outside-toplevel
        return multiprocessing.cpu_count()
    except ImportError:
        return int(os.sysconf('SC_NPROCESSORS_ONLN'))


_TRANS_TABLE = (str if _IN_PY3 else string).maketrans(',-/:.+*', '_______')


def regular_variable_name(name):
    """convert some name to a valid identifier name"""
    return name.translate(_TRANS_TABLE)


if _IN_PY3:
    def iteritems(d, **kw):
        return iter(d.items(**kw))
else:
    def iteritems(d, **kw):
        return d.iteritems(**kw)


def exec_file_content(filename, content, globals, locals):
    """Execute code content as filename"""
    # pylint: disable=exec-used
    exec(compile(content, filename, 'exec'), globals, locals)


def exec_file(filename, globals, locals):
    """Same as python2's execfile builtin function, but python3 has no execfile"""
    # pylint: disable=exec-used
    with open(filename, 'rb') as f:
        exec_file_content(filename, f.read(), globals, locals)


def eval_file(filepath):
    """Load a value from file.

    Safely evaluate an expression node or a string containing a Python literal or container display.
    The string or node provided may only consist of the following Python literal structures:
    strings, bytes, numbers, tuples, lists, dicts, sets, booleans, and None.
    """
    return ast.literal_eval(open(filepath).read())


def source_location(filename):
    """Return source location of current call stack from filename"""
    lineno = 1

    # See https://stackoverflow.com/questions/17407119/python-inspect-stack-is-slow
    frame = inspect.currentframe()
    while frame:
        if frame.f_code.co_filename.endswith(filename):
            lineno = frame.f_lineno
            break
        frame = frame.f_back
    return '%s:%s' % (filename, lineno)


def parse_command_line(argv):
    """Simple command line parsing.

    options can only be passed as the form of `--name=value`, any other arguments are treated as
    normal arguments.

    Returns:
        tuple(options: dict, args: list)
    """
    options = {}
    args = []
    for arg in argv:
        if arg.startswith('--'):
            pos = arg.find('=')
            if pos < 0:
                args.append(arg)
                continue
            name = arg[2:pos]
            value = arg[pos+1:]
            options[name] = value
        else:
            args.append(arg)
    return options, args
