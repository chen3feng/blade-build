# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""
 Manage symbols can be used in BUILD files.
"""


__build_globals = {}


def register_build_global(name, value):
    """Register a variable that accessiable in BUILD file """
    __build_globals[name] = value


def register_build_function(f):
    """Register a function as a build function that callable in BUILD file """
    register_build_global(f.__name__, f)


def get_all():
    """Get the globals dict"""
    return __build_globals
