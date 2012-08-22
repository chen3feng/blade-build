"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Huan Yu <huanyu@tencent.com>
         Feng chen <phongchen@tencent.com>
         Yi Wang <yiwang@tencent.com>
         Chong peng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the util module which provides command functions.

"""

import fcntl
import hashlib
import os
import sys
import subprocess


# Global color enabled or not
color_enabled = False


# file chunk size
chunk_size = 8192


class BladeFile(object):
    """BladeFile object which is used to wrap the file and caculate md5 etc. """
    def __init__(self, file_path):
        """BladeFile init method. """
        self.file_path = file_path
        self.file_object = None

    def get_file_path(self):
        """Returns file path. """
        return self.file_path

    def get_file_object(self):
        """Returns file object. """
        try:
            self.file_object = file(self.file_path, "rb")
            return self.file_object
        except:
            return None

    def close_file_object(self):
        """close the file object. """
        try:
            if self.file_object:
                self.file_object.close()
        except:
            pass


def md5sum_file(blade_file):
    """md5sum of one file. """
    if not isinstance(blade_file, BladeFile):
        error_exit("not a blade type of file to caculate md5")
    m = hashlib.md5()
    f = blade_file.get_file_object()
    if not f:
        error_exit("failed to open a file to caculate md5")
    global chunk_size
    while True:
        d = f.read(chunk_size)
        if not d:
            break
        m.update(d)
    blade_file.close_file_object()
    return m.hexdigest()


def md5sum_str(user_str):
    """md5sum of basestring. """
    m = hashlib.md5()
    if not isinstance(user_str, basestring):
        error_exit("not a valid basestring type to caculate md5")
    m.update(user_str)
    return m.hexdigest()


def md5sum(obj):
    """caculate md5sum and returns it. """
    if isinstance(obj, BladeFile):
        return md5sum_file(obj)
    elif isinstance(obj, basestring):
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


def error(msg, code = 1):
    """dump error message. """
    global color_enabled
    msg = "Blade(error): " + msg
    if color_enabled:
        msg = '\033[1;31m' + msg + '\033[0m'
    print >>sys.stderr, msg


def error_exit(msg, code = 1):
    """dump error message and exit. """
    error(msg)
    sys.exit(code)


def warning(msg):
    """dump warning message but continue. """
    global color_enabled
    msg = "Blade(warning): " + msg
    if color_enabled:
        msg = '\033[1;33m' + msg + '\033[0m'
    print >>sys.stderr, msg


def info_str(msg):
    """wrap str with color or not """
    global color_enabled
    msg = "Blade(info): " + msg
    if color_enabled:
        msg = '\033[1;36m' + msg + '\033[0m'
    return msg


def info(msg):
    """dump info message. """
    print >>sys.stderr, info_str(msg)


def var_to_list(var):
    """change the var to be a list. """
    if isinstance(var, list):
        return var
    return [var]

def relative_path(a_path, reference_path):
    """_relative_path.

    Get the relative path of a_path by considering reference_path as the
    root directory.  For example, if
    reference_path = "/src/paralgo"
    a_path        = "/src/paralgo/mapreduce_lite/sorted_buffer"
    then
     _relative_path(a_path, reference_path) = "mapreduce_lite/sorted_buffer"

    """
    if not a_path:
        raise ValueError("no path specified")

    # Count the number of segments shared by reference_path and a_path.
    reference_list = os.path.abspath(reference_path).split(os.path.sep)
    path_list  = os.path.abspath(a_path).split(os.path.sep)
    for i in range(min(len(reference_list), len(path_list))):
        # TODO(yiwang): Why use lower here?
        if reference_list[i].lower() != path_list[i].lower():
            break
        else:
            # TODO(yiwnag): Why do not move i+=1 out from the loop?
            i += 1

    rel_list = [os.path.pardir] * (len(reference_list)-i) + path_list[i:]
    if not rel_list:
        return os.path.curdir
    return os.path.join(*rel_list)


def get_cwd():
    """get_cwd

    os.getcwd() doesn't work because it will follow symbol link.
    os.environ.get("PWD") doesn't work because it won't reflect os.chdir().
    So in practice we simply use system('pwd') to get current working directory.

    """
    return subprocess.Popen(["pwd"], stdout = subprocess.PIPE, shell = True).communicate()[0].strip()
