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


# Global log file for detailed output during build
_log = None


# Output verbosity control, valid values:
# verbose: verbose mode, show more details
# normal: normal mode, show infos, warnings and errors
# quiet: quiet mode, only show warnings and errors
_VERBOSITIES = ('quiet', 'normal', 'verbose')


_verbosity = 'normal'


# Global color enabled or not
color_enabled = (sys.stdout.isatty() and
                 os.environ.get('TERM') not in ('emacs', 'dumb'))


# See http://en.wikipedia.org/wiki/ANSI_escape_code
# colors
_colors = {}
_colors['red']    = '\033[1;31m'
_colors['green']  = '\033[1;32m'
_colors['yellow'] = '\033[1;33m'
_colors['blue']   = '\033[1;34m'
_colors['purple'] = '\033[1;35m'
_colors['cyan']   = '\033[1;36m'
_colors['white']  = '\033[1;37m'
_colors['gray']   = '\033[1;38m'
_colors['dimpurple'] = '\033[2;35m'
_colors['end']    = '\033[0m'

# cursor movement
_CLEAR_LINE = '\033[2K'
_CURSUR_UP = '\033[A'


def set_log_file(log_file):
    """Set the global log file. """
    global _log
    _log = open(log_file, 'w', 1)


def get_log_file():
    """Return the global log file name. """
    return _log.name


def set_verbosity(value):
    """Set the global verbosity. """
    global _verbosity
    assert value in _VERBOSITIES
    _verbosity = value


def get_verbosity():
    return _verbosity


def verbosity_compare(lhs, rhs):
    """Return -1, 0, 1 according to their order"""
    a = _VERBOSITIES.index(lhs)
    b = _VERBOSITIES.index(rhs)
    return (a > b) - (a < b)


def verbosity_le(verbosity):
    """verbosity less than or equal"""
    return verbosity_compare(lhs, rhs) <= 0


def verbosity_ge(lhs, rhs):
    """verbosity greater than or equal"""
    return verbosity_compare(lhs, rhs) >= 0


def inerasable(msg):
    """Make msg clear line when output"""
    if color_enabled:
        return _CLEAR_LINE + msg
    return msg


def erasable(msg):
    """Make msg not cause new line when output"""
    if color_enabled:
        return _CLEAR_LINE + msg + _CURSUR_UP
    return msg


def colors(name):
    """Return ansi console control sequence from color name"""
    if color_enabled:
        return _colors[name]
    return ''


def _print(msg, verbosity):
    if verbosity_ge(_verbosity, verbosity):
        print msg


def error(msg, prefix=True):
    """dump error message. """
    if prefix:
        msg = 'Blade(error): ' + msg
    log(msg)
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
    log(msg)
    if color_enabled:
        msg = _colors['yellow'] + msg + _colors['end']
    print >>sys.stderr, msg


def info(msg, prefix=True):
    """dump info message. """
    if prefix:
        msg = 'Blade(info): ' + msg
    log(msg)
    if color_enabled:
        msg = _colors['cyan'] + msg + _colors['end']
    _print(msg, 'normal')


def debug(msg, prefix=True):
    """dump debug message. """
    if prefix:
        msg = 'Blade(debug): ' + msg
    log(msg)
    _print(msg, 'verbose')


def log(msg):
    """Dump message into log file. """
    if _log:
        print >>_log, msg


def flush():
    sys.stdout.flush()
    sys.stderr.flush()
    if _log:
        _log.flush()

