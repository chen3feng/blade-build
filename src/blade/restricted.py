# Copyright (c) 2021 Tencent Inc.
# All rights reserved.
#
# Author: chen3feng <chen3feng@gmail.com>
# Date:   2021-03-04

import sys

from blade import console
from blade import util

_IS_PY2 = sys.version_info.major == 2

if _IS_PY2:
    # pylint: disable=import-error
    # pyright: reportMissingImports=false
    import __builtin__ as builtins
else:
    # Do not attempt to use this package on Python2.7 as there
    # might be backports for this package such as future.
    import builtins

_SAFE_NAMES = [
    'None',
    'False',
    'True',
    'abs',
    'all',
    'any',
    'bool',
    'bytes',
    'callable',
    'chr',
    'complex',
    'dict',
    'divmod',
    'enumerate',
    'float',
    'hash',
    'hex',
    'id',
    'int',
    'isinstance',
    'issubclass',
    'len',
    'list',
    'oct',
    'ord',
    'pow',
    'range',
    'repr',
    'round',
    'set',
    'slice',
    'sorted',
    'str',
    'tuple',
    'zip'
]

_SAFE_EXCEPTIONS = [
    'ArithmeticError',
    'AssertionError',
    'AttributeError',
    'BaseException',
    'BufferError',
    'BytesWarning',
    'DeprecationWarning',
    'EOFError',
    'EnvironmentError',
    'Exception',
    'FloatingPointError',
    'FutureWarning',
    'GeneratorExit',
    'IOError',
    'ImportError',
    'ImportWarning',
    'IndentationError',
    'IndexError',
    'KeyError',
    'KeyboardInterrupt',
    'LookupError',
    'MemoryError',
    'NameError',
    'NotImplementedError',
    'OSError',
    'OverflowError',
    'PendingDeprecationWarning',
    'ReferenceError',
    'RuntimeError',
    'RuntimeWarning',
    'StopIteration',
    'SyntaxError',
    'SyntaxWarning',
    'SystemError',
    'SystemExit',
    'TabError',
    'TypeError',
    'UnboundLocalError',
    'UnicodeDecodeError',
    'UnicodeEncodeError',
    'UnicodeError',
    'UnicodeTranslateError',
    'UnicodeWarning',
    'UserWarning',
    'ValueError',
    'Warning',
    'ZeroDivisionError',
]

if _IS_PY2:
    _SAFE_NAMES.extend([
        'basestring',
        'cmp',
        'long',
        'unichr',
        'unicode',
        'xrange',
    ])
    _SAFE_EXCEPTIONS.extend([
        'StandardError',
    ])
else:
    _SAFE_NAMES.extend([
        '__build_class__',  # needed to define new classes
    ])


# Replace some functions to better help users know how to deal with.
_FORBIDDEN_FUNCTIONS = [
    ('__import__', 'import'),
    'exec',
    'execfile',
    'eval',
    'open',
]


def _make_forbidden_wrapper(name):
    def wrapper(*args, **kwargs):
        src_loc = util.calling_source_location(1)  # Skip the `wrapper` function
        error = '"%s" is forbidden in blade, please use the builtin `blade` module' % name
        console.diagnose(src_loc, 'error', error)
        # return None  # pylint: disable=useless-return
    return wrapper


def _make_safe_buildins():
    safe_builtins = {}

    for name in _SAFE_NAMES:
        safe_builtins[name] = getattr(builtins, name)

    for name in _SAFE_EXCEPTIONS:
        safe_builtins[name] = getattr(builtins, name)

    for name in _FORBIDDEN_FUNCTIONS:
        if isinstance(name, tuple):
            name, user_friend_name = name
        else:
            user_friend_name = name
        safe_builtins[name] = _make_forbidden_wrapper(user_friend_name)

    return safe_builtins


safe_builtins = _make_safe_buildins()
