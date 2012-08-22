"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Huan Yu <huanyu@tencent.com>
         Feng Chen <phongchen@tencent.com>
         Yi Wang <yiwang@tencent.com>
         Chong Peng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the CmdOptions module which parses the users'
 input and provides hint for users.

"""


import os
import sys
import traceback
from blade_util import error_exit
from blade_util import get_cwd
from blade_util import relative_path
from blade_util import warning
from cc_targets import cc_binary
from cc_targets import CcBinary
from cc_targets import cc_library
from cc_targets import CcLibrary
from cc_targets import cc_plugin
from cc_targets import CcPlugin
from cc_targets import cc_test
from cc_targets import CcTest
from cc_targets import lex_yacc_library
from cc_targets import LexYaccLibrary
from cc_targets import proto_library
from cc_targets import ProtoLibrary
from cc_targets import resource_library
from cc_targets import ResourceLibrary
from cc_targets import swig_library
from cc_targets import SwigLibrary
from gen_rule_target import gen_rule
from gen_rule_target import GenRuleTarget
from java_jar_target import java_jar
from java_jar_target import JavaJarTarget
from py_targets import py_binary
from py_targets import PythonBinaryTarget


IGNORE_IF_FAIL = 0
WARN_IF_FAIL = 1
ABORT_IF_FAIL = 2


class TargetAttributes(object):
    """Build target attributes
    """
    def __init__(self, arch, bits):
        self._arch = arch
        self._bits = bits

    @property
    def bits(self):
        return self._bits

    @property
    def arch(self):
        return self._arch


build_target = None


def _find_dir_depender(dir, blade):
    """_find_dir_depender to find which target depends on the dir.

    """
    target_database = blade.get_target_database()
    for key in target_database:
        for dkey in target_database[key]['deps']:
            if dkey[0] == dir:
                return "//%s:%s" % (target_database[key]["path"],
                                target_database[key]["name"])
    return None


def _report_not_exist(source_dir, path, blade):
    """ Report dir or BUILD file does not exist
    """
    depender = _find_dir_depender(source_dir, blade)
    if depender:
        error_exit('//%s not found, required by %s, exit...' % (path, depender))
    else:
        error_exit('//%s not found, exit...' % path)


def enable_if(cond, true_value, false_value = None):
    """A global function can be called in BUILD to filter srcs by target"""
    ret = true_value if cond else false_value
    if ret is None:
        ret = []
    return ret


def _load_build_file(source_dir, action_if_fail, processed_source_dirs, blade):
    """_load_build_file to load the BUILD and place the targets into database.

    Invoked by _load_targets.  Load and execute the BUILD
    file, which is a Python script, in source_dir.  Statements in BUILD
    depends on global variable current_source_dir, and will register build
    target/rules into global variables target_database.  If path/BUILD
    does NOT exsit, take action corresponding to action_if_fail.  The
    parameters processed_source_dirs refers to a set defined in the
    caller and used to avoid duplicated execution of BUILD files.

    """

    # Initialize the build_target at first time, to be used for BUILD file
    # loaded by execfile
    global build_target
    if build_target is None:
        options = blade.get_options()
        if options.m == '32':
            arch = 'i386'
        elif options.m == '64':
            arch = 'x86_64'
        build_target = TargetAttributes(arch, int(options.m))

    source_dir = os.path.normpath(source_dir)
    # TODO(yiwang): the character '#' is a magic value.
    if source_dir in processed_source_dirs or source_dir == '#':
        return
    processed_source_dirs.add(source_dir)

    if not os.path.exists(source_dir):
        _report_not_exist(source_dir, source_dir, blade)

    old_path_reserved = blade.get_current_source_path()
    blade.set_current_source_path(source_dir)
    build_file = os.path.join(source_dir, 'BUILD')
    if os.path.exists(build_file):
        try:
            # The magic here is that a BUILD file is a Python script,
            # which can be loaded and executed by execfile().
            execfile(build_file, globals(), None)
        except SystemExit:
            error_exit("%s: fatal error, exit..." % build_file)
        except:
            error_exit('Parse error in %s, exit...\n%s' % (
                    build_file, traceback.format_exc()))
    else:
        if action_if_fail == ABORT_IF_FAIL:
            _report_not_exist(source_dir, build_file, blade)

    blade.set_current_source_path(old_path_reserved)


def _find_depender(dkey, blade):
    """_find_depender to find which target depends on the target with dkey.

    """
    target_database = blade.get_target_database()
    for key in target_database:
        if dkey in target_database[key]['deps']:
            return "//%s:%s" % (target_database[key]["path"],
                                target_database[key]["name"])
    return None


def load_targets(target_ids, working_dir, blade_root_dir, blade):
    """load_targets.

    Parse and load targets, including those specified in command line
    and their direct and indirect dependencies, by loading related BUILD
    files.  Returns a map which contains all these targets.

    """
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
        if target_id.find(':') == -1:
            source_dir, target_name = target_id, '*'
        else:
            source_dir, target_name = target_id.rsplit(':', 1)

        source_dir = relative_path(os.path.join(working_dir, source_dir),
                                    blade_root_dir)

        if target_name != '*' and target_name != '':
            cited_targets.add((source_dir, target_name))
        elif source_dir.endswith('...'):
            source_dir = source_dir[:-3]
            if not source_dir:
                source_dir = "./"
            source_dirs.append((source_dir, WARN_IF_FAIL))
            for root, dirs, files in os.walk(source_dir):
                # Skip over subdirs starting with '.', e.g., .svn.
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for d in dirs:
                    source_dirs.append((os.path.join(root, d), IGNORE_IF_FAIL))
        else:
            source_dirs.append((source_dir, ABORT_IF_FAIL))

    direct_targets = list(cited_targets)

    # Load BUILD files in paths, and add all loaded targets into
    # cited_targets.  Together with above step, we can ensure that all
    # targets mentioned in the command line are now in cited_targets.
    for source_dir, action_if_fail in source_dirs:
        _load_build_file(source_dir,
                         action_if_fail,
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
                         ABORT_IF_FAIL,
                         processed_source_dirs,
                         blade)

        if target_id not in target_database:
            error_exit("%s: target //%s:%s does not exists" % (
                _find_depender(target_id, blade), source_dir, target_name))

        related_targets[target_id] = target_database[target_id]
        for key in related_targets[target_id]['deps']:
            if key not in related_targets:
                cited_targets.add(key)

    # Iterating to get svn root dirs
    for path, name in related_targets:
        root_dir = path.split("/")[0].strip()
        if root_dir not in blade.svn_root_dirs and '#' not in root_dir:
            blade.svn_root_dirs.append(root_dir)

    blade.set_related_targets(related_targets)

    return direct_targets, all_command_targets


def find_blade_root_dir(working_dir):
    """find_blade_root_dir to find the dir holds the BLADE_ROOT file.

    The blade_root_dir is the directory which is the closest upper level
    directory of the current working directory, and containing a file
    named BLADE_ROOT.

    """
    blade_root_dir = working_dir
    if blade_root_dir.endswith('/'):
        blade_root_dir = blade_root_dir[:-1]
    while blade_root_dir and blade_root_dir != "/":
        if os.path.isfile(os.path.join(blade_root_dir, "BLADE_ROOT")):
            break
        blade_root_dir = os.path.dirname(blade_root_dir)
    if not blade_root_dir or blade_root_dir == "/":
        error_exit("Can't find the file 'BLADE_ROOT' in this or any upper directory.\n"
                   "Blade need this file as a placeholder to locate the root source directory "
                   "(aka the directory where you #include start from).\n"
                   "You should create it manually at the first time.")
    return blade_root_dir

