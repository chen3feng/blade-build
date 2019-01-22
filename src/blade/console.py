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

# pylint: disable=bad-whitespace
_COLORS = {
    'red'    : '\033[1;31m',
    'green'  : '\033[1;32m',
    'yellow' : '\033[1;33m',
    'blue'   : '\033[1;34m',
    'purple' : '\033[1;35m',
    'cyan'   : '\033[1;36m',
    'white'  : '\033[1;37m',
    'gray'   : '\033[1;38m',
    'dimpurple' : '\033[2;35m',
    'end'    :  '\033[0m',
}

# cursor movement
_CLEAR_LINE = '\033[2K'
_CURSUR_UP = '\033[A'


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
    # TODO(chen3feng): rename it to `color`
    if color_enabled:
        return _COLORS[name]
    return ''


def colored(text, color):
    """Return ansi console control sequence from color name"""
    if color_enabled:
        return _COLORS[color] + text + _COLORS['end']
    return text


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


def verbosity_le(expected):
    """Current verbosity less than or equal to expected"""
    return verbosity_compare(_verbosity, expected) <= 0


def verbosity_ge(expected):
    """Current verbosity greater than or equal to expected"""
    return verbosity_compare(_verbosity, expected) >= 0


def _print(msg, verbosity):
    if verbosity_ge(verbosity):
        print msg


def error(msg, prefix=True):
    """dump error message. """
    if prefix:
        msg = 'Blade(error): ' + msg
    log(msg)
    print >>sys.stderr, colored(msg, 'red')


def error_exit(msg, code=1):
    """dump error message and exit. """
    error(msg)
    sys.exit(code)


def warning(msg, prefix=True):
    """dump warning message. """
    if prefix:
        msg = 'Blade(warning): ' + msg
    log(msg)
    msg = colored(msg, 'yellow')
    print >>sys.stderr, msg


def notice(msg, prefix=True):
    """dump notable message which is not a warning or error,
       visible in quiet mode"""
    if prefix:
        msg = 'Blade(notice): ' + msg
    log(msg)
    _print(colored(msg, 'blue'), 'quiet')


def info(msg, prefix=True):
    """dump info message. """
    if prefix:
        msg = 'Blade(info): ' + msg
    log(msg)
    _print(colored(msg, 'cyan'), 'normal')


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
