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

from __future__ import print_function

import os
import sys


##############################################################################
# Color and screen
##############################################################################


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


def color(name):
    """Return ansi console control sequence from color name"""
    if color_enabled:
        return _COLORS[name]
    return ''


def colored(text, color):
    """Return ansi color code enclosed text"""
    if color_enabled:
        return _COLORS[color] + text + _COLORS['end']
    return text


##############################################################################
# Log
##############################################################################


# Global log file for detailed output during build
_log = None


def set_log_file(log_file):
    """Set the global log file. """
    global _log
    _log = open(log_file, 'w', 1)


def get_log_file():
    """Return the global log file name. """
    return _log.name


def log(msg):
    """Dump message into log file. """
    if _log:
        print(msg, file=_log)


##############################################################################
# Verbosity
##############################################################################


# Output verbosity control, valid values:
# verbose: verbose mode, show more details
# normal: normal mode, show infos, warnings and errors
# quiet: quiet mode, only show warnings and errors
_VERBOSITIES = ('quiet', 'normal', 'verbose')


_verbosity = 'normal'


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


##############################################################################
# Progress bar
##############################################################################

# Fit with the 80 columns terminal, leave some spaces for other parts such as the numbers.
_PROGRESS_BAR_WIDTH = 65

# TODO(chen3feng): Add lock
_need_clear_line = False  # Whether the last output is progress bar
_last_progress = -1  # The last progress bar value, -1 means none


def _progress_bar(progress, current, total):
    """Progress bar drawing text, like this:
    [============================================================-----] 46/50
    """
    width = progress * _PROGRESS_BAR_WIDTH // 100
    return '[%s%s] %s/%s' % ('=' * width, '-' * (_PROGRESS_BAR_WIDTH - width), current, total)


def show_progress_bar(current, total):
    global _need_clear_line, _last_progress
    progress = current * 100 // total
    if progress != _last_progress:
        bar = _progress_bar(progress, current, total)
        bar += '\r' if color_enabled else '\n'
        print(bar, end='')
        _last_progress = progress
        _need_clear_line = True


def clear_progress_bar():
    global _need_clear_line, _last_progress
    if _need_clear_line:
        if color_enabled:
            print(_CLEAR_LINE, end='')
        _need_clear_line = False
        _last_progress = -1
        sys.stdout.flush()


##############################################################################
# Output
##############################################################################


def _do_print(msg, file=sys.stdout):
    clear_progress_bar()
    print(msg, file=file)


def _print(msg, verbosity):
    if verbosity_ge(verbosity):
        _do_print(msg)


def output(msg):
    """Output message without any decoration"""
    _do_print(msg)
    log(msg)


def error(msg, prefix=True):
    """dump error message. """
    if prefix:
        msg = 'Blade(error): ' + msg
    log(msg)
    _do_print(colored(msg, 'red'), file=sys.stderr)


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
    _do_print(msg, file=sys.stderr)


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


def flush():
    sys.stdout.flush()
    sys.stderr.flush()
    if _log:
        _log.flush()

