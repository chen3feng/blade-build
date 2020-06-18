# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Huan Yu <huanyu@tencent.com>
#         Feng Chen <phongchen@tencent.com>
#         Yi Wang <yiwang@tencent.com>
#         Chong Peng <michaelpeng@tencent.com>
#         Wenting Li <wentingli@tencent.com>
# Date:   October 20, 2011


"""
 This is the CmdOptions module which parses the users'
 input and provides hint for users.

"""

from __future__ import absolute_import

import os
import traceback

from blade import build_attributes
from blade import build_rules
from blade import console
from blade.blade_util import var_to_list, exec_
from blade.pathlib import Path


# import these modules make build functions registered into build_rules
# TODO(chen3feng): Load build modules dynamically to enable extension.


def _load_build_rules():
    # pylint: disable=W0611
    import blade.cc_targets
    import blade.cu_targets
    import blade.gen_rule_target
    import blade.go_targets
    import blade.java_targets
    import blade.scala_targets
    import blade.lex_yacc_target
    import blade.package_target
    import blade.proto_library_target
    import blade.py_targets
    import blade.resource_library_target
    import blade.sh_test_target
    import blade.swig_library_target
    import blade.thrift_library
    import blade.fbthrift_library


def _find_dir_depender(dir, blade):
    """Find which target depends on the dir. """
    target_database = blade.get_target_database()
    for key in target_database:
        target = target_database[key]
        for dkey in target.expanded_deps:
            if dkey[0] == dir:
                return '//%s' % target.fullname
    return None


def _report_not_exist(source_dir, path, blade):
    """Report dir or BUILD file does not exist. """
    depender = _find_dir_depender(source_dir, blade)
    if depender:
        console.error_exit('//%s not found, required by %s' % (path, depender))
    else:
        console.error_exit('//%s not found' % path)


def enable_if(cond, true_value, false_value=None):
    """A global function can be called in BUILD to filter srcs/deps by target"""
    if cond:
        ret = true_value
    else:
        ret = false_value
    if ret is None:
        ret = []
    return ret


def glob(include, exclude=None, excludes=None, allow_empty=False):
    """This function can be called in BUILD to specify a set of files using patterns.
    Args:
        include:List(str), file patterns to be matched.
        exclude:List[str], file patterns to be removed from the result.
        allow_empty:bool: Whether a empty result is a error.

    Patterns may contain shell-like wildcards, such as * , ? , or [charset].
    Additionally, the path element '**' matches any subpath.
    """
    from blade import build_manager
    source_dir = Path(build_manager.instance.get_current_source_path())

    include = var_to_list(include)
    if excludes:
        console.warning('//%s: "glob.excludes" is deprecated, use "exclude" instead' % source_dir)
    exclude = var_to_list(exclude) + var_to_list(excludes)

    def includes_iterator():
        results = []
        for pattern in include:
            for path in source_dir.glob(pattern):
                if path.is_file() and not path.name.startswith('.'):
                    results.append(path.relative_to(source_dir))

        return results

    def is_special(pattern):
        return '*' in pattern or '?' in pattern or '[' in pattern

    non_special_excludes = set()
    match_excludes = set()
    for pattern in exclude:
        if is_special(pattern):
            match_excludes.add(pattern)
        else:
            non_special_excludes.add(pattern)

    def exclusion(path):
        if str(path) in non_special_excludes:
            return True
        for pattern in match_excludes:
            ret = path.match(pattern)
            if ret:
                return True
        return False

    result = sorted(set([str(p) for p in includes_iterator() if not exclusion(p)]))
    if not result and not allow_empty:
        args = repr(include)
        if exclude:
            args += ', exclude=%s' % repr(exclude)
        console.warning('//%s: "glob(%s)" got an empty result. If it is the expected behavior, '
                        'specify "allow_empty=True" to eliminate this message' % (source_dir, args))

    return result


# Each include in a BUILD file can only affect itself
__current_globles = None


# Include a defination file in a BUILD file
def include(name):
    from blade import build_manager
    if name.startswith('//'):
        dir = build_manager.instance.get_root_dir()
        name = name[2:]
    else:
        dir = build_manager.instance.get_current_source_path()
    exec_(os.path.join(dir, name), __current_globles, None)


build_rules.register_function(enable_if)
build_rules.register_function(glob)
build_rules.register_function(include)


