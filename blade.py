#!/usr/bin/env python
#
# Copyright 2011 Tencent Inc.
#
# Authors: Huan Yu <huanyu@tencent.com>
#          Feng Chen <phongchen@tencent.com>
#          Yi Wang <yiwang@tencent.com>
#          Chong Peng <michaelpeng@tencent.com>
#
# Blade is a software building system built upon SCons, but restricts
# the generality and flexibility of SCons to prevent unnecessary
# error-prone complexity.  With Blade, users wrote a BUILD file and
# put it in each of the source directory.  In each BUILD file, there
# could be one or more build rules, each has a TARGET NAME, source
# files and dependent targets.  Blade suports the following types of
# build rules:
#
#    cc_binary         -- build an executable binary from C++ source
#    cc_library        -- build a library from C++ source
#    cc_plugin         -- build a plugin from C++ source
#    cc_test           -- build a unittest binary from C++ source
#    gen_rule          -- used to specify a general building rule
#    java_jar          -- build java jar from java source files
#    lex_yacc_library  -- build a library from lex/yacc source
#    proto_library     -- build a library from Protobuf source
#    resource_library  -- build resource library and gen header files
#    swig_library      -- build swig library for python and java
#
# A target may depend on other target(s), where the dependency is
# transitive.  A dependent target is referred by a TARGET ID, which
# has either of the following forms:
#
#   //<source_dir>:<target_name> -- target defined in <source_dir>/BUILD
#   :<target_name>               -- target defined in the current BUILD file
#   #<target_name>               -- target is a system library, e.g., pthread
#
# where <source_dir> is an absolute path rooted at the source tree and
# specifying where the BUILD file locates, <target_name> specifies a
# target in the BUILD file, and '//' denotes the root of the source tree.
#
# Users invoke Blade from the command line to build (or clean, or
# test) one or more rule/targets.  In the command line, a target id
# is specified in either of the following forms:
#
#   <path>:<target_name> -- to build target defined in <path>/BUILD
#   <path>               -- to build all targets defined in <path>/BUILD
#   <path>/...           -- to build all targets in all BUILD files in
#                           <path> and its desendant directories.
#
# Note that <path> in command line targets is an operating system
# path, which might be a relative path, but <source_dir> in a BUILD
# referring to a dependent target must be an absolute path, rooted at
# '//'.
#
# For example, the following command line
#
#    blade base mapreduce_lite/... parallel_svm:perf_test
#
# builds all targets in base/BUILD, all targets in all BUILDs under
# directory mapreduce_lite, and the target perf_test defined in
# parallel_svm/BUILD

import errno
import fcntl
from optparse import OptionParser
import os.path
import platform
import signal
import string
import shutil
import subprocess
import sys
import time
import traceback

__pychecker__ = 'no-argsused'

IGNORE_IF_FAIL = 0
WARN_IF_FAIL = 1
ABORT_IF_FAIL = 2


# The directory which changes during the runtime of blade, and
# contains BUILD file under current focus.
current_source_dir = "."

# Given some targets specified in the command line, Blade will load
# BUILD files containing these command line targets; global target
# functions, i.e., cc_libarary, cc_binary and etc, in these BUILD
# files will register targets into target_database, which then becomes
# the input to dependency analyzer and SCons rules generator.  It is
# notable that not all targets in target_database are dependencies of
# command line targets.
target_database = {}

# The map used by build rules to ensure that a source file occurres in
# exactly one rule/target(only library target).
src_target_map = {}

# The scons cache manager class string, which should be output to
# scons script if ccache is not installed
scache_manager_class_str = ''

# The targets dependencies map
# Ex, a java_jar target A relies on swig_library B and proto_library C
# so A:[B,C] is added to the the map
targets_dependency_map = {}

# Command targets
command_targets = []

# Keywords for checking the source files path
# and make sure that warning is used correctly
keywords_list = ['thirdparty']


#------------------------------------------------------------------------------
# >>>>>>               Utilities invoked by BUILD Rules                  <<<<<<
#------------------------------------------------------------------------------
# os.getcwd() doesn't work because it will follow symbol link.
# os.environ.get("PWD") doesn't work because it won't reflect os.chdir().
# So in practice we simply use system('pwd') to get current working directory.
def _get_cwd():
    return subprocess.Popen(["pwd"],
                            stdout=subprocess.PIPE,
                            shell=True).communicate()[0].strip()

def _lock_file(fd, flags):
    try:
        fcntl.flock(fd, flags)
        return (True, 0)
    except IOError, ex_value:
        return (False, ex_value[0])

