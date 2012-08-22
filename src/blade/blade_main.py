"""
 Copyright 2011 Tencent Inc.

 Authors: Huan Yu <huanyu@tencent.com>
          Feng Chen <phongchen@tencent.com>
          Yi Wang <yiwang@tencent.com>
          Chong Peng <michaelpeng@tencent.com>

 Blade is a software building system built upon SCons, but restricts
 the generality and flexibility of SCons to prevent unnecessary
 error-prone complexity.  With Blade, users wrote a BUILD file and
 put it in each of the source directory.  In each BUILD file, there
 could be one or more build rules, each has a TARGET NAME, source
 files and dependent targets.  Blade suports the following types of
 build rules:


    cc_binary         -- build an executable binary from C++ source
    cc_library        -- build a library from C++ source
    cc_plugin         -- build a plugin from C++ source
    cc_test           -- build a unittest binary from C++ source
    gen_rule          -- used to specify a general building rule
    java_jar          -- build java jar from java source files
    lex_yacc_library  -- build a library from lex/yacc source
    proto_library     -- build a library from Protobuf source
    resource_library  -- build resource library and gen header files
    swig_library      -- build swig library for python and java

 A target may depend on other target(s), where the dependency is
 transitive.  A dependent target is referred by a TARGET ID, which
 has either of the following forms:

   //<source_dir>:<target_name> -- target defined in <source_dir>/BUILD
   :<target_name>               -- target defined in the current BUILD file
   #<target_name>               -- target is a system library, e.g., pthread

 where <source_dir> is an absolute path rooted at the source tree and
 specifying where the BUILD file locates, <target_name> specifies a
 target in the BUILD file, and '//' denotes the root of the source tree.

 Users invoke Blade from the command line to build (or clean, or
 test) one or more rule/targets.  In the command line, a target id
 is specified in either of the following forms:

   <path>:<target_name> -- to build target defined in <path>/BUILD
   <path>               -- to build all targets defined in <path>/BUILD
   <path>/...           -- to build all targets in all BUILD files in
                           <path> and its desendant directories.

 Note that <path> in command line targets is an operating system
 path, which might be a relative path, but <source_dir> in a BUILD
 referring to a dependent target must be an absolute path, rooted at
 '//'.

 For example, the following command line

    blade base mapreduce_lite/... parallel_svm:perf_test

 builds all targets in base/BUILD, all targets in all BUILDs under
 directory mapreduce_lite, and the target perf_test defined in
 parallel_svm/BUILD
"""


import errno
import fcntl
import os
import platform
import signal
import subprocess
import sys
import traceback
import blade
import configparse
from blade import Blade
from blade_util import error
from blade_util import error_exit
from blade_util import get_cwd
from blade_util import info
from blade_util import lock_file
from blade_util import unlock_file
from command_args import CmdArguments
from configparse import BladeConfig
from load_build_files import find_blade_root_dir
from optparse import OptionParser


# Query targets
query_targets = None

# Run target
run_target = None

# Return code
blade_ret_code = 0

def _main(blade_path):
    """The main entry of blade. """

    cmd_options = CmdArguments()

    command = cmd_options.get_command()
    targets = cmd_options.get_targets()

    global query_targets
    global run_target
    if command == 'query':
        query_targets = list(targets)
    if command == 'run':
        run_target = targets[0]

    if not targets:
        targets = ['.']
    options = cmd_options.get_options()

    # Set current_source_dir to the directory which contains the
    # file BLADE_ROOT, is upper than and is closest to the current
    # directory.  Set working_dir to current directory.
    working_dir = get_cwd()
    current_source_dir = find_blade_root_dir(working_dir)
    os.chdir(current_source_dir)
    if current_source_dir != working_dir:
        # This message is required by vim quickfix mode if pwd is changed during
        # the building, DO NOT change the pattern of this message.
        print "Blade: Entering directory `%s'" % current_source_dir

    # Init global configuration manager
    configparse.blade_config = BladeConfig(current_source_dir)
    configparse.blade_config.parse()

    # Init global blade manager.
    current_building_path = "build%s_%s" % (options.m, options.profile)

    lock_file_fd = None
    locked_scons = False
    try:
        lock_file_fd = open('.SConstruct.lock', 'w')
        old_fd_flags =  fcntl.fcntl(lock_file_fd.fileno(), fcntl.F_GETFD)
        fcntl.fcntl(lock_file_fd.fileno(), fcntl.F_SETFD, old_fd_flags | fcntl.FD_CLOEXEC)

        (locked_scons,
         ret_code) = lock_file(lock_file_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not locked_scons:
            if ret_code == errno.EAGAIN:
                error_exit("There is already an active building in current source "
                           "dir tree,\n"
                           "or make sure there is no SConstruct file existed with "
                           "BLADE_ROOT. Blade will exit...")
            else:
                error_exit("Lock exception, please try it later.")

        if command == 'query' and (
                hasattr(options, 'depended') and options.depended):
            targets = ['...']
        blade.blade = Blade(targets,
                            blade_path,
                            working_dir,
                            current_building_path,
                            current_source_dir,
                            options,
                            blade_command=command)

        # Build the targets
        blade.blade.generate()

        # Flush the printing
        sys.stdout.flush()
        sys.stderr.flush()

        # Tune the jobs num
        if command in ['build', 'run', 'test']:
            options.jobs = blade.blade.tune_parallel_jobs_num()

        # Switch case due to different sub command
        action = {
                 'build' : build,
                 'run'   : run,
                 'test'  : test,
                 'clean' : clean,
                 'query' : query
                 }[command](options)
        return action
    finally:
        if (hasattr(options, 'scons_only') and not options.scons_only) or (
                command == 'clean' or command == 'query' ):
            try:
                if locked_scons:
                    os.remove(os.path.join(current_source_dir, 'SConstruct'))
                    unlock_file(lock_file_fd.fileno())
                lock_file_fd.close()
            except Exception as inst:
                pass
    return 0


def _build(options):
    if options.scons_only:
        return 0

    scons_options = '--duplicate=soft-copy --cache-show'
    scons_options += " -j %s %s" % (
            options.jobs, '-k' if options.keep_going else '')

    p = subprocess.Popen("scons %s" % scons_options, shell=True)
    try:
        p.wait()
        if p.returncode:
            error("building failure")
            return p.returncode
    except: # KeyboardInterrupt
        return 1
    return 0


def build(options):
    return _build(options)


def run(options):
    global run_target
    ret = _build(options)
    if ret:
        return ret
    return blade.blade.run(run_target)


def test(options):
    ret =  _build(options)
    if ret:
        return ret
    return blade.blade.test()


def clean(options):
    info("cleaning...(hint: please specify --generate-dynamic to clean your so)")
    p = subprocess.Popen(
    "scons --duplicate=soft-copy -c -s --cache-show", shell=True)
    p.wait()
    info("cleaning done.")
    return p.returncode


def query(options):
    global query_targets
    return blade.blade.query(query_targets)


def main(blade_path):
    exit_code = 0
    try:
        exit_code = _main(blade_path)
    except SystemExit as e:
        exit_code = e.code
    except KeyboardInterrupt:
        error_exit("keyboard interrupted", -signal.SIGINT)
    except:
        error_exit(traceback.format_exc())
    sys.exit(exit_code)


"""About main entry

Main entry is placed to __main__.py, cause we need to pack
the python sources to a zip ball and invoke the blade through
command line in this way: python blade.zip

"""