def _load_build_file(source_dir, processed_source_dirs, blade):
    """Load the BUILD and place the targets into database.

    Invoked by _load_targets.  Load and execute the BUILD
    file, which is a Python script, in source_dir.  Statements in BUILD
    depends on global variable current_source_dir, and will register build
    target/rules into global variables target_database.  Report error
    and exit if path/BUILD does NOT exist.
    The parameters processed_source_dirs refers to a set defined in the
    caller and used to avoid duplicated execution of BUILD files.

    """
    source_dir = os.path.normpath(source_dir)
    # TODO(yiwang): the character '#' is a magic value.
    if source_dir in processed_source_dirs or source_dir == '#':
        return
    processed_source_dirs.add(source_dir)

    if not os.path.exists(source_dir):
        _report_not_exist(source_dir, source_dir, blade)

    old_current_source_path = blade.get_current_source_path()
    blade.set_current_source_path(source_dir)
    build_file = os.path.join(source_dir, 'BUILD')
    if os.path.exists(build_file) and not os.path.isdir(build_file):
        try:
            # The magic here is that a BUILD file is a Python script,
            # which can be loaded and executed by execfile().
            global __current_globles
            __current_globles = build_rules.get_all()
            exec_(build_file, __current_globles, None)
        except SystemExit:
            console.error_exit('%s: Fatal error' % build_file)
        except:  # pylint: disable=bare-except
            console.error_exit('Parse error in %s\n%s' % (
                build_file, traceback.format_exc()))
    else:
        _report_not_exist(source_dir, build_file, blade)

    blade.set_current_source_path(old_current_source_path)


def _find_depender(dkey, blade):
    """Find which target depends on the target with dkey. """
    target_database = blade.get_target_database()
    for key in target_database:
        target = target_database[key]
        if dkey in target.expanded_deps:
            return '//%s' % target.fullname
    return None


# File names should be skipped
_SKIP_FILES = ['BLADE_ROOT', '.bladeskip']


def _is_load_excluded(root, d):
    """Whether exclude the directory when loading BUILD.
    """
    # TODO(wentingli): Exclude directories matching patterns configured globally

    # Exclude directories starting with '.', e.g. '.', '..', '.svn', '.git'.
    if d.startswith('.'):
        return True

    # Exclude build dirs
    for build_dir in ('build32_debug', 'build32_release',
                       'build64_debug', 'build64_release'):
        if d.startswith(build_dir):
            return True

    # Exclude directories containing special files
    for skip_file in _SKIP_FILES:
        if os.path.exists(os.path.join(root, d, skip_file)):
            console.info('Skip "%s"' % os.path.join(root, d))
            return True

    return False


def load_targets(target_ids, blade_root_dir, blade):
    """load_targets.

    Parse and load targets, including those specified in command line
    and their direct and indirect dependencies, by loading related BUILD
    files.  Returns a map which contains all these targets.

    """
    _load_build_rules()

    # pylint: disable=too-many-locals
    build_rules.register_variable('build_target', build_attributes.attributes)
    target_database = blade.get_target_database()

    # targets specified in command line
    cited_targets = set()
    # cited_targets and all its dependencies
    related_targets = {}
    # source dirs mentioned in command line
    source_dirs = []
    # to prevent duplicated loading of BUILD files
    processed_source_dirs = set()

    direct_targets = []
    all_command_targets = []
    # Parse command line target_ids.  For those in the form of <path>:<target>,
    # record (<path>,<target>) in cited_targets; for the rest (with <path>
    # but without <target>), record <path> into paths.
    for target_id in target_ids:
        source_dir, target_name = target_id.rsplit(':', 1)

        if target_name != '*' and target_name != '...':
            cited_targets.add((source_dir, target_name))
        elif target_name == '...':
            for root, dirs, files in os.walk(source_dir):
                # Note the dirs[:] = slice assignment; we are replacing the
                # elements in dirs (and not the list referred to by dirs) so
                # that os.walk() will not process deleted directories.
                dirs[:] = [d for d in dirs if not _is_load_excluded(root, d)]
                if 'BUILD' in files:
                    source_dirs.append(root)
        else:
            source_dirs.append(source_dir)

    direct_targets = list(cited_targets)

    # Load BUILD files in paths, and add all loaded targets into
    # cited_targets.  Together with above step, we can ensure that all
    # targets mentioned in the command line are now in cited_targets.
    for source_dir in source_dirs:
        _load_build_file(source_dir,
                         processed_source_dirs,
                         blade)

    for key in target_database:
        cited_targets.add(key)
    all_command_targets = list(cited_targets)

    # Starting from targets specified in command line, breath-first
    # propagate to load BUILD files containing directly and indirectly
    # dependent targets.  All these targets form related_targets,
    # which is a subset of target_databased created by loading  BUILD files.
    while cited_targets:
        source_dir, target_name = cited_targets.pop()
        target_id = (source_dir, target_name)
        if target_id in related_targets:
            continue

        _load_build_file(source_dir,
                         processed_source_dirs,
                         blade)

        if target_id not in target_database:
            console.error_exit('%s: target //%s:%s does not exist' % (
                _find_depender(target_id, blade), source_dir, target_name))

        related_targets[target_id] = target_database[target_id]
        for key in related_targets[target_id].expanded_deps:
            if key not in related_targets:
                cited_targets.add(key)

    # Iterating to get svn root dirs
    for path, name in related_targets:
        root_dir = path.split('/')[0].strip()
        if root_dir not in blade.svn_root_dirs and '#' not in root_dir:
            blade.svn_root_dirs.append(root_dir)

    return direct_targets, all_command_targets, related_targets