def _unlock_file(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return (True, 0)
    except IOError, ex_value:
        return (False, ex_value[0])

_color_enabled = False

def _error_exit(msg, code = 1):
    msg = "Blade(error): " + msg
    if _color_enabled:
        msg = '\033[1;31m' + msg + '\033[0m'
    print >>sys.stderr, msg
    sys.exit(code)

def _warning(msg):
    msg = "Blade(warning): " + msg
    if _color_enabled:
        msg = '\033[1;33m' + msg + '\033[0m'
    print >>sys.stderr, msg

def _check_name(name):
    if '/' in name:
        _error_exit('%s:%s: Invalid target name, should not contain dir part.' % (
                current_source_dir, name))

def _check_deps(name, deps):
    for dep in deps:
        if not (dep.startswith(':') or dep.startswith('#') or
                dep.startswith('//') or dep.startswith('./')):
            _error_exit('%s/%s: Invalid dep in %s.' % (current_source_dir, name, dep))
        if dep.count(':') > 1:
            _error_exit('%s/%s: Invalid dep %s, missing \',\' between 2 deps?' %
                        (current_source_dir, name, dep))


def _general_target(name, srcs, deps, target_type, kwargs):
    _check_name(name)
    _check_deps(name, deps)
    _check_kwargs(name, kwargs)

    key = (current_source_dir, name)
    target_database[key] = {'type' : target_type,
                            'srcs' : srcs,
                            'deps' : [],
                            'path' : current_source_dir,
                            'name' : name,
                            'options' : {}
                            }
    allow_dup_src_type_list = ['cc_binary', 'cc_test', 'dynamic_cc_binary']
    for s in srcs:
        if '..' in s or s.startswith('/'):
            raise Exception, (
                'Invalid source file path: %s. '
                'can only be relative path, and must in current directory or '
                'subdirectorys') % s

        src_key = os.path.normpath('%s/%s' % (current_source_dir, s))
        src_value = '%s %s:%s' % (target_type, current_source_dir, name)
        if src_key in src_target_map:
            value_existed = src_target_map[src_key]
            if not (value_existed.split(": ")[0] in allow_dup_src_type_list and
                    target_type in allow_dup_src_type_list):
                # Just warn here, not raising exception
                _warning( 'Source %s belongs to both %s and %s' % (
                        s, src_target_map[src_key], src_value))
        src_target_map[src_key] = src_value

    for d in deps:
        if d[0] == ':':
            # Depend on library in current directory
            dkey = (os.path.normpath(current_source_dir), d[1:])
        elif d.startswith('//'):
            # Depend on library in remote directory
            if not ':' in d:
                raise Exception, 'Wrong format in %s:%s' % (current_source_dir,
                                                            name)
            (path, lib) = d[2:].rsplit(':', 1)
            dkey = (os.path.normpath(path), lib)
        elif d.startswith('#'):
            # System libaray, they don't have entry in BUILD so we need
            # to add deps manually.
            dkey = ('#', d[1:])
            target_database[dkey] = {'type' : 'system_library',
                                     'srcs' : '',
                                     'deps' : [],
                                     'path' : current_source_dir,
                                     'name' : d,
                                     'options': {}
                                     }
        else:
            # Depend on library in relative subdirectory
            if not ':' in d:
                raise Exception, 'Wrong format in %s:%s' % (current_source_dir,
                                                            name)
            (path, lib) = d.rsplit(':', 1)
            if '..' in path:
                raise Exception, "Don't use '..' in path"
            dkey = (os.path.normpath('%s/%s' %
                                     (current_source_dir, path)), lib)

        if dkey not in target_database[key]['deps']:
            target_database[key]['deps'].append(dkey)


def _var_to_list(var):
    if isinstance(var, list):
        return var
    return [var]

def _check_kwargs(name, kwargs):
    if kwargs:
        _warning("%s:%s: unrecognized options %s"  % (
                 current_source_dir, name, kwargs))

def _check_incorrect_no_warning(warning, target_key, srcs):
    if not srcs or warning == 'yes':
        return

    global current_source_dir
    global keywords_list
    for keyword in keywords_list:
        if keyword in current_source_dir:
            return

    illegal_path_list = []
    for keyword in keywords_list:
        illegal_path_list += [s for s in srcs if not keyword in s]

    if illegal_path_list:
        _warning("//%s:%s : warning='no' is only allowed for code in thirdparty." % (
                target_key[0], target_key[1]))

def _cc_target(name,
               srcs=[],
               deps=[],
               warning='yes',
               defs=[],
               incs=[],
               optimize=[],
               extra_cppflags=[],
               target_type='',
               kwargs=None):
    srcs = _var_to_list(srcs)
    deps = _var_to_list(deps)
    defs = _var_to_list(defs)
    incs = _var_to_list(incs)
    opt  = _var_to_list(optimize)
    extra_cppflags = _var_to_list(extra_cppflags)
    _general_target(name, srcs, deps, target_type, kwargs)
    key = (current_source_dir, name)

    target_database[key]['options']['warnings'] = warning
    target_database[key]['options']['defs'] = defs
    target_database[key]['options']['incs'] = incs
    target_database[key]['options']['optimize'] = opt
    target_database[key]['options']['extra_cppflags'] = extra_cppflags

    _check_defs(defs)
    _check_incorrect_no_warning(warning, key, srcs)

def _check_defs(defs = []):
    cxx_keyword_list = [
            "and", "and_eq", "alignas", "alignof", "asm", "auto",
            "bitand", "bitor", "bool", "break", "case", "catch",
            "char", "char16_t", "char32_t", "class", "compl", "const",
            "constexpr", "const_cast", "continue", "decltype", "default",
            "delete", "double", "dynamic_cast", "else", "enum",
            "explicit", "export", "extern", "false", "float", "for",
            "friend", "goto", "if", "inline", "int", "long", "mutable",
            "namespace", "new", "noexcept", "not", "not_eq", "nullptr",
            "operator", "or", "or_eq", "private", "protected", "public",
            "register", "reinterpret_cast", "return", "short", "signed",
            "sizeof", "static", "static_assert", "static_cast", "struct",
            "switch", "template", "this", "thread_local", "throw",
            "true", "try", "typedef", "typeid", "typename", "union",
            "unsigned", "using", "virtual", "void", "volatile", "wchar_t",
            "while", "xor", "xor_eq"]
    for macro in defs:
        pos = macro.find('=')
        if pos != -1:
            macro = macro[0:pos]
        if macro in cxx_keyword_list:
            _warning("DO NOT specify c++ keyword %s in defs list" % macro )

#------------------------------------------------------------------------------
# >>>>>>                         Build Rules                             <<<<<<
#------------------------------------------------------------------------------


def cc_library(name,
               srcs=[],
               deps=[],
               warning='yes',
               defs=[],
               incs=[],
               optimize=[],
               always_optimize=False,
               pre_build=0,
               link_all_symbols=0,
               extra_cppflags=[],
               **kwargs):
    _cc_target(name, srcs, deps, warning, defs,
               incs, optimize, extra_cppflags, 'cc_library', kwargs)
    key = (current_source_dir, name)
    if pre_build:
        target_database[key]['type'] = 'pre_build_cc_library'
        target_database[key]['srcs'] = []

    target_database[key]['options']['link_all_symbols'] = link_all_symbols
    target_database[key]['options']['always_optimize'] = always_optimize


def cc_test(name,
            srcs = [],
            deps = [],
            warning = 'yes',
            defs = [],
            incs = [],
            optimize = [],
            dynamic_link = 0,
            testdata = [],
            extra_cppflags = [],
            export_dynamic = 0,
            **kwargs):
    testdata = _var_to_list(testdata)
    _cc_target(name, srcs, deps, warning, defs,
               incs, optimize, extra_cppflags, 'cc_test', kwargs)

    key = (current_source_dir, name)
    target_database[key]['options']['testdata'] = testdata

    # Hardcode deps rule to thirdparty gtest main lib.
    dkey = ('thirdparty/gtest', 'gtest_main')
    if dkey not in target_database[key]['deps']:
        target_database[key]['deps'].append(dkey)

    dkey = ('thirdparty/gtest', 'gtest')
    if dkey not in target_database[key]['deps']:
        target_database[key]['deps'].append(dkey)

    if dynamic_link == 1:
        target_database[key]['type'] = 'dynamic_cc_test'

    if export_dynamic == 1:
        target_database[key]['options']['export_dynamic'] = 1


def cc_binary(name,
              srcs = [],
              deps = [],
              warning = 'yes',
              defs = [],
              incs = [],
              optimize = [],
              dynamic_link = 0,
              extra_cppflags = [],
              export_dynamic = 0,
              **kwargs):
    _cc_target(name, srcs, deps, warning, defs,
               incs, optimize, extra_cppflags, 'cc_binary', kwargs)
    key = (current_source_dir, name)
    if dynamic_link == 1:
        target_database[key]['type'] = 'dynamic_cc_binary'

    if export_dynamic == 1:
        target_database[key]['options']['export_dynamic'] = 1


def java_jar(name, srcs = [], deps = [], pre_build = 0, **kwargs):
    srcs = _var_to_list(srcs)
    deps = _var_to_list(deps)
    key = (current_source_dir, name)
    _general_target(name, srcs, deps, 'java_jar', kwargs)
    if pre_build:
        target_database[key]['type'] = 'pre_build_java_jar'


def proto_library(name,
                  srcs=[],
                  deps=[],
                  optimize=[],
                  **kwargs):
    srcs = _var_to_list(srcs)
    for src in srcs:
        _check_proto_src_name(src)
    deps = _var_to_list(deps)
    _general_target(name, srcs, deps, 'proto_library', kwargs)

    # Hardcode deps rule to thirdparty protobuf lib.
    dkey = ('thirdparty/protobuf', 'protobuf')
    key = (current_source_dir, name)
    if dkey not in target_database[key]['deps']:
        target_database[key]['deps'].append(dkey)

    target_database[key]['options']['link_all_symbols'] = 1
    target_database[key]['options']['optimize'] = _var_to_list(optimize)


def lex_yacc_library(name, srcs = [], deps = [],
                     recursive = 0, prefix = None, **kwargs):
    if len(srcs) != 2:
        raise Exception, ("'srcs' for lex_yacc_library should "
                          "be a pair of (lex_source, yacc_source)")
    deps = _var_to_list(deps)
    key = (current_source_dir, name)
    _general_target(name, srcs, deps, 'lex_yacc_library', kwargs)
    target_database[key]['options']['recursive'] = recursive
    target_database[key]['options']['prefix'] = prefix


def gen_rule(name, srcs = [], outs = [], deps = [], cmd = "", **kwargs):
    srcs = _var_to_list(srcs)
    deps = _var_to_list(deps)
    outs = _var_to_list(outs)
    _general_target(name, srcs, deps, 'gen_rule', kwargs)
    key = (current_source_dir, name)
    target_database[key]['outs'] = outs
    target_database[key]['cmd'] = cmd


def cc_plugin(name,
              srcs = [],
              deps = [],
              warning = 'yes',
              defs = [],
              incs = [],
              optimize = [],
              pre_build = 0,
              link_all_symbols = 0,
              extra_cppflags = [],
              **kwargs):
    _cc_target(name, srcs, deps, warning, defs,
               incs, optimize, extra_cppflags, 'cc_library', kwargs)
    key = (current_source_dir, name)
    target_database[key]['type'] = 'cc_plugin'
    if pre_build == 1:
        target_database[key]['type'] = 'pre_build_cc_library'
        target_database[key]['srcs'] = []

    target_database[key]['options']['link_all_symbols'] = link_all_symbols


def swig_library(name,
                 srcs=[],
                 deps=[],
                 warning='no',
                 java_package='',
                 java_lib_packed=0,
                 optimize=[],
                 extra_swigflags=[],
                 **kwargs):
    _cc_target(name, srcs, deps, 'yes', [],
               [], [], extra_swigflags, 'cc_library', kwargs)
    key = (current_source_dir, name)
    target_database[key]['type'] = 'swig_library'

    target_database[key]['options']['cpperraswarn'] = warning
    target_database[key]['options']['java_package'] = java_package
    target_database[key]['options']['java_lib_packed'] = java_lib_packed
    target_database[key]['options']['optimize'] = _var_to_list(optimize)

def resource_library(name,
                     srcs=[],
                     deps=[],
                     optimize=[],
                     extra_cppflags=[],
                     **kwargs):
    _cc_target(name, srcs, deps, 'yes', [],
               [], [], extra_cppflags, 'cc_library', kwargs)
    key = (current_source_dir, name)
    target_database[key]['type'] = 'resource_library'
    target_database[key]['options']['optimize'] = _var_to_list(optimize)

#------------------------------------------------------------------------------
# >>>>>>              Build rules helper functions                       <<<<<<
#------------------------------------------------------------------------------

def _check_proto_src_name(src):
    err = 0
    base_name = os.path.basename(src)
    pos = base_name.rfind('.')
    if pos == -1:
        err = 1
    file_suffix = base_name[pos + 1:]
    if file_suffix != 'proto':
        err = 1
    if err:
        _error_exit("invalid proto file name %s" % src)


#------------------------------------------------------------------------------
# >>>>>>              Ccache/Scons cache manager                         <<<<<<
#------------------------------------------------------------------------------

# CcacheManager is mainly used to setup the ccache environment
# provided that the system has ccache installed. Blade will
# use ccache as compiler cache.
class CcacheManager(object):
    def __init__(self, blade_root_dir, scons_rules_generator = None,
                 distcc_host_list = [], ccache_dir = '~/.ccache',
                 ccache_prefix = '', ccache_log = '~/ccache.log'):
        self.blade_root_dir = blade_root_dir
        self.rules_generator = scons_rules_generator
        self.distcc_host_list = distcc_host_list
        self.ccache_dir = os.path.expanduser(ccache_dir)
        self.ccache_prefix = ccache_prefix
        self.ccache_log = os.path.expanduser(ccache_log)
        self.ccache_installed = self._check_ccache_install()

    @staticmethod
    def _check_ccache_install():
        p = subprocess.Popen(
            "ccache --version",
            env={},
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True)
        (stdout, stderr) = p.communicate()
        if p.returncode == 0:
            version_line = stdout.splitlines(True)[0]
            if version_line and version_line.find("ccache version") != -1:
                print "Blade: ccache found"
                return True
        return False

    def is_ccache_installed(self):
        return self.ccache_installed

    def setup_ccache_env(self, envs):
        if not self.ccache_installed:
            return
        distcc_env = 'DISTCC_HOSTS = "%s"' % ' '.join(self.distcc_host_list)
        ccache_dir = 'CCACHE_DIR = "%s"' % self.ccache_dir
        ccache_prefix = 'CCACHE_PREFIX = "%s"' % self.ccache_prefix
        ccache_logfile = 'CCACHE_LOGFILE = "%s"' % self.ccache_log
        ccache_basedir = 'CCACHE_BASEDIR = "%s"' % self.blade_root_dir
        rule_generator = self.rules_generator
        if rule_generator:
            for env in envs:
                rule_generator._output('%s.Append(%s, %s, %s, %s, %s)' % (
                        env,
                        distcc_env,
                        ccache_dir,
                        ccache_prefix,
                        ccache_logfile,
                        ccache_basedir))

scache_manager_class_str = """
# Scons cache manager, which should be output to scons script.
# It will periodically check the cache folder and purge the files
# with smallest weight. The weight for each file is caculated as
# file_size * exp(-age * log(2) / half_time).
# We should pay attention that this progress will impact large builds
# and we should not reduce the progress interval(the evaluating nodes).
class ScacheManager(object):
    def __init__(self, cache_path = None, cache_limit = 0,
                 cache_life = 6 * 60 * 60):
        self.cache_path = cache_path
        self.cache_limit = cache_limit
        self.cache_life = cache_life
        self.exponent_scale = math.log(2) / cache_life
        self.purge_cnt = 0

    def __call__(self, node, *args, **kwargs):
        self.purge(self.get_file_list())

    def cache_remove(self, file_item):
        if not file_item:
            return
        if not os.path.exists(file_item):
            return
        os.remove(file_item)

    def purge(self, file_list):
        self.purge_cnt += 1
        if not file_list:
            return
        map(self.cache_remove, file_list)
        print 'Blade: scons cache purged'

    def get_file_list(self):
        if not self.cache_path:
            return []

        file_stat_list = [(x, os.stat(x)[6:8]) for x in glob.glob(os.path.join(self.cache_path, '*', '*'))]
        if not file_stat_list:
            return []

        current_time = time.time()
        file_stat_list = [(x[0], x[1][0],
            x[1][0]*math.exp(self.exponent_scale*(x[1][1] - current_time)))
            for x in file_stat_list]

        file_stat_list.sort(key = lambda x: x[2], reverse = True)

        total_sz, start_index = 0, None
        for i, x in enumerate(file_stat_list):
            total_sz += x[1]
            if total_sz >= self.cache_limit:
                start_index = i
                break

        if not start_index:
            return []
        else:
            return [x[0] for x in file_stat_list[start_index:]]
"""

#------------------------------------------------------------------------------
# >>>>>>              Rules/Targets Dependency Expander                  <<<<<<
#------------------------------------------------------------------------------

# Given the map of related targets, i.e., the subset of target_database
# that are dependencies of those targets speicifed in Blade command
# line, this utility class expands the 'deps' property of each target
# to be all direct and indirect dependencies of that target.
class DependenciesExpander:
    def __init__(self, targets):
        self.targets = targets
        self.deps_map_cache = {}

    def expand_deps(self):
        for target_id in self.targets.keys():
            self.targets[target_id]['deps'] = self._find_all_deps(target_id)
            # Handle the special case: dependencies of a dynamic_cc_binary
            # must be built as dynamic libraries.
            if (self.targets[target_id]['type'] == 'dynamic_cc_binary') or (
                self.targets[target_id]['type'] == 'dynamic_cc_test'):
                for dep in self.targets[target_id]['deps']:
                    self.targets[dep]['options']['build_dynamic'] = 1
            elif self.targets[target_id]['type'] == 'swig_library':
                for dep in self.targets[target_id]['deps']:
                    if self.targets[dep]['type'] == 'proto_library':
                        self.targets[dep]['options']['generate_php'] = True
            elif self.targets[target_id]['type'] == 'java_jar':
                target_name = self.targets[target_id]['name']
                if not target_name in targets_dependency_map.keys():
                    targets_dependency_map[target_name] = []
                for dep in self.targets[target_id]['deps']:
                    if self.targets[dep]['type'] == 'proto_library':
                        self.targets[dep]['options']['generate_java'] = True
                        dep_target_name = self.targets[dep]['name']
                        targets_dependency_map[target_name].append(dep_target_name)
                    elif self.targets[dep]['type'] == 'swig_library':
                        self.targets[dep]['options']['generate_java'] = True
                        dep_target_name = self.targets[dep]['name']
                        targets_dependency_map[target_name].append(dep_target_name)


    # Return all targets depended by target_id directly and/or indirectly.
    # We need the parameter root_target_id to check loopy dependency.
    def _find_all_deps(self, target_id, root_target_id = None):
        if root_target_id == None:
            root_target_id = target_id

        new_deps_list = self.deps_map_cache.get(target_id, None)
        if not new_deps_list is None:
            return new_deps_list

        new_deps_list = []
        for d in self.targets[target_id]['deps']:
            if d == root_target_id:
                print "loop dependency of %s" % ':'.join(root_target_id)
            new_deps_piece = [d]
            if d not in self.targets:
                _error_exit('Target %s:%s depends on %s:%s, '
                            'but it is missing, exit...' % (target_id[0],
                                                            target_id[1],
                                                            d[0],
                                                            d[1]))
            new_deps_piece += self._find_all_deps(d, root_target_id)
            # Append new_deps_piece to new_deps_list, be aware of
            # de-duplication:
            for nd in new_deps_piece:
                if nd in new_deps_list:
                    new_deps_list.remove(nd)
                new_deps_list.append(nd)

        self.deps_map_cache[target_id] = new_deps_list
        return new_deps_list


    def get_targets(self):
        return self.targets


#------------------------------------------------------------------------------
# >>>>>>                   SCons Rules Generator                         <<<<<<
#------------------------------------------------------------------------------

class SconsRulesGenerator:
    def __init__(self, scons_path, targets, options, blade_root_dir):
        self.targets = targets
        self.objects = {}
        self.scons_file = open(scons_path, 'w')
        self.build_dir = "build%s_%s" % (options.m, options.profile)
        self.options = options
        self.gcc_version = self._get_gcc_version("gcc")
        self.python_inc = self._get_python_include()
        self.java_inc = self._get_java_include()
        self.php_inc = self._get_php_include()
        self.java_class_path_list = []
        self.java_jar_dep_source_list = []
        self.java_jar_dep_source_files_map = {}
        self.java_jar_after_dep_source_list = []
        self.java_jar_cmd_list = []
        self.java_jar_var_map = {}
        self.java_jar_targets_map = {}
        self.pyswig_flags = ''
        self.javaswig_flags = ''
        self.ccache_mgr = CcacheManager(blade_root_dir)
        self.cmd_var_list = []
        self.java_external_pack_files = []
        self.gen_rule_files_map = {}
        self.var_names_cache = {}
        self.flags_except_warning = []
        self.warning_cflags = []
        self.warning_cxxflags = []
        self.warning_cppflags = []

    def _output(self, content):
        print >>self.scons_file, content

    @staticmethod
    def _get_gcc_version(compiler):
        p = subprocess.Popen(
            compiler + " --version",
            env={},
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True)
        (stdout, stderr) = p.communicate()
        if p.returncode == 0:
            version_line = stdout.splitlines(True)[0]
            version = version_line.split()[2]
            return version
        return ""

    @staticmethod
    def _get_python_include():
        p = subprocess.Popen(
            "python-config --includes",
            env={},
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True)
        (stdout, stderr) = p.communicate()
        if p.returncode == 0:
            include_line = stdout.splitlines(True)[0]
            header = include_line.split()[0][2:]
            return header
        return ""

    @staticmethod
    def _get_java_include():
        p = subprocess.Popen(
            "java -version",
            env={},
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True)
        (stdout, stderr) = p.communicate()
        if p.returncode == 0:
            version_line = stderr.splitlines(True)[0]
            version = version_line.split()[2]
            version = version.replace('"', '')
            include_list = []
            include_list.append('/usr/java/jdk%s/include' % version)
            include_list.append('/usr/java/jdk%s/include/linux' % version)
            return include_list
        return []

    @staticmethod
    def _get_php_include():
        p = subprocess.Popen(
            "php-config --includes",
            env={},
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True)
        (stdout, stderr) = p.communicate()
        if p.returncode == 0:
            include_line = stdout.splitlines(True)[0]
            headers = include_line.split()
            header_list = [ "'%s'" % s[2:] for s in headers]
            return header_list
        return ""

    @staticmethod
    def _get_package_name(src):
        package_name_java = 'java_package'
        package_name = 'package'
        if not os.path.isfile(src):
            return ""
        package_line = ''
        package = ''
        normal_package_line = ''
        for line in open(src):
            line = line.strip()
            if line.startswith('//'):
                continue
            pos = line.find('//')
            if pos != -1:
                line = line[0:pos]
            if package_name_java in line:
                package_line = line
                break
            if line.startswith(package_name):
                normal_package_line = line

        if package_line:
            package = package_line.split('=')[1]
            package = package.strip("""'";\n""")
            package = package.replace('.', '/')
            return package
        elif normal_package_line:
            package = normal_package_line.split(' ')[1]
            package = package.strip("""'";\n""")
            package = package.replace('.', '/')
            return package
        else:
            return ""

    def _topological_sort(self, pairlist):
        numpreds = {}   # elt -> # of predecessors
        successors = {} # elt -> list of successors
        for second, options in pairlist.items():
            if not numpreds.has_key(second):
                numpreds[second] = 0
            deps = options['deps']
            for first in deps:
                # make sure every elt is a key in numpreds
                if not numpreds.has_key(first):
                    numpreds[first] = 0

                # since first < second, second gains a pred ...
                numpreds[second] = numpreds[second] + 1

                # ... and first gains a succ
                if successors.has_key(first):
                    successors[first].append(second)
                else:
                    successors[first] = [second]

        # suck up everything without a predecessor
        answer = filter(lambda x, numpreds=numpreds: numpreds[x] == 0,
                        numpreds.keys())

        # for everything in answer, knock down the pred count on
        # its successors; note that answer grows *in* the loop
        for x in answer:
            assert numpreds[x] == 0
            del numpreds[x]
            if successors.has_key(x):
                for y in successors[x]:
                    numpreds[y] = numpreds[y] - 1
                    if numpreds[y] == 0:
                        answer.append(y)

        return answer

    def _regular_variable_name(self, name):
        return name.translate(string.maketrans(",-/.+*", "______"))

    def _generate_variable_name(self, path, name, suffix = ""):
        suffix_str = ""
        if suffix:
            suffix_str = "_suFFix_%s" % suffix
        reg_path = self.var_names_cache.get(path, "")
        reg_name = self.var_names_cache.get(name, "")
        if not reg_path:
            reg_path = self._regular_variable_name(path)
            self.var_names_cache[path] = reg_path
        if not reg_name:
            reg_name = self._regular_variable_name(name)
            self.var_names_cache[name] = reg_name
        return "v_%s_mAgIc_%s%s" % (reg_path, reg_name,suffix_str)

    def _file_path(self, path, file):
        return "%s/%s/%s" % (self.build_dir, path, file)

    def _srcs_list(self, path, srcs):
        return ','.join(["'%s'" % self._file_path(path, src) for src in srcs])

    def _pyswig_gen_file(self, path, src):
        swig_name = src[:-2]
        return self._file_path(path, '%s_pywrap.cxx' % swig_name)

    def _javaswig_gen_file(self, path, src):
        swig_name = src[:-2]
        return self._file_path(path, '%s_javawrap.cxx' % swig_name)

    def _phpswig_gen_file(self, path, src):
        swig_name = src[:-2]
        return self._file_path(path, '%s_phpwrap.cxx' % swig_name)

    def _swig_src_file(self, path, src):
        return self._file_path(path, src)

    def _proto_gen_files(self, path, src):
        proto_name = src[:-6]
        return (self._file_path(path, '%s.pb.cc' % proto_name),
                self._file_path(path, '%s.pb.h' % proto_name))

    def _proto_gen_php_files(self, path, src):
        proto_name = src[:-6]
        return self._file_path(path, '%s.pb.php' % proto_name)

    def _java_jar_gen_path(self, path, src):
        return os.path.join(path, src)

    def _java_jar_gen_class_root(self, path, name):
        return os.path.join(self.build_dir, path, name + '_classes')

    def _proto_java_gen_file(self, path, src, package):
        proto_name = src[:-6]
        base_name  = os.path.basename(proto_name)
        base_name  = ''.join(base_name.title().split('_'))
        base_name  = '%s.java' % base_name
        dir_name = os.path.join(path, package)
        proto_name = os.path.join(dir_name, base_name)
        return os.path.join(self.build_dir, proto_name)


    def _proto_src_file(self, path, src):
        return '%s/%s' % (path, src)


    def _env_name(self, target):
        return "env_%s" % self._generate_variable_name(target['path'],
                                                       target['name'])

    def _objs_name(self, target):
        return "objs_%s" % self._generate_variable_name(target['path'],
                                                        target['name'])

    # TODO(phongchen): more reliable way
    def _dep_is_library(self, dep):
        target_type = self.targets[dep].get('type')
        return ('library' in target_type or 'plugin' in target_type)

    def _dep_is_jar_to_compile(self, dep):
        target_type = self.targets[dep].get('type')
        return ('java_jar' in target_type and 'pre_build' not in target_type)

    def _java_jar_deps_list(self, deps):
        jar_list = []
        for jar in deps:
            if not jar:
                continue

            if not self._dep_is_jar_to_compile(jar):
                continue

            jar_name = '%s.jar' % jar[1]
            jar_path = os.path.join(self.build_dir, jar[0], jar_name)
            jar_list.append(jar_path)
        return jar_list

    def _static_deps_list(self, deps):
        lib_list = []
        link_all_symbols_lib_list = []
        for lib in deps:
            # lib is (path, libname) pair.
            if not lib:
                continue

            if not self._dep_is_library(lib):
                continue

            # system lib
            if lib[0] == "#":
                lib_name = "'%s'" % lib[1]
                lib_path = lib[1]
            else:
                lib_name = self._generate_variable_name(lib[0], lib[1])
                lib_path = self._file_path(lib[0], 'lib%s.a' % lib[1])

            if self.targets[lib].get('options', {}).get('link_all_symbols', 0):
                link_all_symbols_lib_list.append((lib_path, lib_name))
            else:
                lib_list.append(lib_name)

        return (link_all_symbols_lib_list, lib_list)


    def _dynamic_deps_list(self, deps):
        lib_list = []
        for lib in deps:
            # lib is (path, libname) pair.
            if not lib:
                continue

            if not self._dep_is_library(lib):
                continue

            if (self.targets[lib]['type'] == 'cc_library' and
                not self.targets[lib]['srcs']):
                continue
            # system lib
            if lib[0] == "#":
                lib_name = "'%s'" % lib[1]
            else:
                lib_name = self._generate_variable_name(lib[0],
                                                        lib[1],
                                                        "dynamic")

            lib_list.append(lib_name)

        return lib_list


    def _pre_build_cc_library_build_path(self, path, name, dynamic = 0):
        if not dynamic:
            return "%s" % os.path.join(
                self.build_dir,
                path,
                'lib%s.a' % name)
        else:
            return "%s" % os.path.join(
                self.build_dir,
                path,
                'lib%s.so' % name)


    def _pre_build_cc_library_src_path(self, path, name, dynamic = 0):
        if not dynamic:
            return "%s" % os.path.join(
                path,
                'lib%s_%s' % (self.options.m, self.options.profile),
                'lib%s.a' % name)
        else:
            return "%s" % os.path.join(
                path,
                'lib%s_%s' % (self.options.m, self.options.profile),
                'lib%s.so' % name)


    def _env_rules(self, cc_target_type_list, target_types_no_warning):
        for key, target in self.targets.items():
            env_name = self._env_name(target)
            if target['type'] in target_types_no_warning:
                self._output("%s = env_no_warning.Clone()" % env_name)
                continue
            if target['type'] == 'system_library' or (
                    target['type'] in cc_target_type_list):
                continue
            self._output("%s = env_with_error.Clone()" % env_name)

    def _objects_rules(self, cc_target_type_list):
        for key, target in self.targets.items():
            path = target['path']
            objs_name = self._objs_name(target)

            if target['type'] not in cc_target_type_list:
                continue

            env_name = self._env_name(target)
            warnings = target.get('options', {}).get('warnings', '')
            if warnings == 'no':
                self._output("%s = env_no_warning.Clone()" % env_name)
            else:
                self._output("%s = env_with_error.Clone()" % env_name)

            self._setup_cppflags_from_option(target, env_name)

            objs = []
            sources = []
            for src in target['srcs']:
                src_name_header = self._generate_variable_name(path, src)
                src_name = '%s_%s' % (src_name_header, target['name'])
                if src_name not in self.objects:
                    self.objects[src_name] = (
                        "%s_%s_object" % (
                                src_name_header,
                                self._regular_variable_name(target['name'])))
                    target_path = os.path.join(
                            self.build_dir, path, target['name'] + '.objs', src)
                    self._output(
                        "%s = %s.SharedObject(target = '%s' + env['OBJSUFFIX']"
                        ", source = '%s')" % (self.objects[src_name],
                                              env_name,
                                              target_path,
                                              self._file_path(path, src)))
                sources.append(self._file_path(path, src))
                objs.append(self.objects[src_name])
            self._output("%s = [%s]" % (objs_name, ','.join(objs)))
            self._output("%s.Depends(%s, %s)" % (
                         env_name, objs_name, sources))

    def _check_optimize_flags(self, oflag):
        opt_list = ['O0', 'O1', 'O2', 'O3', 'Os', 'Ofast']
        if not oflag in opt_list:
            _error_exit("please specify optimization flags only in %s" % (
                        ','.join(opt_list)))

    def _setup_cppflags_from_option(self, target, env_name):
        cppflags_from_option, incs_list = self._get_cppflags_from_option(target)
        if cppflags_from_option:
            self._output("%s.Append(CPPFLAGS = %s) " % (
                   env_name, cppflags_from_option))
        if incs_list:
            self._output("%s.Append(CPPPATH=%s)" % (
                   env_name, incs_list))

    def _check_gcc_flag(self, gcc_flag_list, cpp_flags, options):
        gcc_flags_list_checked = []
        for flag in gcc_flag_list:
            if flag == '-fno-omit-frame-pointer':
                if options.profile != 'release':
                    continue
            gcc_flags_list_checked.append(flag)
        return gcc_flags_list_checked


    def _get_cppflags_from_option(self, target):
        warnings = target.get('options', {}).get('warnings', '')
        defs_list = target.get('options', {}).get('defs', [])
        incs_list = target.get('options', {}).get('incs', [])
        opt_list = target.get('options', {}).get('optimize', [])
        extra_cppflags = target.get('options', {}).get('extra_cppflags', [])
        always_optimize = target.get('options', {}).get('always_optimize', False)

        cpp_flags = []
        new_defs_list = []
        new_incs_list = []
        new_opt_list = []
        user_oflag = ''
        if warnings == 'no':
            cpp_flags.append('-w')
        if defs_list:
            new_defs_list = [('-D' + macro) for macro in defs_list]
            cpp_flags += new_defs_list
        if incs_list:
            for inc in incs_list:
                new_incs_list.append(os.path.join(target['path'], inc))
        if opt_list:
            for flag in opt_list:
                if flag.find('O') == -1:
                    new_opt_list.append('-' + flag)
                else:
                    self._check_optimize_flags(flag)
                    user_oflag = '-%s' % flag
            cpp_flags += new_opt_list

        oflag = ''
        if always_optimize:
            oflag = user_oflag if user_oflag else '-O2'
            cpp_flags.append(oflag)
        else:
            if self.options.profile == 'release':
                oflag = user_oflag if user_oflag else '-O2'
                cpp_flags.append(oflag)

        # Add the compliation flags here
        # 1. -fno-omit-frame-pointer to release, enabled with 'O', 'O2', 'O3', 'Os'
        blade_gcc_flags = ['-fno-omit-frame-pointer']
        blade_gcc_flags_checked = self._check_gcc_flag(blade_gcc_flags,
                                                       cpp_flags,
                                                       self.options)
        cpp_flags += list(set(blade_gcc_flags_checked).difference(set(cpp_flags)))
        incs_list = list(set(new_incs_list))

        return (cpp_flags + extra_cppflags, incs_list)

    def _filter_out_invalid_flags(self, flag_list, flag_type='cpp', cpp_str='cpp'):
        flag_type_list = ['cpp', 'c', 'cxx']
        flag_list_var = _var_to_list(flag_list)
        if not flag_type in flag_type_list:
            return flag_list

        option = ''
        if flag_type == 'c':
            option = '-xc'
        elif flag_type == 'cxx':
            option = '-xc++'

        ret_flag_list = []
        for flag in flag_list_var:
            cmd_str = "echo '' | %s %s %s >/dev/null 2>&1" % (cpp_str, option, flag)
            if subprocess.call(cmd_str, shell=True) == 0:
                ret_flag_list.append(flag)
        return ret_flag_list

    def _get_error_flags(self, cpp_str='cpp'):
        cppflags = [
                "-Werror=char-subscripts",
                "-Werror=comments",
                "-Werror=conversion-null",
                "-Werror=empty-body",
                "-Werror=endif-labels",
                "-Werror=format",
                "-Werror=format-nonliteral",
                "-Werror=missing-include-dirs",
                "-Werror=non-virtual-dtor",
                "-Werror=overflow",
                "-Werror=overloaded-virtual",
                "-Werror=parentheses",
                "-Werror=reorder",
                "-Werror=return-type",
                "-Werror=sequence-point",
                "-Werror=sign-compare",
                "-Werror=switch",
                "-Werror=type-limits",
                "-Werror=uninitialized",
                # Masked it at first
                # "-Werror=unused-function",
                "-Werror=unused-label",
                "-Werror=unused-result",
                "-Werror=unused-value",
                "-Werror=unused-variable",
                "-Werror=write-strings"
        ]
        cflags = ["-Werror-implicit-function-declaration"]
        cxxflags = [
                "-Werror=vla",
                "-Werror=non-virtual-dtor"
        ]

        filtered_cppflags = self._filter_out_invalid_flags(cppflags, 'cpp', cpp_str)
        filtered_cflags = self._filter_out_invalid_flags(cflags, 'c', cpp_str)
        filtered_cxxflags = self._filter_out_invalid_flags(cxxflags, 'cxx', cpp_str)

        return (filtered_cflags, filtered_cppflags, filtered_cxxflags)

    def _get_warning_flags(self, cpp_str='cpp'):
        cppflags = [
                "-Wall",
                "-Wextra",
                # disable some warnings enabled by Wextra
                "-Wno-unused-parameter",
                "-Wno-missing-field-initializers",
                # other useful warnings
                "-Wendif-labels",
                "-Wfloat-equal",
                "-Wformat=2",
                "-Wframe-larger-than=65536",
                "-Wmissing-include-dirs",
                "-Wpointer-arith",
                "-Wwrite-strings",
        ]
        cxxflags = [
                "-Wno-invalid-offsetof",
                "-Woverloaded-virtual",
                "-Wnon-virtual-dtor",
                "-Wvla"
        ]

        filtered_cppflags = self._filter_out_invalid_flags(cppflags, 'cpp', cpp_str)
        filtered_cxxflags = self._filter_out_invalid_flags(cxxflags, 'cxx', cpp_str)

        return (filtered_cppflags, filtered_cxxflags)

    def _cc_binary_rules(self, target):
        env_name = self._env_name(target)
        if (self.gcc_version >= "4.5"):
            self._output('%s.Append(LINKFLAGS=["-static-libgcc", '
                         '"-static-libstdc++"])' % env_name)

        (link_all_symbols_lib_list, lib_list) = self._static_deps_list(
            target['deps'])
        lib_str = "LIBS=[]"
        if lib_list:
            lib_str = 'LIBS=[%s]' % ','.join(lib_list)
        if link_all_symbols_lib_list:
            whole_link_flags = ["-Wl,--whole-archive"]
            for i in link_all_symbols_lib_list:
                whole_link_flags.append(i[0])
            whole_link_flags.append('-Wl,--no-whole-archive')
            self._output(
                '%s.Append(LINKFLAGS=%s)' % (env_name, whole_link_flags))

        if target.get('options', {}).get('export_dynamic', 0) == 1:
            self._output(
                "%s.Append(LINKFLAGS='-rdynamic')" % env_name)

        self._output("%s = %s.Program('%s', %s, %s)" % (
                self._generate_variable_name(target['path'], target['name']),
                env_name,
                self._file_path(target['path'], target['name']),
                self._objs_name(target),
                lib_str))

        for i in link_all_symbols_lib_list:
            self._output("%s.Depends(%s, %s)" % (
                    env_name,
                    self._generate_variable_name(target['path'],
                                                 target['name']),
                    i[1]))

        self._generate_targets_deps(target,
                    self._generate_variable_name(target['path'], target['name']))

        self._output('%s.Append(LINKFLAGS=str(version_obj[0]))' % env_name)
        self._output("%s.Requires(%s, version_obj)" % (
                env_name,
                self._generate_variable_name(target['path'], target['name'])))


    def _cc_test_rules(self, target):
        self._cc_binary_rules(target)

    def _dynamic_cc_test_rules(self, target):
        self._dynamic_cc_binary_rules(target)

    def _dynamic_cc_binary_rules(self, target):
        env_name = self._env_name(target)

        lib_list = self._dynamic_deps_list(target['deps'])
        lib_str = "LIBS=[]"
        if lib_list:
            lib_str = 'LIBS=[%s]' % ','.join(lib_list)

        if target.get('options', {}).get('export_dynamic', 0) == 1:
            self._output(
                "%s.Append(LINKFLAGS='-rdynamic')" % env_name)

        self._output("%s = %s.Program('%s', %s, %s)" % (
                self._generate_variable_name(target['path'], target['name']),
                env_name,
                self._file_path(target['path'], target['name']),
                self._objs_name(target),
                lib_str))

        self._generate_targets_deps(target,
                    self._generate_variable_name(target['path'], target['name']))

    def _dynamic_cc_library_rules(self, target):
        lib_list = self._dynamic_deps_list(target['deps'])
        lib_str = "LIBS=[]"
        if lib_list:
            lib_str = 'LIBS=[%s]' % ','.join(lib_list)
        env_name = self._env_name(target)
        if target['srcs'] or target['deps']:
            self._output('%s.Append(LINKFLAGS=["-Xlinker", "--no-undefined"])'
                         % env_name)
            self._output("%s = %s.SharedLibrary('%s', %s, %s)" % (
                    self._generate_variable_name(target['path'],
                                                 target['name'],
                                                 'dynamic'),
                    env_name,
                    self._file_path(target['path'], target['name']),
                    self._objs_name(target),
                    lib_str))
            self._generate_targets_deps(target,
                    self._generate_variable_name(target['path'],
                                                 target['name'],
                                                 'dynamic'))

    def _cc_library_rules(self, target):
        env_name = self._env_name(target)

        self._output("%s = %s.Library('%s', %s)" % (
                self._generate_variable_name(target['path'], target['name']),
                env_name,
                self._file_path(target['path'], target['name']),
                self._objs_name(target)))
        self._output("%s.Depends(%s, %s)" % (
                env_name,
                self._generate_variable_name(target['path'], target['name']),
                self._objs_name(target)))
        self._generate_targets_deps(target,
                    self._generate_variable_name(target['path'], target['name']))

        if (self.options.generate_dynamic or
            target.get('options', {}).get('build_dynamic', 0)):
            self._dynamic_cc_library_rules(target)

    def _cc_plugin_rules(self, target):
        env_name = self._env_name(target)

        (link_all_symbols_lib_list, lib_list) = self._static_deps_list(
            target['deps'])
        lib_str = "LIBS=[]"
        if lib_list:
            lib_str = 'LIBS=[%s]' % ','.join(lib_list)
        if link_all_symbols_lib_list:
            whole_link_flags = ["-Wl,--whole-archive"]
            for i in link_all_symbols_lib_list:
                whole_link_flags.append(i[0])
            whole_link_flags.append('-Wl,--no-whole-archive')
            self._output(
                '%s.Append(LINKFLAGS=%s)' % (env_name, whole_link_flags))

        if target['srcs'] or target['deps']:
            self._output('%s.Append(LINKFLAGS=["-fPIC"])'
                         % env_name)
            self._output("%s = %s.SharedLibrary('%s', %s, %s)" % (
                    self._generate_variable_name(target['path'],
                                                 target['name'],
                                                 'dynamic'),
                    env_name,
                    self._file_path(target['path'], target['name']),
                    self._objs_name(target),
                    lib_str))

            self._generate_targets_deps(target,
                    self._generate_variable_name(target['path'],
                                                 target['name'],
                                                 'dynamic'))
        for i in link_all_symbols_lib_list:
            self._output("%s.Depends(%s, %s)" % (
                    env_name,
                    self._generate_variable_name(
                        target['path'], target['name'], 'dynamic'), i[1]))

    def _proto_library_rules(self, target):
        env_name = self._env_name(target)
        # build java source according to its option
        global command_targets
        # java rules is different from php cause the java files
        # are needed to be compiled together. If it is depeneded,
        # it should generate java files.
        if self.options.generate_java or (
                target.get('options', {}).get('generate_java', False) or (
                        target['path'], target['name']) in command_targets):
            self._proto_java_rules(target)

        if self.options.generate_php and (
                target.get('options', {}).get('generate_php', False) or (
                        target['path'], target['name']) in command_targets):
            self._proto_php_rules(target)

        self._setup_cppflags_from_option(target, env_name)

        obj_names = []
        sources = []
        for src in target['srcs']:
            (proto_src, proto_hdr) = self._proto_gen_files(target['path'], src)

            self._output("%s.Proto(['%s', '%s'], '%s')" % (
                    env_name,
                    proto_src,
                    proto_hdr,
                    self._proto_src_file(target['path'], src)))
            obj_name = "%s_object" % self._generate_variable_name(
                target['path'], src)
            obj_names.append(obj_name)
            self._output(
                "%s = %s.SharedObject(target = '%s' + env['OBJSUFFIX'], "
                "source = '%s')" % (obj_name,
                                    env_name,
                                    proto_src,
                                    proto_src))
            sources.append(proto_src)

        self._output("%s = [%s]" % (self._objs_name(target),
                                    ','.join(obj_names)))
        self._output("%s.Depends(%s, %s)" % (
                env_name, self._objs_name(target), sources))

        self._output("%s = %s.Library('%s', %s)" % (
                self._generate_variable_name(target['path'], target['name']),
                env_name,
                self._file_path(target['path'], target['name']),
                self._objs_name(target)))
        self._output("%s.Depends(%s, %s)" % (
                env_name,
                self._generate_variable_name(target['path'], target['name']),
                self._objs_name(target)))

        self._generate_targets_deps(target,
                    self._generate_variable_name(target['path'], target['name']))
        if (self.options.generate_dynamic or
            target.get('options', {}).get('build_dynamic', 0)):
            self._dynamic_cc_library_rules(target)

    def _proto_java_rules(self, target):
        env_name = self._env_name(target)
        target_key = (target['path'], target['name'])
        self.java_jar_dep_source_files_map[target_key] = []

        for src in target['srcs']:
            src_path = self._proto_src_file(target['path'], src)
            package_folder = self._get_package_name(src_path)
            proto_java_src_package = self._proto_java_gen_file(target['path'], src, package_folder)

            self._output("%s.ProtoJava(['%s'], '%s')" % (
                    env_name,
                    proto_java_src_package,
                    src_path))

            self.java_jar_dep_source_list.append((
                os.path.dirname(proto_java_src_package),
                os.path.join(self.build_dir, target['path']),
                target['name']))
            self.java_jar_dep_source_files_map[target_key].append(
                    proto_java_src_package)

    def _proto_php_rules(self, target):
        env_name = self._env_name(target)
        for src in target['srcs']:
            proto_php_src = self._proto_gen_php_files(target['path'], src)

            self._output("%s.ProtoPhp(['%s'], '%s')" % (
                    env_name,
                    proto_php_src,
                    self._proto_src_file(target['path'], src)))

    def _pre_build_java_jar_rules(self, target):
        jar_path = os.path.join(target['path'], target['name'] + '.jar')
        self.java_class_path_list.append(jar_path)


    def _java_jar_rules_prepare_dep(self, target, new_src):
        env_name = self._env_name(target)
        target_dep_list = targets_dependency_map[target['name']]

        new_dep_source_list = []
        cmd_var = target['name'] + '_cmd_dep_var_'
        dep_cmd_var = ''
        cmd_var_idx = 0
        for dep_src in self.java_jar_dep_source_list:
            dep_target_name = dep_src[2]
            if not dep_target_name in target_dep_list:
                continue
            dep_dir = _relative_path(dep_src[0], dep_src[1])
            new_path = os.path.join(new_src, dep_dir)
            new_dep_source_list.append(new_path)
            cmd_var_id = cmd_var + str(cmd_var_idx)
            if cmd_var_idx == 0:
                dep_cmd_var = cmd_var_id
            if not new_path in self.java_jar_cmd_list:
                self._output('%s = %s.Command("%s", "%s", [Mkdir("%s")])' % (
                        cmd_var_id,
                        env_name,
                        new_path,
                        '',
                        new_path))
                self.cmd_var_list.append(cmd_var_id)
                self.java_jar_cmd_list.append(new_path)
                cmd_var_idx += 1
            cmd_var_id = cmd_var + str(cmd_var_idx)
            cmd_var_idx += 1
            cmd = 'cp %s/*.java %s' % (dep_src[0], new_path)
            self._output('%s = %s.Command("%s/dummy_file_%s", "%s", ["%s"])' % (
                    cmd_var_id,
                    env_name,
                    new_path,
                    cmd_var_idx,
                    dep_src[0],
                    cmd))
            self.cmd_var_list.append(cmd_var_id)

        # depends on the dep files
        if dep_cmd_var:
            for dep in self.targets[(target['path'], target['name'])]['deps']:
                files_list = self.java_jar_dep_source_files_map.get(dep, [])
                if files_list:
                    self._output('%s.Depends(%s, %s)' % (
                            env_name,
                            dep_cmd_var,
                            files_list))

        self._generate_targets_deps(target, self.cmd_var_list)

        self.java_jar_after_dep_source_list = new_dep_source_list

    def _java_jar_rules_compile_src(self,
                                    target,
                                    target_source_list,
                                    new_src,
                                    pack_list,
                                    classes_var_list):
        env_name = self._env_name(target)
        class_root = self._java_jar_gen_class_root(target['path'], target['name'])
        jar_list = self._java_jar_deps_list(target['deps'])
        class_path_list = self.java_class_path_list
        class_path = ':'.join(class_path_list + jar_list)

        new_target_source_list = []
        for src_dir in target_source_list:
            rel_path = _relative_path(src_dir, target['path'])
            pos = rel_path.find('/')
            package = rel_path[pos + 1:]
            new_src_path = os.path.join(new_src, package)
            new_target_source_list.append(new_src_path)

            cmd_var = target['name'] + '_cmd_src_var_'
            cmd_var_idx = 0
            if not new_src_path in self.java_jar_cmd_list:
                cmd_var_id = cmd_var + str(cmd_var_idx)
                self._output('%s = %s.Command("%s", "%s", [Mkdir("%s")])' % (
                        cmd_var_id,
                        env_name,
                        new_src_path,
                        '',
                        new_src_path))
                cmd_var_idx += 1
                self.java_jar_cmd_list.append(new_src_path)
            cmd_var_id = cmd_var + str(cmd_var_idx)
            cmd_var_idx += 1
            cmd = 'cp %s/*.java %s' % (src_dir, new_src_path)
            self._output('%s = %s.Command("%s/dummy_src_file_%s", "%s", ["%s"])' % (
                    cmd_var_id,
                    env_name,
                    new_src_path,
                    cmd_var_idx,
                    src_dir,
                    cmd))
            self.cmd_var_list.append(cmd_var_id)

        if new_target_source_list:
            classes_var = '%s_classes' % (
            self._generate_variable_name(target['path'], target['name']))

            javac_cmd = 'javac'
            if not class_path:
                javac_class_path = ''
            else:
                javac_class_path = ' -classpath ' + class_path
            javac_classes_out = ' -d ' + class_root
            javac_source_path = ' -sourcepath ' + new_src

            no_dup_source_list = []
            for dep_src in self.java_jar_after_dep_source_list:
                if not dep_src in no_dup_source_list:
                    no_dup_source_list.append(dep_src)
            for src in new_target_source_list:
                if not src in no_dup_source_list:
                    no_dup_source_list.append(src)

            source_files_list = []
            for src_dir in no_dup_source_list:
                srcs = os.path.join(src_dir, "*.java")
                source_files_list.append(srcs)

            cmd = javac_cmd + javac_class_path + javac_classes_out + \
                    javac_source_path + " " + " ".join(source_files_list)
            dummy_file = target['name'] + '_dummy_file'
            class_root_dummy = os.path.join(class_root, dummy_file)
            self._output('%s = %s.Command("%s", "%s", ["%s"])' % (
                    classes_var,
                    env_name,
                    class_root_dummy,
                    '',
                    cmd))

            # Find out the java jar explict denpendency
            for dep in self.targets[(target['path'], target['name'])]['deps']:
                dep_java_jar_list = self.java_jar_targets_map.get(dep, None)
                if dep_java_jar_list:
                    self._output("%s.Depends(%s, %s)" % (
                        env_name,
                        classes_var,
                        dep_java_jar_list))

            for cmd in self.cmd_var_list:
                self._output('%s.Depends(%s, %s)' % (
                        env_name,
                        classes_var,
                        cmd))

            self.java_class_path_list.append(class_root)
            classes_var_list.append(classes_var)
            pack_list.append(class_root)

    def _java_jar_rules_make_jar(self, target, pack_list, classes_var_list):
        env_name = self._env_name(target)
        target_base_dir = os.path.join(self.build_dir, target['path'])
        dep_target_list = targets_dependency_map[target['name']]
        self.java_jar_targets_map[(target['path'], target['name'])] = []

        cmd_jar = target['name'] + '_cmd_jar'
        cmd_var = target['name'] + '_cmd_jar_var_'
        cmd_idx = 0
        cmd_var_id = ''
        cmd_list = []
        self.java_jar_var_map[target['name']] = []
        for class_path in pack_list:
            # need to place one dummy file into the source folder for user builder
            build_file = os.path.join(current_source_dir, 'BLADE_ROOT')
            build_file_dst = os.path.join(class_path, 'BLADE_ROOT')
            if not build_file_dst in self.java_jar_cmd_list:
                self._output('%s = %s.Command("%s", "%s", [Copy("%s", "%s")])' % (
                        cmd_jar,
                        env_name,
                        build_file_dst,
                        build_file,
                        build_file_dst,
                        build_file))
                cmd_list.append(cmd_jar)
                self.java_jar_cmd_list.append(build_file_dst)
            for f in self.java_external_pack_files:
                dep_target_name = f[1]
                if not dep_target_name in dep_target_list:
                    continue
                cmd_var_id = cmd_var + str(cmd_idx)
                f_dst = os.path.join(class_path, os.path.basename(f[0]))
                if not f_dst in self.java_jar_cmd_list:
                    self._output('%s = %s.Command("%s", "%s", \
                            [Copy("$TARGET","$SOURCE")])' % (
                                    cmd_var_id,
                                    env_name,
                                    f_dst,
                                    f[0]))
                    self.java_jar_cmd_list.append(f_dst)
                    cmd_list.append(cmd_var_id)
                    cmd_idx += 1
            rel_path = _relative_path(class_path, target_base_dir)
            class_path_name = rel_path.replace('/', '_')
            jar_var = '%s_%s_jar' % (
                    self._generate_variable_name(target['path'], target['name']),
                    class_path_name)
            jar_target = '%s.jar' % (
                    self._file_path(target['path'], target['name']))
            jar_target_object = jar_target + '.jar'
            cmd_remove_var = "cmd_remove_%s" % jar_var
            removed = False
            if (not jar_target in self.java_jar_cmd_list) and (
                os.path.exists(jar_target)):
                self._output('%s = %s.Command("%s", "", [Delete("%s")])' % (
                        cmd_remove_var,
                        env_name,
                        jar_target_object,
                        jar_target))
                removed = True
            self._output('%s = %s.BladeJar(["%s"], "%s")' % (
                    jar_var,
                    env_name,
                    jar_target,
                    build_file_dst))
            self.java_jar_targets_map[(target['path'], target['name'])].append(jar_target)
            self.java_jar_var_map[target['name']].append(jar_var)

            for dep_classes_var in classes_var_list:
                if dep_classes_var:
                    self._output('%s.Depends(%s, %s)' % (
                            env_name, jar_var, dep_classes_var))
            for cmd in cmd_list:
                self._output('%s.Depends(%s, %s)' % (
                        env_name, jar_var, cmd ))
            if removed:
                self._output('%s.Depends(%s, %s)' % (
                        env_name, jar_var, cmd_remove_var))

    def _java_jar_rules(self, target):
        env_name = self._env_name(target)
        self._output("%s = env.Clone()" % env_name)
        class_root = self._java_jar_gen_class_root(target['path'], target['name'])

        # make unique
        self.java_jar_dep_source_list = list(set(self.java_jar_dep_source_list))

        if not class_root in self.java_jar_cmd_list:
            self._output('%s.Command("%s", "%s", [Mkdir("%s")])' % (
                    env_name, class_root, '', class_root))
            self.java_jar_cmd_list.append(class_root)

        target_source_list = []
        for src_dir in target['srcs']:
            java_src = self._java_jar_gen_path(target['path'], src_dir)
            if not java_src in target_source_list:
                target_source_list.append(java_src)

        new_src_dir = ''
        src_dir = target['name'] + '_src'
        new_src_dir = os.path.join(self.build_dir, target['path'], src_dir)
        if not new_src_dir in self.java_jar_cmd_list:
            self._output('%s.Command("%s", "%s", [Mkdir("%s")])' % (
                    env_name,
                    new_src_dir,
                    '',
                    new_src_dir))
            self.java_jar_cmd_list.append(new_src_dir)

        pack_list = []
        classes_var_list = []
        if self.java_jar_dep_source_list:
            self._java_jar_rules_prepare_dep(target, new_src_dir)

        self._java_jar_rules_compile_src(target,
                                         target_source_list,
                                         new_src_dir,
                                         pack_list,
                                         classes_var_list)

        self._java_jar_rules_make_jar(target, pack_list, classes_var_list)


    def _lex_yacc_library_rules(self, target):
        lex_source_file = self._file_path(target['path'], target['srcs'][0])
        lex_cc_file = '%s.cc' % lex_source_file

        lex_flags = []
        if target.get('options', {}).get('recursive', 0):
            lex_flags.append('-R')
        prefix = target.get('options', {}).get('prefix', None)
        if prefix:
            lex_flags.append('-P %s' % prefix)
        self._output(
            "lex_%s = env.CXXFile(LEXFLAGS=%s, target='%s', source='%s');" % (
                self._generate_variable_name(target['path'], target['name']),
                lex_flags, lex_cc_file, lex_source_file))
        yacc_source_file = self._file_path(target['path'], target['srcs'][1])
        yacc_cc_file = '%s.cc' % yacc_source_file
        yacc_hh_file = '%s.hh' % yacc_source_file

        yacc_flags = []
        if prefix:
            yacc_flags.append('-p %s' % prefix)

        self._output(
            "yacc_%s = env.Yacc(YACCFLAGS=%s, target=['%s', '%s'], source='%s');" % (
                self._generate_variable_name(target['path'], target['name']),
                yacc_flags, yacc_cc_file, yacc_hh_file, yacc_source_file))
        self._output("env.Depends(lex_%s, yacc_%s)" % (
                self._generate_variable_name(target['path'], target['name']),
                self._generate_variable_name(target['path'], target['name'])))


        self._output(
            "%s = ['%s', '%s']" % (self._objs_name(target),
                                   lex_cc_file,
                                   yacc_cc_file))
        self._output("%s = env.Library('%s', %s)" % (
                self._generate_variable_name(target['path'], target['name']),
                self._file_path(target['path'], target['name']),
                self._objs_name(target)))

        self._generate_targets_deps(target,
                    self._generate_variable_name(target['path'], target['name']))

        if (self.options.generate_dynamic or
            target.get('options', {}).get('build_dynamic', 0)):
            self._dynamic_cc_library_rules(target)

    def _pre_build_cc_library_rules(self, target):
        target_key = (target['path'], target['name'])
        allow_only_dynamic = True
        build_dynamic = False
        need_static_lib_targets = ['cc_test',
                                   'cc_binary',
                                   'cc_plugin',
                                   'swig_library']
        for key in self.targets.keys():
            if target_key in self.targets[key].get('deps', []) and (
                    self.targets[key].get('type', None) in need_static_lib_targets):
                allow_only_dynamic = False

        if self.options.generate_dynamic or (
                target.get('options', {}).get('build_dynamic', 0)):
            build_dynamic = True

        var_name = self._generate_variable_name(target['path'], target['name'])
        if not allow_only_dynamic:
            self._output(
                'Command("%s", "%s", Copy("$TARGET", "$SOURCE"))' % (
                    self._pre_build_cc_library_build_path(target['path'],
                                                          target['name']),
                    self._pre_build_cc_library_src_path(target['path'],
                                                        target['name'])))
            self._output("%s = env.File('%s')" % (
                    var_name,
                    self._pre_build_cc_library_build_path(target['path'],
                                                          target['name'])))
        if build_dynamic:
            self._output(
                'Command("%s", "%s", Copy("$TARGET", "$SOURCE"))' % (
                    self._pre_build_cc_library_build_path(target['path'],
                                                          target['name'],
                                                          dynamic = 1),
                    self._pre_build_cc_library_src_path(target['path'],
                                                        target['name'],
                                                        dynamic = 1)))
            var_name = self._generate_variable_name(target['path'],
                                                    target['name'],
                                                    "dynamic")
            self._output("%s = env.File('%s')" % (
                    var_name,
                    self._pre_build_cc_library_build_path(target['path'],
                                                          target['name'],
                                                          1)))

    def _gen_rule_rules(self, target):
        var_name = self._generate_variable_name(target['path'], target['name'])
        env_name = self._env_name(target)
        self._output("%s = env.Clone()" % env_name)

        srcs_str = ""
        if not target['srcs']:
            srcs_str = 'time_value'
        else:
            srcs_str = self._srcs_list(target['path'], target['srcs'])
        cmd = target['cmd']
        cmd = cmd.replace("$SRCS", '$SOURCES')
        cmd = cmd.replace("$OUTS", '$TARGETS')
        cmd = cmd.replace("$FIRST_SRC", '$SOURCE')
        cmd = cmd.replace("$FIRST_OUT", '$TARGET')
        cmd = cmd.replace("$BUILD_DIR", self.build_dir)
        self._output('%s = %s.Command([%s], [%s], "%s")' % (
                var_name,
                env_name,
                self._srcs_list(target['path'], target['outs']),
                srcs_str,
                cmd))

        self.gen_rule_files_map[(target['path'], target['name'])] = var_name
        dep_var_list = []
        for i in target['deps']:
            dep_target = self.targets[i]
            if dep_target['type'] == 'system_library':
                continue
            elif dep_target['type'] == 'swig_library':
                dep_var_name = self._generate_variable_name(
                        dep_target['path'], dep_target['name'], 'dynamic_py')
                dep_var_list.append(dep_var_name)
                dep_var_name = self._generate_variable_name(
                        dep_target['path'], dep_target['name'], 'dynamic_java')
                dep_var_list.append(dep_var_name)
            elif dep_target['type'] == 'java_jar':
                dep_var_list += self.java_jar_var_map[dep_target['name']]
            else:
                dep_var_name = self._generate_variable_name(
                        dep_target['path'], dep_target['name'])
                dep_var_list.append(dep_var_name)

        for dep_var_name in dep_var_list:
            self._output("%s.Depends(%s, %s)" % (env_name,
                                                 var_name,
                                                 dep_var_name))

    def _swig_extract_dependency_files(self, src):
        dep = []
        for line in open(src):
            if line.startswith('#include') or line.startswith('%include'):
                line = line.split(' ')[1].strip("""'"\r\n""")
                if not ('<' in line or line in dep):
                    dep.append(line)
        return [i for i in dep if os.path.exists(i)]

    def _swig_library_rules_py(self, target):
        env_name  = self._env_name(target)
        obj_names_py = []
        flag_list = []
        warning = target.get('options', {}).get('cpperraswarn', '')
        flag_list.append(('cpperraswarn', warning))
        self.pyswig_flags = ''
        pyswig_flags = ''
        for flag in flag_list:
            if flag[0] == 'cpperraswarn':
                if flag[1] == 'yes':
                    pyswig_flags += ' -cpperraswarn'
        self.pyswig_flags = pyswig_flags

        builder_name = self._regular_variable_name(target['name']) + '_py_bld'
        builder_alias = self._regular_variable_name(target['name']) + '_py_bld_alias'
        swig_bld_cmd = "swig -python -threads %s -c++ -I%s -o $TARGET $SOURCE" % (
                       pyswig_flags, self.build_dir)

        self._output("%s = Builder(action=MakeAction('%s', "
                "compile_swig_python_message))" % (
                builder_name, swig_bld_cmd))
        self._output('%s.Append(BUILDERS={"%s" : %s})' % (
                env_name, builder_alias, builder_name))

        # setup cppflags
        self._setup_cppflags_from_option(target, env_name)

        dep_files = []
        dep_files_map = {}
        for src in target['srcs']:
            pyswig_src = self._pyswig_gen_file(target['path'], src)
            self._output('%s.%s(["%s"], "%s")' % (
                    env_name,
                    builder_alias,
                    pyswig_src,
                    os.path.join(target['path'],src)))
            obj_name_py = "%s_object" % self._generate_variable_name(
                target['path'], src, 'python')
            obj_names_py.append(obj_name_py)

            self._output(
                "%s = %s.SharedObject(target = '%s' + env['OBJSUFFIX'], "
                "source = '%s')" % (obj_name_py,
                                    env_name,
                                    pyswig_src,
                                    pyswig_src))

            dep_files = self._swig_extract_dependency_files(os.path.join(target['path'], src))
            self._output("%s.Depends('%s', %s)" % (
                         env_name,
                         pyswig_src,
                         dep_files))
            dep_files_map[os.path.join(target['path'], src)] = dep_files

        objs_name = self._objs_name(target)
        objs_name_py = objs_name + "_py"

        self._output("%s = [%s]" % (
                objs_name_py, ','.join(obj_names_py)))

        target_path = self._file_path(target['path'], target['name'])
        target_lib = os.path.basename(target_path)
        if not target_lib.startswith('_'):
            target_lib = '_' + target_lib
        target_path_py = os.path.join(
            os.path.dirname(target_path), target_lib)

        (link_all_symbols_lib_list,
         lib_list) = self._static_deps_list(target['deps'])
        lib_str = "LIBS=[]"
        if lib_list:
            lib_str = 'LIBS=[%s]' % ','.join(lib_list)
        if link_all_symbols_lib_list:
            whole_link_flags = ["-Wl,--whole-archive"]
            for i in link_all_symbols_lib_list:
                whole_link_flags.append(i[0])
            whole_link_flags.append('-Wl,--no-whole-archive')
            self._output(
                '%s.Append(LINKFLAGS=%s)' % (env_name, whole_link_flags))

        if target['srcs'] or target['deps']:
            self._output('%s.Append(LINKFLAGS=["-fPIC"])'
                         % env_name)
            self._output("%s = %s.SharedLibrary('%s', %s, %s, SHLIBPREFIX = '')" % (
                    self._generate_variable_name(target['path'],
                                                 target['name'],
                                                 'dynamic_py'),
                    env_name,
                    target_path_py,
                    objs_name_py,
                    lib_str))

            self._generate_targets_deps(target,
                    self._generate_variable_name(target['path'],
                                                 target['name'],
                                                 'dynamic_py'))

        for i in link_all_symbols_lib_list:
            self._output("%s.Depends(%s, %s)" % (
                    env_name,
                    self._generate_variable_name(
                        target['path'], target['name'], 'dynamic_py'), i[1]))
        return dep_files_map

    def _swig_library_rules_java_helper(self,
                                        target,
                                        dep_outdir,
                                        bld_jar,
                                        lib_packed,
                                        out_dir,
                                        builder_alias,
                                        dep_files_map):
        depend_outdir = dep_outdir
        build_jar = bld_jar
        java_lib_packed = lib_packed
        env_name = self._env_name(target)
        out_dir_dummy = os.path.join(out_dir, 'dummy_file')
        obj_names_java = []

        # Add java path for building lower version gcc
        if self.java_inc:
            self._output('%s.Append(CPPPATH=%s)' % (env_name, self.java_inc))

        dep_files = []
        target_key = (target['path'], target['name'])
        self.java_jar_dep_source_files_map[target_key] = []
        for src in target['srcs']:
            javaswig_src = self._javaswig_gen_file(target['path'], src)
            javaswig_var = self._regular_variable_name(javaswig_src)
            self._output("%s = %s.%s(['%s'], '%s')" % (
                    javaswig_var,
                    env_name,
                    builder_alias,
                    javaswig_src,
                    os.path.join(target['path'], src)))
            self.java_jar_dep_source_files_map[target_key].append(javaswig_src)
            if depend_outdir:
                self._output('%s.Depends(%s, "%s")' % (
                        env_name,
                        javaswig_var,
                        out_dir_dummy))
            self.cmd_var_list.append(javaswig_var)

            obj_name_java = "%s_object" % self._generate_variable_name(
                    target['path'], src, 'java')
            obj_names_java.append(obj_name_java)

            self._output(
                    "%s = %s.SharedObject(target = '%s' + env['OBJSUFFIX'], "
                    "source = '%s')" % (
                            obj_name_java,
                            env_name,
                            javaswig_src,
                            javaswig_src))

            dep_key = os.path.join(target['path'], src)
            if dep_key in dep_files_map.keys():
                dep_files = dep_files_map[dep_key]
            else:
                dep_files = self._swig_extract_dependency_files(dep_key)
            self._output("%s.Depends('%s', %s)" % (
                         env_name,
                         javaswig_src,
                         dep_files))

        objs_name = self._objs_name(target)
        objs_name_java = objs_name + "_java"
        self._output("%s = [%s]" % (objs_name_java,
                                    ','.join(obj_names_java)))

        target_path = self._file_path(target['path'], target['name'])
        target_path_java = target_path + '_java'

        (link_all_symbols_lib_list,
         lib_list) = self._static_deps_list(target['deps'])
        lib_str = "LIBS=[]"
        if lib_list:
            lib_str = 'LIBS=[%s]' % ','.join(lib_list)

        if target['srcs'] or target['deps']:
            self._output("%s = %s.SharedLibrary('%s', %s, %s)" % (
                    self._generate_variable_name(target['path'],
                                                 target['name'],
                                                 'dynamic_java'),
                    env_name,
                    target_path_java,
                    objs_name_java,
                    lib_str))

        for i in link_all_symbols_lib_list:
            self._output("%s.Depends(%s, %s)" % (
                    env_name,
                    self._generate_variable_name(
                        target['path'], target['name'], 'dynamic_java'), i[1]))
        if build_jar and java_lib_packed:
            lib_dir = os.path.dirname(target_path_java)
            lib_name = os.path.basename(target_path_java)
            lib_name = 'lib%s.so' %lib_name
            self.java_external_pack_files.append((
                    os.path.join(lib_dir,lib_name),
                    target['name']))


    def _swig_library_rules_java(self, target, dep_files_map):
        env_name = self._env_name(target)
        build_jar = False
        java_lib_packed = False

        # Append -fno-strict-aliasing flag to cxxflags and cppflags
        self._output('%s.Append(CPPFLAGS = ["-fno-strict-aliasing"])' % env_name)
        if target.get('options', {}).get('generate_java', False):
            build_jar = True

        flag_list = []
        warning = target.get('options', {}).get('cpperraswarn', '')
        flag_list.append(('cpperraswarn', warning))
        java_package = target.get('options', {}).get('java_package', '')
        flag_list.append(('package', java_package))
        java_lib_packed = target.get('options', {}).get('java_lib_packed', 0)
        flag_list.append(('java_lib_packed', java_lib_packed))
        self.javaswig_flags = ''
        javaswig_flags = ''
        depend_outdir = False
        out_dir = os.path.join(self.build_dir, target['path'])
        for flag in flag_list:
            if flag[0] == 'cpperraswarn':
                if flag[1] == 'yes':
                    javaswig_flags += ' -cpperraswarn'
            if flag[0] == 'java_lib_packed':
                if flag[1]:
                    java_lib_packed = True
            if flag[0] == 'package':
                if flag[1]:
                    javaswig_flags += ' -package %s' % flag[1]
                    package_dir = flag[1].replace('.', '/')
                    out_dir = os.path.join(self.build_dir,
                            target['path'], package_dir)
                    out_dir_dummy = os.path.join(out_dir, 'dummy_file')
                    javaswig_flags += ' -outdir %s' % out_dir
                    swig_outdir_cmd = 'swig_out_cmd_var'
                    if not os.path.exists(out_dir):
                        depend_outdir = True
                        self._output('%s = %s.Command("%s", "%s", [Mkdir("%s")])' % (
                                swig_outdir_cmd,
                                env_name,
                                out_dir_dummy,
                                '',
                                out_dir))
                        self.cmd_var_list.append(swig_outdir_cmd)
                    if build_jar:
                        self.java_jar_dep_source_list.append((
                                out_dir,
                                os.path.join(self.build_dir, target['path']),
                                target['name']))
        self.javaswig_flags = javaswig_flags

        target_name = self._regular_variable_name(target['name'])
        builder_name = target_name + '_java_bld'
        builder_alias = target_name + '_java_bld_alias'
        swig_bld_cmd = "swig -java %s -c++ -I%s -o $TARGET $SOURCE" % (
                       javaswig_flags, self.build_dir)

        self._output("%s = Builder(action=MakeAction('%s', "
                "compile_swig_java_message))" % (
                builder_name, swig_bld_cmd))
        self._output('%s.Append(BUILDERS={"%s" : %s})' % (
                env_name, builder_alias, builder_name))
        self._swig_library_rules_java_helper(target, depend_outdir, build_jar,
                                             java_lib_packed, out_dir,
                                             builder_alias, dep_files_map)

    def _swig_library_rules_php(self, target, dep_files_map):
        env_name  = self._env_name(target)
        obj_names_php = []
        flag_list = []
        warning = target.get('options', {}).get('cpperraswarn', '')
        flag_list.append(('cpperraswarn', warning))
        self.phpswig_flags = ''
        phpswig_flags = ''
        for flag in flag_list:
            if flag[0] == 'cpperraswarn':
                if flag[1] == 'yes':
                    phpswig_flags += ' -cpperraswarn'
        self.phpswig_flags = phpswig_flags

        builder_name = '%s_php_bld' % self._regular_variable_name(target['name'])
        builder_alias = '%s_php_bld_alias' % self._regular_variable_name(target['name'])
        swig_bld_cmd = "swig -php %s -c++ -I%s -o $TARGET $SOURCE" % (
                       phpswig_flags, self.build_dir)

        self._output("%s = Builder(action=MakeAction('%s', "
                "compile_swig_php_message))" % (
                builder_name, swig_bld_cmd))
        self._output('%s.Append(BUILDERS={"%s" : %s})' % (
                env_name, builder_alias, builder_name))

        if self.php_inc:
            self._output("%s.Append(CPPPATH=%s)" % (env_name, self.php_inc))
        dep_files = []
        dep_files_map = {}
        for src in target['srcs']:
            phpswig_src = self._phpswig_gen_file(target['path'], src)
            self._output('%s.%s(["%s"], "%s")' % (
                    env_name,
                    builder_alias,
                    phpswig_src,
                    os.path.join(target['path'],src)))
            obj_name_php = "%s_object" % self._generate_variable_name(
                target['path'], src, 'php')
            obj_names_php.append(obj_name_php)

            self._output(
                "%s = %s.SharedObject(target = '%s' + env['OBJSUFFIX'], "
                "source = '%s')" % (obj_name_php,
                                    env_name,
                                    phpswig_src,
                                    phpswig_src))

            dep_key = os.path.join(target['path'], src)
            if dep_key in dep_files_map.keys():
                dep_files = dep_files_map[dep_key]
            else:
                dep_files = self._swig_extract_dependency_files(dep_key)
            self._output("%s.Depends('%s', %s)" % (
                         env_name,
                         phpswig_src,
                         dep_files))

        objs_name = self._objs_name(target)
        objs_name_php = "%s_php" % objs_name

        self._output("%s = [%s]" % (objs_name_php, ','.join(obj_names_php)))

        target_path = self._file_path(target['path'], target['name'])
        target_lib = os.path.basename(target_path)
        target_path_php = os.path.join(os.path.dirname(target_path), target_lib)

        (link_all_symbols_lib_list,
         lib_list) = self._static_deps_list(target['deps'])
        lib_str = "LIBS=[]"
        if lib_list:
            lib_str = 'LIBS=[%s]' % ','.join(lib_list)

        if target['srcs'] or target['deps']:
            self._output('%s.Append(LINKFLAGS=["-fPIC"])'
                         % env_name)
            self._output("%s = %s.SharedLibrary('%s', %s, %s, SHLIBPREFIX = '')" % (
                    self._generate_variable_name(target['path'], target['name']),
                    env_name,
                    target_path_php,
                    objs_name_php,
                    lib_str))

            self._generate_targets_deps(target,
                    self._generate_variable_name(target['path'], target['name']))

        for i in link_all_symbols_lib_list:
            self._output("%s.Depends(%s, %s)" % (
                    env_name,
                    self._generate_variable_name(target['path'], target['name']), i[1]))

    def _swig_library_rules(self, target):
        dep_files_map = {}
        dep_files_map = self._swig_library_rules_py(target)
        if self.options.generate_java or (
                target.get('options', {}).get('generate_java', False)):
            self._swig_library_rules_java(target, dep_files_map)
        if self.options.generate_php:
            if not self.php_inc:
                _error_exit("failed to build //%s:%s, please install php modules" % (
                        target['path'], target['name']))
            else:
                self._swig_library_rules_php(target, dep_files_map)

    def _resource_library_rules(self, target):
        env_name = self._env_name(target)
        (out_dir, res_file_name) = self._resource_library_rules_helper(target)

        target['options']['res_srcs'] = []
        for src in target['srcs']:
            src_path = os.path.join(target['path'], src)
            src_base = os.path.basename(src_path)
            src_base_name = self._regular_variable_name(src_base) + '.c'
            new_src_path = os.path.join(out_dir, src_base_name)
            cmd_bld = self._regular_variable_name(new_src_path) + '_bld'
            self._output('%s = %s.ResourceFile("%s", "%s")' % (
                         cmd_bld, env_name, new_src_path, src_path))
            target['options']['res_srcs'].append(new_src_path)

        self._resource_library_rules_objects(target)

        self._output("%s = %s.Library('%s', %s)" % (
                self._generate_variable_name(target['path'], target['name']),
                env_name,
                self._file_path(target['path'], target['name']),
                self._objs_name(target)))

        self._generate_targets_deps(target,
                    self._generate_variable_name(target['path'], target['name']))

        if (self.options.generate_dynamic or
            target.get('options', {}).get('build_dynamic', 0)):
            self._dynamic_cc_library_rules(target)

    def _resource_library_rules_objects(self, target):
        env_name = self._env_name(target)
        objs_name = self._objs_name(target)

        self._setup_cppflags_from_option(target, env_name)

        objs = []
        res_srcs = target.get('options', {}).get('res_srcs', [])
        res_objects = {}
        path = target['path']
        for src in res_srcs:
            base_src_name = self._regular_variable_name(os.path.basename(src))
            src_name = base_src_name + '_' + target['name'] + '_res'
            if src_name not in res_objects:
                res_objects[src_name] = (
                        "%s_%s_object" % (
                                base_src_name,
                                self._regular_variable_name(target['name'])))
                target_path = os.path.join(self.build_dir,
                                               path,
                                               target['name'] + '.objs',
                                               base_src_name)
                self._output(
                        "%s = %s.SharedObject(target = '%s' + env['OBJSUFFIX']"
                        ", source = '%s')" % (res_objects[src_name],
                                              env_name,
                                              target_path,
                                              src))
            objs.append(res_objects[src_name])
        self._output('%s = [%s]' % (objs_name, ','.join(objs)))

    def _resource_library_rules_helper(self, target):
        env_name = self._env_name(target)
        out_dir = os.path.join(self.build_dir, target['path'])
        res_name = self._regular_variable_name(target['name'])
        res_file_name = res_name
        res_file_header = res_file_name + '.h'
        res_header_path = os.path.join(out_dir, res_file_header)

        src_list = []
        for src in target['srcs']:
            src_path = os.path.join(target['path'], src)
            src_list.append(src_path)

        cmd_bld = res_name + '_header_cmd_bld'
        self._output('%s = %s.ResourceHeader("%s", %s)' % (
                     cmd_bld, env_name, res_header_path, src_list))

        return (out_dir, res_file_name)

    def _generate_targets_deps(self, target, files):
        """Generates deps that two targets don't have scons dependency but needed.

        1. gen_rule

        """
        env_name = self._env_name(target)
        files = _var_to_list(files)
        files_str = ",".join(["%s" % f for f in files])
        deps = target['deps']
        for d in deps:
            dep_target = self.targets[d]
            if dep_target['type'] == 'gen_rule':
                srcs_list = self.gen_rule_files_map[(dep_target['path'], dep_target['name'])]
                if srcs_list:
                    self._output("%s.Depends([%s], [%s])" % (
                        env_name,
                        files_str,
                        srcs_list))

    def output(self):
        try:
            os.remove("blade-bin")
        except os.error:
            pass
        os.symlink(os.path.abspath(self.build_dir), "blade-bin")
        self._output(
            r"""
import os
import subprocess
import sys
import signal
import time
import socket
import glob
import math


def generate_resource_header(target, source, env):
    res_header_path = str(target[0])

    if not os.path.exists(os.path.dirname(res_header_path)):
        os.mkdir(os.path.dirname(res_header_path))
    f = open(res_header_path, 'w')

    print >>f, '// This file was automatically generated by blade'
    print >>f, '#ifdef __cplusplus\nextern "C" {\n#endif\n'
    for s in source:
        var_name = str(s)
        for i in [',', '-', '/', '.', '+']:
            var_name = var_name.replace(i, '_')
        print >>f, 'extern const char RESOURCE_%s[%d];' % (var_name, s.get_size())
    print >>f, '\n#ifdef __cplusplus\n}\n#endif\n'
    f.close()


def generate_resource_file(target, source, env):
    src_path = str(source[0])
    new_src_path = str(target[0])
    cmd = "xxd -i %s | sed 's/unsigned char /const char RESOURCE_/g' > %s" % (
           src_path, new_src_path)
    os.popen(cmd)
""")

        if self.options.verbose:
            self._output("option_verbose = True")
        else:
            self._output("option_verbose = False")

        self._output(
                r"""
def MakeAction(cmd, cmdstr):
    if option_verbose:
        return Action(cmd)
    else:
        return Action(cmd, cmdstr)
""")
        cache_class_str = '' if self.ccache_mgr.is_ccache_installed() else scache_manager_class_str
        self._output(cache_class_str)

        self._output((
                """if not os.path.exists('%s'):
    os.mkdir('%s')""") % (self.build_dir, self.build_dir))

        version_cpp_template = string.Template("""
version_cpp = open('$filename', 'w')
print >>version_cpp, 'extern "C" {'
print >>version_cpp, 'namespace binary_version {'
print >>version_cpp, 'extern const char kBuildType[] = "$buildtype";'
print >>version_cpp, 'extern const char kBuildTime[] = "%s";' % time.asctime()
print >>version_cpp, 'extern const char kBuilderName[] = "%s";' % os.getenv('USER')
print >>version_cpp, (
    'extern const char kHostName[] = "%s";' % socket.gethostname())
print >>version_cpp, 'extern const char kCompiler[] = "$compiler";'
print >>version_cpp, '}'
print >>version_cpp, '}'
version_cpp.close()
env_version = Environment(ENV = os.environ)
env_version.Append(SHCXXCOMSTR = 'Version information updated')
env_version.Append(CPPFLAGS = '-m$m')
version_obj = env_version.SharedObject('$filename')
""")
        self._output(version_cpp_template.substitute(
                filename = "%s/version.cpp" % self.build_dir,
                compiler = "GCC %s" % self.gcc_version,
                buildtype = "%s" % self.options.profile,
                m = self.options.m))

        self._output("VariantDir('%s', '.', duplicate=0)" % self.build_dir)

        toolchain_dir = os.environ.get('TOOLCHAIN_DIR', '')
        if toolchain_dir and not toolchain_dir.endswith('/'):
            toolchain_dir += '/'
        cpp_str = toolchain_dir + os.environ.get('CPP', 'cpp')
        cc_str = toolchain_dir + os.environ.get('CC', 'gcc')
        cxx_str = toolchain_dir + os.environ.get('CXX', 'g++')
        ld_str = toolchain_dir + os.environ.get('LD', 'g++')

        (self.warning_cppflags,
         self.warning_cxxflags) = self._get_warning_flags(cpp_str)

        (self.err_cflags,
         self.err_cppflags,
         self.err_cxxflags) = self._get_error_flags(cpp_str)

        self.flags_except_warning += ["-m%s" % self.options.m, "-mcx16", "-pipe"]

        linkflags = ["-m%s" % self.options.m]
        if self.options.profile == 'debug':
            self.flags_except_warning += ["-ggdb3", "-fstack-protector"]
        elif self.options.profile == 'release':
            self.flags_except_warning += ["-g", "-DNDEBUG"]
        self.flags_except_warning += ["-D_FILE_OFFSET_BITS=64"]

        if self.options.gprof:
            self.flags_except_warning.append('-pg')
            linkflags.append('-pg')

        if self.options.gcov:
            self.flags_except_warning.append('--coverage')
            linkflags.append('--coverage')

        self.flags_except_warning = self._filter_out_invalid_flags(
                self.flags_except_warning, 'cpp', cpp_str)

        self._output("os.environ['LC_ALL'] = 'C'")

        cc_env_str = ''

        if self.ccache_mgr.is_ccache_installed():
            cc_env_str = 'CC="ccache %s", CXX="ccache %s",' % (cc_str, cxx_str)
        else:
            cc_env_str = 'CC="%s", CXX="%s",' % (cc_str, cxx_str)
        self._output("""
env = Environment(ENV=os.environ, %s CPPPATH=['thirdparty', '%s', '%s'],
CPPFLAGS=%s, CFLAGS=%s, CXXFLAGS=%s, LINK="%s", LINKFLAGS=%s)
""" % (cc_env_str, self.build_dir, self.python_inc,
       self.warning_cppflags + self.flags_except_warning,
       self.warning_cflags,
       self.warning_cxxflags,
       ld_str, linkflags))

        self._output("""
env_with_error = Environment(ENV=os.environ, %s CPPPATH=['thirdparty', '%s', '%s'],
CPPFLAGS=%s, CFLAGS=%s, CXXFLAGS=%s, LINK="%s", LINKFLAGS=%s)
""" % (cc_env_str, self.build_dir, self.python_inc,
       self.warning_cppflags + self.err_cppflags + self.flags_except_warning,
       self.warning_cflags + self.err_cflags,
       self.warning_cxxflags + self.err_cxxflags,
       ld_str, linkflags))

        self._output("""
env_no_warning = Environment(ENV=os.environ, %s CPPPATH=['thirdparty', '%s', '%s'],
CPPFLAGS=%s, CFLAGS=[], CXXFLAGS=[], LINK="%s", LINKFLAGS=%s)
""" % (cc_env_str, self.build_dir, self.python_inc,
       self.flags_except_warning, ld_str, linkflags))

        envs = ["env", "env_with_error", "env_no_warning"]
        if self.options.cache_dir:
            if not self.ccache_mgr.is_ccache_installed():
                self._output("CacheDir('%s')" % self.options.cache_dir)
                self._output("print('Blade: Using cache directory %s')" % (
                        self.options.cache_dir))
                if self.options.cache_size != -1:
                    self._output("scache_manager = ScacheManager('%s', cache_limit = %s)" % (
                            self.options.cache_dir, self.options.cache_size))
                    self._output("Progress(scache_manager, interval = 100)")

        self.ccache_mgr.setup_ccache_env(envs)

        md5_ts_str = 'MD5-timestamp'
        for env in envs:
            self._output("%s.Decider('%s')\n" % (env, md5_ts_str))

        self._output(
        """
colors = {}
colors['red']    = '\033[1;31m'
colors['green']  = '\033[1;32m'
colors['yellow'] = '\033[1;33m'
colors['blue']   = '\033[1;34m'
colors['purple'] = '\033[1;35m'
colors['cyan']   = '\033[1;36m'
colors['white']  = '\033[1;37m'
colors['gray']   = '\033[1;38m'
colors['end']    = '\033[0m'
""")

        if not self.options.color:
            self._output(
                """
for key, value in colors.iteritems():
    colors[key] = ''
""")

        self._output(
            """
def error_colorize(message):
    colored_message = ""
    errors = [": error:", ": fatal error:", ": undefined reference to"]
    warnings = [": warning:", ": note: "]
    for t in message.splitlines(True):
        color = 'cyan'
        for w in warnings:
            if w in t:
                color = 'yellow'
                break
        for w in errors:
            if w in t:
                color = 'red'
                break
        colored_message += "%s%s%s" % (colors[color], t, colors['end'])
    return colored_message

def echospawn( sh, escape, cmd, args, env ):
    # convert env from unicode strings
    asciienv = {}
    for key, value in env.iteritems():
        asciienv[key] = str(value)

    cmdline = ' '.join(args)
    p = subprocess.Popen(
        cmdline,
        env=asciienv,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        shell=True,
        universal_newlines=True)
    (stdout, stderr) = p.communicate()

    if p.returncode:
        if p.returncode != -signal.SIGINT:
            sys.stdout.write(error_colorize(stdout))
            sys.stderr.write(error_colorize(stderr))
    else:
        if stderr:
            sys.stderr.write(error_colorize(stderr))
            sys.stdout.write(error_colorize(stdout))
        else:
            sys.stdout.write(stdout)

    return p.returncode
""")
        echospawn_str = 'echospawn'
        for env in envs:
            self._output("%s['SPAWN'] = %s\n" % (env, echospawn_str))

        self._output(
                """
compile_proto_cc_message = '%sCompiling %s$SOURCE%s to cc source%s' % \
    (colors['cyan'], colors['purple'], colors['cyan'], colors['end'])

compile_proto_java_message = '%sCompiling %s$SOURCE%s to java source%s' % \
    (colors['cyan'], colors['purple'], colors['cyan'], colors['end'])

compile_proto_php_message = '%sCompiling %s$SOURCE%s to php source%s' % \
    (colors['cyan'], colors['purple'], colors['cyan'], colors['end'])

compile_resource_header_message = '%sGenerating resource header %s$TARGET%s%s' % \
    (colors['cyan'], colors['purple'], colors['cyan'], colors['end'])

compile_resource_message = '%sCompiling %s$SOURCE%s as resource file%s' % \
    (colors['cyan'], colors['purple'], colors['cyan'], colors['end'])

compile_source_message = '%sCompiling %s$SOURCE%s%s' % \
    (colors['cyan'], colors['purple'], colors['cyan'], colors['end'])

link_program_message = '%sLinking Program %s$TARGET%s%s' % \
    (colors['green'], colors['purple'], colors['green'], colors['end'])

link_library_message = '%sCreating Static Library %s$TARGET%s%s' % \
    (colors['green'], colors['purple'], colors['green'], colors['end'])

ranlib_library_message = '%sRanlib Library %s$TARGET%s%s' % \
    (colors['green'], colors['purple'], colors['green'], colors['end']) \

link_shared_library_message = '%sLinking Shared Library %s$TARGET%s%s' % \
    (colors['green'], colors['purple'], colors['green'], colors['end'])

compile_java_jar_message = '%sGenerating java jar %s$TARGET%s%s' % \
    (colors['cyan'], colors['purple'], colors['cyan'], colors['end'])

compile_yacc_message = '%sYacc %s$SOURCE%s to $TARGET%s' % \
    (colors['cyan'], colors['purple'], colors['cyan'], colors['end'])

compile_swig_python_message = '%sCompiling %s$SOURCE%s to python source%s' % \
    (colors['cyan'], colors['purple'], colors['cyan'], colors['end'])

compile_swig_java_message = '%sCompiling %s$SOURCE%s to java source%s' % \
    (colors['cyan'], colors['purple'], colors['cyan'], colors['end'])

compile_swig_php_message = '%sCompiling %s$SOURCE%s to php source%s' % \
    (colors['cyan'], colors['purple'], colors['cyan'], colors['end'])
""")

        env_message = """
    CXXCOMSTR = compile_source_message,
    CCCOMSTR = compile_source_message,
    SHCCCOMSTR = compile_source_message,
    SHCXXCOMSTR = compile_source_message,
    ARCOMSTR = link_library_message,
    RANLIBCOMSTR = ranlib_library_message,
    SHLINKCOMSTR = link_shared_library_message,
    LINKCOMSTR = link_program_message,
    JAVACCOMSTR = compile_source_message
"""

        if not self.options.verbose:
            for env in envs:
                self._output("%s.Append(%s)\n" % (env, env_message))

        builder_list = []
        self._output("time_value = Value('%s')" %  time.asctime())
        self._output(
            "proto_bld = Builder(action = MakeAction('thirdparty/protobuf/bin/protoc "
            "--proto_path=. -I. -Ithirdparty -I=`dirname $SOURCE` "
            "--cpp_out=%s "
            "$SOURCE', compile_proto_cc_message))" % self.build_dir)
        builder_list.append("BUILDERS = {'Proto' : proto_bld}")

        self._output(
            "proto_java_bld = Builder(action = MakeAction('thirdparty/protobuf/bin/protoc --proto_path=. "
            "--proto_path=thirdparty --java_out=%s/`dirname $SOURCE` "
            "$SOURCE', compile_proto_java_message))" % self.build_dir)
        builder_list.append("BUILDERS = {'ProtoJava' : proto_java_bld}")

        self._output(
            "proto_php_bld = Builder(action = MakeAction('thirdparty/protobuf/bin/protoc "
            "--proto_path=. "
            "--plugin=protoc-gen-php=thirdparty/Protobuf-PHP/protoc-gen-php.php "
            "-I. -Ithirdparty -Ithirdparty/Protobuf-PHP/library -I=`dirname $SOURCE` "
            "--php_out=%s/`dirname $SOURCE` "
            "$SOURCE', compile_proto_php_message))" % self.build_dir)
        builder_list.append("BUILDERS = {'ProtoPhp' : proto_php_bld}")

        self._output(
                     r"""
blade_jar_bld = Builder(action = MakeAction('jar cf $TARGET -C `dirname $SOURCE` .',
    compile_java_jar_message))

yacc_bld = Builder(action = MakeAction('bison $YACCFLAGS -d -o $TARGET $SOURCE',
    compile_yacc_message))

resource_header_bld = Builder(action = MakeAction(generate_resource_header,
    compile_resource_header_message))

resource_file_bld = Builder(action = MakeAction(generate_resource_file,
    compile_resource_message))
""")
        builder_list.append("BUILDERS = {'BladeJar' : blade_jar_bld}")
        builder_list.append("BUILDERS = {'Yacc' : yacc_bld}")
        builder_list.append("BUILDERS = {'ResourceHeader' : resource_header_bld}")
        builder_list.append("BUILDERS = {'ResourceFile' : resource_file_bld}")

        for builder in builder_list:
            for env in envs:
                self._output("%s.Append(%s)\n" % (env, builder))

        target_types_no_warning = ['swig_library']

        cc_target_types = ["cc_library",
                           "cc_binary",
                           "dynamic_cc_binary",
                           "cc_test",
                           "dynamic_cc_test",
                           "cc_plugin"]

        self._env_rules(cc_target_types, target_types_no_warning)
        self._objects_rules(cc_target_types)
        for k in self._topological_sort(self.targets):
            target = self.targets[k]
            if target['type'] == 'cc_binary':
                self._cc_binary_rules(target)
            elif target['type'] == 'cc_test':
                self._cc_test_rules(target)
            elif target['type'] == 'dynamic_cc_test':
                self._dynamic_cc_test_rules(target)
            elif target['type'] == 'dynamic_cc_binary':
                self._dynamic_cc_binary_rules(target)
            elif target['type'] == 'cc_library':
                self._cc_library_rules(target)
            elif target['type'] == 'pre_build_cc_library':
                self._pre_build_cc_library_rules(target)
            elif target['type'] == 'proto_library':
                self._proto_library_rules(target)
            elif target['type'] == 'lex_yacc_library':
                self._lex_yacc_library_rules(target)
            elif target['type'] == 'gen_rule':
                self._gen_rule_rules(target)
            elif target['type'] == 'cc_plugin':
                self._cc_plugin_rules(target)
            elif target['type'] == 'swig_library':
                self._swig_library_rules(target)
            elif target['type'] == 'java_jar':
                self._java_jar_rules(target)
            elif target['type'] == 'pre_build_java_jar':
                self._pre_build_java_jar_rules(target)
            elif target['type'] == 'resource_library':
                self._resource_library_rules(target)
        self.scons_file.close()

#------------------------------------------------------------------------------
# >>>>>>                  Commandline Options Parser                     <<<<<<
#------------------------------------------------------------------------------

class CmdOptions:
    def __init__(self):
        (self.options, self.args) = self._cmd_parse()
        if (self.options.profile != 'debug' and
            self.options.profile != 'release'):
            _error_exit("--profile must be 'debug' or 'release'.")

        if self.options.m is None:
            self.options.m = self._arch_bits()
        else:
            if not (self.options.m == "32" or self.options.m == "64"):
                _error_exit("--m must be '32' or '64'")

            # TODO(phongchen): cross compile checking
            if self.options.m == "64" and platform.machine() != "x86_64":
                _error_exit("Sorry, 64-bit environment is required for "
                            "building 64-bit targets.")

        if self.options.color == "yes":
            self.options.color = True;
        elif self.options.color == "no":
            self.options.color = False;
        elif self.options.color == "auto" or  self.options.color is None:
            self.options.color = (sys.stdout.isatty() and
                                 os.environ['TERM'] not in ('emacs', 'dumb'))
        else:
            _error_exit("--color can only be yes, no or auto.")

        if self.options.cache_dir is None:
            self.options.cache_dir = os.environ.get('BLADE_CACHE_DIR')
        if self.options.cache_dir:
            self.options.cache_dir = os.path.expanduser(self.options.cache_dir)

        if self.options.cache_size is None:
            self.options.cache_size = os.environ.get('BLADE_CACHE_SIZE')

        if self.options.cache_size == "unlimited":
            self.options.cache_size = -1
        if self.options.cache_size is None:
            self.options.cache_size = 2 * 1024 * 1024 * 1024
        else:
            self.options.cache_size = int(self.options.cache_size) * 1024 * 1024 * 1024


    def _cmd_parse(self):
        cmd_parser = OptionParser('%prog [options] target1[ target2...]',
                                  add_help_option=False)

        # Build profiles
        cmd_parser.add_option(
            "-h", "--help", dest = "help",
            action = "help", default = False,
            help = "Show help message and exit. For any questions, "
            "please refer to Blade wiki page: "
            "http://infra.soso.oa.com/mediawiki/index.php/%E5%88%86%E7%B1%BB:Blade")
        cmd_parser.add_option("-m",
                              dest = "m",
                              help = ("Generate code for a 32-bit(-m32) or "
                                      "64-bit(-m64) environment, "
                                      "default is autodetect."))
        cmd_parser.add_option("-p",
                              "--profile",
                              dest = "profile",
                              default = "release",
                              help = ("Build profile: debug or release, "
                                      "default is release."))

        # Actions
        cmd_parser.add_option(
            "-c", "--clean", dest = "clean",
            action = "store_true", default = False,
            help = "Clean up by removing all target files for which "
            "a construction command is specified.")
        cmd_parser.add_option(
            "--generate-scons-only", dest = "scons_only",
            action = "store_true", default = False,
            help = "Generate scons script for debug purpose.")
        cmd_parser.add_option(
            "-t", "--test", dest = "test",
            action = "store_true", default = False,
            help = "Run all testing targets after successful build.")

        cmd_parser.add_option(
            "--testargs", dest = "testargs", type = "string",
            help = "Command line arguments to be passed to tests.")

        cmd_parser.add_option(
            "-k", "--keep-going", dest = "keep_going",
            action = "store_true", default = False,
            help = "Continue as much as possible after an error.")

        # Options
        cmd_parser.add_option(
            "-j", "--jobs", dest = "jobs", type = "int", default = 1,
            help = ("Specifies the number of jobs (commands) to "
                    "run simultaneously."))
        cmd_parser.add_option(
            "--cache-dir", dest = "cache_dir", type = "string",
            help = "Specifies location of shared cache directory.")
        cmd_parser.add_option(
            "--cache-size", dest = "cache_size", type = "string",
            help = "Specifies cache size of shared cache directory in Gigabytes."
                   "'unlimited' for unlimited. ")
        cmd_parser.add_option(
            "--verbose", dest = "verbose", action = "store_true",
            default = False, help = "Show all details.")
        cmd_parser.add_option(
            "--color", dest = "color",
            default = "auto",
            help = "Enable color: yes, no or auto, default is auto.")

        cmd_parser.add_option(
            "--generate-dynamic", dest = "generate_dynamic",
            action = "store_true", default = False,
            help = "Generate dynamic libraries.")

        cmd_parser.add_option(
            "--generate-java", dest = "generate_java",
            action = "store_true", default = False,
            help = "Generate java files for proto_library and swig_library.")

        cmd_parser.add_option(
            "--generate-php", dest = "generate_php",
            action = "store_true", default = False,
            help = "Generate php files for proto_library and swig_library.")

        cmd_parser.add_option(
            "--gprof", dest = "gprof",
            action = "store_true", default = False,
            help = "Add build options to support GNU gprof.")

        cmd_parser.add_option(
            "--gcov", dest = "gcov",
            action = "store_true", default = False,
            help = "Add build options to support GNU gcov to do coverage test.")
        return cmd_parser.parse_args()


    def _arch_bits(self):
        if 'x86_64' == platform.machine():
            return '64'
        else:
            return '32'


    def get_args(self):
        return self.args


    def get_options(self):
        return self.options

#------------------------------------------------------------------------------
# >>>>>>                         Unit Test Runner                        <<<<<<
#------------------------------------------------------------------------------

class TestRunner:
    def __init__(self, targets, options):
        self.targets = targets
        self.build_dir = "build%s_%s" % (options.m, options.profile)
        self.options = options

    def _test_executable(self, target):
        return "%s/%s/%s" % (self.build_dir, target['path'], target['name'])


    def _runfiles_dir(self, target):
        return "./%s.runfiles" % (self._test_executable(target))


    def _prepare_test_env(self, target):
        shutil.rmtree(self._runfiles_dir(target), ignore_errors = True)
        os.mkdir(self._runfiles_dir(target))
        link_name_list = []
        for i in target['options']['testdata']:
            if isinstance(i, tuple):
                data_target = i[0]
                link_name = i[1]
            else:
                data_target = link_name = i
            if '..' in data_target:
                continue
            if link_name.startswith('//'):
                link_name = link_name[2:]
            if link_name in link_name_list:
                _error_exit("Ambiguous testdata of //%s:%s: %s, exit..." % (
                             target['path'], target['name'], link_name))
            link_name_list.append(link_name)
            try:
                os.makedirs(os.path.dirname('%s/%s' % (
                        self._runfiles_dir(target), link_name)))
            except os.error:
                pass
            if data_target.startswith('//'):
                _warning("Test data not in the same directory with BUILD file")
                data_target = data_target[2:]
                os.symlink(os.path.abspath(data_target),
                        '%s/%s' % (self._runfiles_dir(target), link_name))
            else:
                os.symlink(os.path.abspath("%s/%s" % (target['path'], data_target)),
                       '%s/%s' % (self._runfiles_dir(target), link_name))

    def run(self):
        failed_targets = []
        for target in self.targets.values():
            if not (target['type'] == 'cc_test' or target['type'] == 'dynamic_cc_test'):
                continue
            self._prepare_test_env(target)
            old_pwd = _get_cwd()
            cmd = "%s --gtest_output=xml" % os.path.abspath(self._test_executable(target))
            if self.options.testargs:
                cmd = "%s %s" % (cmd, self.options.testargs)

            print "Running %s" % cmd
            sys.stdout.flush() # make sure output before scons if redirected

            os.chdir(self._runfiles_dir(target))
            p = subprocess.Popen(cmd, shell = True)
            p.wait()
            if p.returncode:
                target["test_exit_code"] = p.returncode
                failed_targets.append(target)

            os.chdir(old_pwd)

        print "============== Testing Summary ============="
        if failed_targets:
            print "Tests failed:"
            for i in failed_targets:
                print "%s/%s, exit code: %s" % (
                    i["path"], i["name"], i["test_exit_code"])
            return 1
        else:
            print "All Tests passed!"
            return 0


#------------------------------------------------------------------------------
# >>>>>>            Recursively Load and Execute BUILD Files             <<<<<<
#------------------------------------------------------------------------------

# Invoked by _load_targets.  Load and execute the BUILD
# file, which is a Python script, in source_dir.  Statements in BUILD
# depends on global variable current_source_dir, and will register build
# target/rules into global variables target_database.  If path/BUILD
# does NOT exsit, take action corresponding to action_if_fail.  The
# parameters processed_source_dirs refers to a set defined in the
# caller and used to avoid duplicated execution of BUILD files.
def _load_build_file(source_dir, action_if_fail, processed_source_dirs):
    source_dir = os.path.normpath(source_dir)
    # TODO(yiwang): the character '#' is a magic value.
    if source_dir in processed_source_dirs or source_dir == '#':
        return
    processed_source_dirs.add(source_dir)

    global current_source_dir
    old_path = current_source_dir
    current_source_dir = source_dir
    build_file = os.path.join(source_dir, 'BUILD')
    if os.path.exists(build_file):
        try:
            # The magic here is that a BUILD file is a Python script,
            # which can be loaded and executed by execfile().
            execfile(build_file)
        except SystemExit:
            _error_exit("%s: fatal error, exit..." % build_file)
        except:
            _error_exit('Parse error in %s, exit...\n%s' % (
                    build_file, traceback.format_exc()))
    else:
        if action_if_fail == WARN_IF_FAIL:
            print >>sys.stderr, '%s not exist, skip...' % build_file
        elif action_if_fail == ABORT_IF_FAIL:
            _error_exit('%s not exist, exit...' % build_file)
    current_source_dir = old_path


def _find_depender(dkey):
    for key in target_database:
        if dkey in target_database[key]['deps']:
            return "//%s:%s" % (target_database[key]["path"],
                                target_database[key]["name"])
    return None


# Get the relative path of a_path by considering reference_path as the
# root directory.  For example, if
#   reference_path = "/src/paralgo"
#   a_path        = "/src/paralgo/mapreduce_lite/sorted_buffer"
# then
#   _relative_path(a_path, reference_path) = "mapreduce_lite/sorted_buffer"
#
def _relative_path(a_path, reference_path):
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


# Parse and load targets, including those specified in command line
# and their direct and indirect dependencies, by loading related BUILD
# files.  Returns a map which contains all these targets.
def _load_targets(target_ids, working_dir, blade_root_dir):
    global target_database

    # targets specified in command line
    cited_targets = set()
    # cited_targets and all its dependencies
    related_targets = {}
    # source dirs mentioned in command line
    source_dirs = []
    # to prevent duplicated loading of BUILD files
    processed_source_dirs = set()

    # Parse command line target_ids.  For those in the form of <path>:<target>,
    # record (<path>,<target>) in cited_targets; for the rest (with <path>
    # but without <target>), record <path> into paths.
    for target_id in target_ids:
        if target_id.find(':') == -1:
            source_dir, target_name = target_id, '*'
        else:
            source_dir, target_name = target_id.rsplit(':', 1)

        source_dir = _relative_path(os.path.join(working_dir, source_dir),
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

    global command_targets
    command_targets = list(cited_targets)
    # Load BUILD files in paths, and add all loaded targets into
    # cited_targets.  Together with above step, we can ensure that all
    # targets mentioned in the command line are now in cited_targetts.
    for source_dir, action_if_fail in source_dirs:
        _load_build_file(source_dir, action_if_fail, processed_source_dirs)
    for key in target_database:
        cited_targets.add(key)

    # Starting from targets specified in command line, breath-first
    # propagate to load BUILD files containing directly and indirectly
    # dependent targets.  All these targets form related_targets,
    # which is a subset of target_databased created by loading  BUILD files.
    while cited_targets:
        source_dir, target_name = cited_targets.pop()
        target_id = (source_dir, target_name)
        if target_id in related_targets:
            continue

        _load_build_file(source_dir, ABORT_IF_FAIL, processed_source_dirs)
        if target_id not in target_database:
            raise Exception, "%s: target //%s:%s does not exists" % (
                _find_depender(target_id), source_dir, target_name)

        related_targets[target_id] = target_database[target_id]
        for key in related_targets[target_id]['deps']:
            if key not in related_targets:
                cited_targets.add(key)
    return related_targets


# The blade_root_dir is the directory which is the closest upper level
# directory of the current working directory, and containing a file
# named BLADE_ROOT.
def _find_blade_root_dir(working_dir):
    blade_root_dir = working_dir
    if blade_root_dir.endswith('/'):
        blade_root_dir = blade_root_dir[:-1]
    while blade_root_dir and blade_root_dir != "/":
        if os.path.isfile(os.path.join(blade_root_dir, "BLADE_ROOT")):
            break
        blade_root_dir = os.path.dirname(blade_root_dir)
    if not blade_root_dir or blade_root_dir == "/":
        _error_exit("Can't find the file 'BLADE_ROOT' in this or any upper directory.\n"
                    "Blade need this file as a placeholder to locate the root source directory "
                    "(aka the directory where you #include start from).\n"
                    "You should create it manually at the first time.")
    return blade_root_dir


#------------------------------------------------------------------------------
# >>>>>>                        The Main Entry                           <<<<<<
#------------------------------------------------------------------------------

def _main():
    # Check the python version
    if platform.python_version() < '2.6':
        _error_exit("please update your python version to 2.6 or above")

    cmd_options = CmdOptions()
    targets = cmd_options.get_args()
    if not targets:
        targets = ['.']

    options = cmd_options.get_options()
    global _color_enabled
    _color_enabled = options.color

    # Set global current_source_dir to the directory which contains the
    # file BLADE_ROOT, is upper than and is closest to the current
    # directory.  Set working_dir to current directory.
    global current_source_dir
    working_dir = _get_cwd()
    current_source_dir = _find_blade_root_dir(working_dir)
    os.chdir(current_source_dir)
    if current_source_dir != working_dir:
        print "Blade: Entering directory `%s'" % current_source_dir
        sys.stdout.flush() # make sure output before scons if redirected

    # Load targets specified in command line and their dependencies by
    # loading and running related BUILD files as Python scripts.
    related_targets = _load_targets(targets, working_dir, current_source_dir)

    # For each loaded target, expand its 'deps' property to include
    # all its direct and/or indirect dependencies.
    deps_expander = DependenciesExpander(related_targets)
    deps_expander.expand_deps()
    targets = deps_expander.get_targets()

    lock_file = None
    locked_scons = False
    try:
        lock_file = open('.SConstruct.lock', 'w')

        (locked_scons,
         ret_code) = _lock_file(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not locked_scons:
            if ret_code == errno.EAGAIN:
                _error_exit("There is already an active building in current source "
                            "dir tree,\n"
                            "or make sure there is no SConstruct file existed with "
                            "BLADE_ROOT. Blade will exit...")
            else:
                _error_exit("Lock exception, please try it later.")

        generator = SconsRulesGenerator('SConstruct',
                                        targets,
                                        options,
                                        current_source_dir)
        generator.output()

        if options.scons_only:
            return 0

        if options.clean:
            p = subprocess.Popen(
                "scons --duplicate=soft-copy -c -s --cache-show", shell = True)
            p.wait()
            return p.returncode

        scons_options = '--duplicate=soft-copy -Q --cache-show'
        scons_options += " -j %s %s" % (
                options.jobs, '-k' if options.keep_going else '')

        p = subprocess.Popen(
        "scons %s" % scons_options,
        shell = True)
        try:
            p.wait()
            if p.returncode:
                return p.returncode
        except: # KeyboardInterrupt
            return 1

        if options.test:
            test_runner = TestRunner(targets, options)
            return test_runner.run()

    finally:
        if not options.scons_only:
            try:
                if locked_scons:
                    os.remove(os.path.join(current_source_dir, 'SConstruct'))
                    _unlock_file(lock_file.fileno())
                lock_file.close()
            except Exception, e:
                print e
                pass

    return 0


def main():
    exit_code = 0
    try:
        exit_code = _main()
    except SystemExit, e:
        exit_code = e.code
    except KeyboardInterrupt:
        _error_exit("keyboard interrupted", -signal.SIGINT)
    except:
        _error_exit(traceback.format_exc())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
