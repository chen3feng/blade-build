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
import re
import string
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


def lock_file(fd, flags):
    """lock file. """
    try:
        fcntl.flock(fd, flags)
        return (True, 0)
    except IOError, ex_value:
        return (False, ex_value[0])


def unlock_file(fd):
    """unlock file. """
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return (True, 0)
    except IOError, ex_value:
        return (False, ex_value[0])


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


def relative_path(a_path, reference_path):
    """_relative_path.

    Get the relative path of a_path by considering reference_path as the
    root directory.  For example, if
    reference_path = '/src/paralgo'
    a_path        = '/src/paralgo/mapreduce_lite/sorted_buffer'
    then
     _relative_path(a_path, reference_path) = 'mapreduce_lite/sorted_buffer'

    """
    if not a_path:
        raise ValueError('no path specified')

    # Count the number of segments shared by reference_path and a_path.
    reference_list = os.path.abspath(reference_path).split(os.path.sep)
    path_list = os.path.abspath(a_path).split(os.path.sep)
    i = 0
    for i in range(min(len(reference_list), len(path_list))):
        # TODO(yiwang): Why use lower here?
        if reference_list[i].lower() != path_list[i].lower():
            break
        else:
            # TODO(yiwnag): Why do not move i+=1 out from the loop?
            i += 1

    rel_list = [os.path.pardir] * (len(reference_list) - i) + path_list[i:]
    if not rel_list:
        return os.path.curdir
    return os.path.join(*rel_list)


def get_cwd():
    """get_cwd

    os.getcwd() doesn't work because it will follow symbol link.
    os.environ.get('PWD') doesn't work because it won't reflect os.chdir().
    So in practice we simply use system('pwd') to get current working directory.

    """
    p = subprocess.Popen(['pwd'], stdout=subprocess.PIPE, shell=True)
    return p.communicate()[0].strip()


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
