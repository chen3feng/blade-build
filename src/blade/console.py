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

import os
import sys


# Global color enabled or not
color_enabled = (sys.stdout.isatty() and
                 os.environ['TERM'] not in ('emacs', 'dumb'))


def error(msg):
    """dump error message. """
    msg = "Blade(error): " + msg
    if color_enabled:
        msg = '\033[1;31m' + msg + '\033[0m'
    print >>sys.stderr, msg


def error_exit(msg, code=1):
    """dump error message and exit. """
    error(msg)
    sys.exit(code)


def warning(msg):
    """dump warning message but continue. """
    msg = "Blade(warning): " + msg
    if color_enabled:
        msg = '\033[1;33m' + msg + '\033[0m'
    print >>sys.stderr, msg


def info(msg, prefix=True):
    """dump info message. """
    if prefix:
        msg = "Blade(info): " + msg
    if color_enabled:
        msg = '\033[1;36m' + msg + '\033[0m'
    print >>sys.stderr, msg
