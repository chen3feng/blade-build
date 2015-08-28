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


import os
import sys


# Global color enabled or not
color_enabled = (sys.stdout.isatty() and
                 os.environ['TERM'] not in ('emacs', 'dumb'))


# _colors
_colors = {}
_colors['red']    = '\033[1;31m'
_colors['green']  = '\033[1;32m'
_colors['yellow'] = '\033[1;33m'
_colors['blue']   = '\033[1;34m'
_colors['purple'] = '\033[1;35m'
_colors['cyan']   = '\033[1;36m'
_colors['white']  = '\033[1;37m'
_colors['gray']   = '\033[1;38m'
_colors['end']    = '\033[0m'


_CLEAR_LINE = '\033[2K'
_CURSUR_UP = '\033[A'


def inerasable(msg):
    """Make msg clear line when output"""
    if color_enabled:
        return _CLEAR_LINE + msg
    return msg


def erasable(msg):
    """Make msg does't cause new line when output"""
    if color_enabled:
        return _CLEAR_LINE + msg + _CURSUR_UP
    return msg


def colors(name):
    """Return ansi console control sequence from color name"""
    if color_enabled:
        return _colors[name]
    return ''


def error(msg):
    """dump error message. """
    msg = 'Blade(error): ' + msg
    if color_enabled:
        msg = _colors['red'] + msg + _colors['end']
    print >>sys.stderr, msg


def error_exit(msg, code=1):
    """dump error message and exit. """
    error(msg)
    sys.exit(code)


def warning(msg):
    """dump warning message but continue. """
    msg = 'Blade(warning): ' + msg
    if color_enabled:
        msg = _colors['yellow'] + msg + _colors['end']
    print >>sys.stderr, msg


def info(msg, prefix=True):
    """dump info message. """
    if prefix:
        msg = 'Blade(info): ' + msg
    if color_enabled:
        msg = _colors['cyan'] + msg + _colors['end']
    print >>sys.stderr, msg

